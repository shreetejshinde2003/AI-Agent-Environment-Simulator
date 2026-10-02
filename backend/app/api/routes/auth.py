"""Google OAuth/OpenID Connect authentication.

Google authenticates the person.
This application creates only a local identity and opaque revocable session.

Google passwords, access tokens, refresh tokens and ID tokens are never
persisted in the application database.
"""

from __future__ import annotations

import asyncio
import hmac
import uuid
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token as google_id_token

from app.core.config import settings
from app.security.session import (
    OAUTH_NONCE_COOKIE,
    OAUTH_PKCE_COOKIE,
    OAUTH_STATE_COOKIE,
    OAUTH_TRANSACTION_SECONDS,
    SESSION_COOKIE_NAME,
    SESSION_HOURS,
    create_opaque_token,
    create_pkce_pair,
    parse_timestamp,
    session_expiry,
    token_digest,
    utcnow,
)
from app.storage.database import repository


router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)

GOOGLE_AUTHORIZATION_ENDPOINT = (
    "https://accounts.google.com/o/oauth2/v2/auth"
)

GOOGLE_TOKEN_ENDPOINT = (
    "https://oauth2.googleapis.com/token"
)

GOOGLE_SCOPES = "openid email profile"


def _require_google_configuration() -> None:
    missing = [
        name
        for name, value in (
            (
                "GOOGLE_CLIENT_ID",
                settings.GOOGLE_CLIENT_ID,
            ),
            (
                "GOOGLE_CLIENT_SECRET",
                settings.GOOGLE_CLIENT_SECRET,
            ),
            (
                "GOOGLE_REDIRECT_URI",
                settings.GOOGLE_REDIRECT_URI,
            ),
            (
                "FRONTEND_URL",
                settings.FRONTEND_URL,
            ),
        )
        if not value.strip()
    ]

    if missing:
        raise HTTPException(
            503,
            detail={
                "code": "google_auth_not_configured",
                "message": (
                    "Google authentication is not configured."
                ),
            },
        )


def _production_cookie() -> bool:
    return settings.GOOGLE_REDIRECT_URI.startswith(
        "https://"
    )


def _set_oauth_cookie(
    response: Response,
    name: str,
    value: str,
) -> None:
    response.set_cookie(
        key=name,
        value=value,
        max_age=OAUTH_TRANSACTION_SECONDS,
        httponly=True,
        secure=_production_cookie(),
        samesite="lax",
        path="/api/v1/auth/google/callback",
    )


def _clear_oauth_cookies(
    response: Response,
) -> None:
    for name in (
        OAUTH_STATE_COOKIE,
        OAUTH_NONCE_COOKIE,
        OAUTH_PKCE_COOKIE,
    ):
        response.delete_cookie(
            key=name,
            path="/api/v1/auth/google/callback",
            secure=_production_cookie(),
            httponly=True,
            samesite="lax",
        )


def _set_session_cookie(
    response: Response,
    token: str,
) -> None:
    secure = _production_cookie()

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_HOURS * 60 * 60,
        httponly=True,
        secure=secure,
        # Railway and Vercel are separate sites in production.
        samesite="none" if secure else "lax",
        path="/",
    )


def _clear_session_cookie(
    response: Response,
) -> None:
    secure = _production_cookie()

    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        secure=secure,
        httponly=True,
        samesite="none" if secure else "lax",
    )


