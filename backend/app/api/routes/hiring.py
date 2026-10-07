"""Authenticated organization hiring foundation and human review endpoints."""
from fastapi import APIRouter, Header, HTTPException, Request

from app.api.routes.workspaces import require_request_permission, request_user_id
from app.models.schemas import (HiringRequirementInput, HiringRequirementUpdate, RoleKnowledgeInput,
                                RoleKnowledgeUpdate, JobDescriptionInput, JobDescriptionUpdate, HRRecord,
                                HRReviewSubmissionInput, HRReviewDecisionInput, HRReviewRecord, HRReviewEvent)
from app.security.rbac import AuthorizationError, Permission
from app.storage.database import repository
from app.storage.hiring import HiringError

router = APIRouter(prefix="/hiring", tags=["hiring"])


def scope(request, workspace_id):
    workspace = require_request_permission(request, workspace_id, Permission.WORKSPACE_VIEW)
    if workspace["kind"] != "organization":
        raise HTTPException(403, {"code": "organization_required", "message": "Select an organization for HR Hiring."})
    return dict(workspace_id=workspace["id"], user_id=request_user_id(request))


def operation(call, *args, **kwargs):
    try:
        return call(*args, **kwargs)
    except HiringError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc
    except AuthorizationError as exc:
        raise HTTPException(403, {"code": "hr_permission_denied", "message": "An active HR human role with this permission is required."}) from exc


@router.get("/capabilities")
def capabilities(request: Request, x_workspace_id: str | None = Header(default=None)):
    return operation(repository.hiring_capabilities, **scope(request, x_workspace_id))


def register(kind, create_model, update_model):
    def listing(request: Request, x_workspace_id: str | None = Header(default=None)):
        return operation(repository.list_hiring, kind, **scope(request, x_workspace_id))

    def detail(record_id: str, request: Request, x_workspace_id: str | None = Header(default=None)):
        return operation(repository.get_hiring, kind, record_id, **scope(request, x_workspace_id))

    def revisions(record_id: str, request: Request, x_workspace_id: str | None = Header(default=None)):
        return operation(repository.get_hiring, kind, record_id, revisions=True, **scope(request, x_workspace_id))

    def create(payload: create_model, request: Request, x_workspace_id: str | None = Header(default=None)):
        return operation(repository.save_hiring, kind, payload, **scope(request, x_workspace_id))

    def update_record(record_id: str, payload: update_model, request: Request,
                      x_workspace_id: str | None = Header(default=None)):
        content = create_model.model_validate(payload.model_dump(exclude={"expected_revision"}))
        return operation(repository.save_hiring, kind, content, record_id=record_id,
                         expected_revision=payload.expected_revision, **scope(request, x_workspace_id))

    def linked_descriptions(record_id: str, revision: int, request: Request,
                            x_workspace_id: str | None = Header(default=None)):
        return operation(repository.linked_job_descriptions, kind, record_id, revision,
                         **scope(request, x_workspace_id))

    path = "/" + kind.replace("_", "-")
    if kind in {"requirements", "role_knowledge"}:
        router.add_api_route(path + "/{record_id}/revisions/{revision}/job-descriptions",
                             linked_descriptions, methods=["GET"], response_model=list[HRRecord],
                             name=kind + "_linked_descriptions")
    for suffix, endpoint, methods, response in (("", listing, ["GET"], list[HRRecord]),
            ("", create, ["POST"], HRRecord), ("/{record_id}", detail, ["GET"], HRRecord),
            ("/{record_id}", update_record, ["PUT"], HRRecord),
            ("/{record_id}/revisions", revisions, ["GET"], list[HRRecord])):
        router.add_api_route(path + suffix, endpoint, methods=methods, response_model=response,
                             status_code=201 if endpoint is create else 200,
                             name=kind + "_" + endpoint.__name__)


register("requirements", HiringRequirementInput, HiringRequirementUpdate)
register("role_knowledge", RoleKnowledgeInput, RoleKnowledgeUpdate)
register("job_descriptions", JobDescriptionInput, JobDescriptionUpdate)


@router.get('/reviews/capabilities')
def review_capabilities(request: Request, x_workspace_id: str | None = Header(default=None)):
    return operation(repository.review_capabilities, **scope(request, x_workspace_id))


@router.get('/reviews', response_model=list[HRReviewRecord])
def review_list(request: Request, x_workspace_id: str | None = Header(default=None)):
    return operation(repository.list_reviews, **scope(request, x_workspace_id))


@router.post('/reviews', response_model=HRReviewRecord, status_code=201)
def review_submit(payload: HRReviewSubmissionInput, request: Request,
                  x_workspace_id: str | None = Header(default=None)):
    return operation(repository.submit_review, payload, **scope(request, x_workspace_id))


@router.get('/reviews/{submission_id}', response_model=HRReviewRecord)
def review_detail(submission_id: str, request: Request, x_workspace_id: str | None = Header(default=None)):
    return operation(repository.get_review, submission_id, **scope(request, x_workspace_id))


@router.get('/reviews/{submission_id}/history', response_model=list[HRReviewEvent])
def review_history(submission_id: str, request: Request, x_workspace_id: str | None = Header(default=None)):
    return operation(repository.get_review, submission_id, **scope(request, x_workspace_id)).history


@router.post('/reviews/{submission_id}/review', response_model=HRReviewRecord)
def review_decision(submission_id: str, payload: HRReviewDecisionInput, request: Request,
                    x_workspace_id: str | None = Header(default=None)):
    return operation(repository.decide_review, submission_id, payload, **scope(request, x_workspace_id))


@router.post('/reviews/{submission_id}/approval', response_model=HRReviewRecord)
def approval_decision(submission_id: str, payload: HRReviewDecisionInput, request: Request,
                      x_workspace_id: str | None = Header(default=None)):
    return operation(repository.decide_review, submission_id, payload, approval=True, **scope(request, x_workspace_id))