async def _exchange_code(
    *,
    code: str,
    code_verifier: str,
) -> dict:
    """Exchange the one-time authorization code.

    Returned provider tokens exist only in process memory long enough to
    verify identity. They are never persisted.
    """

    try:
        async with httpx.AsyncClient(
            timeout=15.0
        ) as client:
            response = await client.post(
                GOOGLE_TOKEN_ENDPOINT,
                data={
                    "code": code,
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                    "grant_type": "authorization_code",
                    "code_verifier": code_verifier,
                },
            )

    except httpx.HTTPError as exc:
        raise HTTPException(
            502,
            detail={
                "code": "google_token_exchange_failed",
                "message": (
                    "Google authentication service could not be reached."
                ),
            },
        ) from exc

    if response.status_code != 200:
        raise HTTPException(
            401,
            detail={
                "code": "google_token_exchange_rejected",
                "message": (
                    "Google rejected the authorization code."
                ),
            },
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise HTTPException(
            502,
            detail={
                "code": "invalid_google_token_response",
                "message": (
                    "Google returned an invalid token response."
                ),
            },
        ) from exc

    if not isinstance(payload, dict):
        raise HTTPException(
            502,
            detail={
                "code": "invalid_google_token_response",
                "message": (
                    "Google returned an invalid token response."
                ),
            },
        )

    return payload


def _verify_google_id_token(
    raw_id_token: str,
) -> dict:
    """Verify signature plus standard Google OIDC claims."""

    claims = google_id_token.verify_oauth2_token(
        raw_id_token,
        GoogleRequest(),
        settings.GOOGLE_CLIENT_ID,
    )

    if not isinstance(claims, dict):
        raise ValueError(
            "Invalid Google identity claims."
        )

    return claims


def _public_user(user: dict) -> dict:
    return {
        "id": user["id"],
        "email": user["email"],
        "displayName": user["display_name"],
        "profilePicture": user["profile_picture"],
        "emailVerified": user["email_verified"],
        "active": user["active"],
    }


def _authenticated_record(
    request: Request,
) -> tuple[dict, dict]:
    token = request.cookies.get(
        SESSION_COOKIE_NAME
    )

    if not token:
        raise HTTPException(
            401,
            detail={
                "code": "not_authenticated",
                "message": "Authentication required.",
            },
        )

    session = repository.get_auth_session_by_digest(
        token_digest(token)
    )

    if session is None:
        raise HTTPException(
            401,
            detail={
                "code": "invalid_session",
                "message": "Authentication session is invalid.",
            },
        )

    if session["revoked_at"] is not None:
        raise HTTPException(
            401,
            detail={
                "code": "session_revoked",
                "message": "Authentication session has been revoked.",
            },
        )

    if parse_timestamp(
        session["expires_at"]
    ) <= utcnow():
        raise HTTPException(
            401,
            detail={
                "code": "session_expired",
                "message": "Authentication session has expired.",
            },
        )

    user = repository.get_user(
        session["user_id"]
    )

    if user is None or not user["active"]:
        raise HTTPException(
            401,
            detail={
                "code": "user_unavailable",
                "message": "Authenticated user is unavailable.",
            },
        )

    return user, session


@router.get("/google/login")
async def google_login():
    """Begin the browser-based Google authorization-code flow."""

    _require_google_configuration()

    state = create_opaque_token()
    nonce = create_opaque_token()
    verifier, challenge = create_pkce_pair()

    query = urlencode(
        {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "response_type": "code",
            "scope": GOOGLE_SCOPES,
            "state": state,
            "nonce": nonce,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "access_type": "online",
            "prompt": "select_account",
        }
    )

    response = RedirectResponse(
        url=(
            f"{GOOGLE_AUTHORIZATION_ENDPOINT}"
            f"?{query}"
        ),
        status_code=302,
    )

    _set_oauth_cookie(
        response,
        OAUTH_STATE_COOKIE,
        state,
    )

    _set_oauth_cookie(
        response,
        OAUTH_NONCE_COOKIE,
        nonce,
    )

    _set_oauth_cookie(
        response,
        OAUTH_PKCE_COOKIE,
        verifier,
    )

    return response


@router.get("/google/callback")
async def google_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    """Complete Google authentication and create a local app session."""

    _require_google_configuration()

    if error:
        raise HTTPException(
            400,
            detail={
                "code": "google_authorization_denied",
                "message": (
                    "Google authorization was cancelled or denied."
                ),
            },
        )

    expected_state = request.cookies.get(
        OAUTH_STATE_COOKIE
    )

    nonce = request.cookies.get(
        OAUTH_NONCE_COOKIE
    )

    verifier = request.cookies.get(
        OAUTH_PKCE_COOKIE
    )

    if (
        not state
        or not expected_state
        or not hmac.compare_digest(
            state,
            expected_state,
        )
    ):
        raise HTTPException(
            400,
            detail={
                "code": "invalid_oauth_state",
                "message": (
                    "OAuth state validation failed."
                ),
            },
        )

    if not code or not nonce or not verifier:
        raise HTTPException(
            400,
            detail={
                "code": "incomplete_oauth_transaction",
                "message": (
                    "OAuth transaction data is incomplete."
                ),
            },
        )

    token_payload = await _exchange_code(
        code=code,
        code_verifier=verifier,
    )

    raw_id_token = token_payload.get(
        "id_token"
    )

    if not isinstance(
        raw_id_token,
        str,
    ) or not raw_id_token:
        raise HTTPException(
            401,
            detail={
                "code": "google_identity_missing",
                "message": (
                    "Google did not provide an identity token."
                ),
            },
        )

    try:
        claims = await asyncio.to_thread(
            _verify_google_id_token,
            raw_id_token,
        )
    except Exception as exc:
        raise HTTPException(
            401,
            detail={
                "code": "invalid_google_identity",
                "message": (
                    "Google identity verification failed."
                ),
            },
        ) from exc

    returned_nonce = claims.get(
        "nonce"
    )

    if (
        not isinstance(returned_nonce, str)
        or not hmac.compare_digest(
            returned_nonce,
            nonce,
        )
    ):
        raise HTTPException(
            401,
            detail={
                "code": "invalid_google_nonce",
                "message": (
                    "Google identity nonce validation failed."
                ),
            },
        )

    google_sub = claims.get("sub")
    email = claims.get("email")
    email_verified = claims.get(
        "email_verified"
    )

    if (
        not isinstance(google_sub, str)
        or not google_sub
        or not isinstance(email, str)
        or not email
        or email_verified is not True
    ):
        raise HTTPException(
            401,
            detail={
                "code": "google_identity_incomplete",
                "message": (
                    "A verified Google email identity is required."
                ),
            },
        )

    display_name = claims.get("name")

    if not isinstance(
        display_name,
        str,
    ) or not display_name.strip():
        display_name = email.split(
            "@",
            1,
        )[0]

    picture = claims.get("picture")

    if picture is not None and not isinstance(
        picture,
        str,
    ):
        picture = None

    now = utcnow()
    existing = repository.get_user_by_google_sub(
        google_sub
    )

    if existing is not None:
        if not existing["active"]:
            raise HTTPException(
                403,
                detail={
                    "code": "account_disabled",
                    "message": (
                        "This account has been disabled."
                    ),
                },
            )

        user = dict(
            existing,
            email=email,
            display_name=display_name.strip(),
            profile_picture=picture,
            email_verified=True,
            last_login_at=now.isoformat(),
        )

    else:
        user = {
            "id": (
                f"USR-{uuid.uuid4().hex[:16]}"
            ),
            "google_sub": google_sub,
            "email": email,
            "display_name": (
                display_name.strip()
            ),
            "profile_picture": picture,
            "email_verified": True,
            "active": True,
            "created_at": now.isoformat(),
            "last_login_at": now.isoformat(),
        }

    repository.save_user(user)

    opaque_session_token = create_opaque_token()
    expires_at = session_expiry()

    repository.save_auth_session(
        {
            "id": (
                f"SES-{uuid.uuid4().hex[:20]}"
            ),
            "user_id": user["id"],
            "token_digest": token_digest(
                opaque_session_token
            ),
            "created_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "revoked_at": None,
        }
    )

    destination = (
        settings.FRONTEND_URL.rstrip("/")
        + "/?auth=success"
    )

    response = RedirectResponse(
        url=destination,
        status_code=302,
    )

    _clear_oauth_cookies(response)

    _set_session_cookie(
        response,
        opaque_session_token,
    )

    return response


@router.get("/me")
async def me(request: Request):
    user, _ = _authenticated_record(
        request
    )

    return {
        "authenticated": True,
        "user": _public_user(user),
    }


@router.post("/logout", status_code=204)
async def logout(request: Request):
    token = request.cookies.get(
        SESSION_COOKIE_NAME
    )

    if token:
        session = (
            repository
            .get_auth_session_by_digest(
                token_digest(token)
            )
        )

        if (
            session is not None
            and session["revoked_at"] is None
        ):
            repository.revoke_auth_session(
                session["id"],
                utcnow().isoformat(),
            )

    response = Response(
        status_code=204
    )

    _clear_session_cookie(response)

    return response
