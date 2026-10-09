import {
  Bot,
  ShieldCheck,
} from "lucide-react";

import { AUTH_LOGIN_URL } from "../services/authClient";
import { sessionPresentation } from "../utils/sessionPresentation";
import Button from "../components/common/Button";
import "./Login.css";

export default function Login({
  error = null,
  onRetry,
}) {
  const feedback = error ? sessionPresentation(error) : null;
  return (
    <main className="login-page">
      <section className="login-panel">
        <div className="login-brand-icon">
          <Bot size={30} strokeWidth={1.9} />
        </div>

        <p className="login-eyebrow">
          Agent Environment Simulator
        </p>

        <h1>Sign in to continue</h1>

        <p className="login-description">
          Access the multi-agent simulation and
          evaluation workspace using your Google
          account.
        </p>

        {error && (
          <div
            className="login-error"
            role="alert"
          >
            <strong>{feedback.title}</strong>
            <p>{feedback.message}</p>
          </div>
        )}

        {error && !feedback.signIn && onRetry && <Button variant="primary" onClick={onRetry}>Retry connection</Button>}

        <a
          className="google-login-button"
          href={AUTH_LOGIN_URL}
        >
          <svg
            viewBox="0 0 24 24"
            aria-hidden="true"
            className="google-login-icon"
          >
            <path
              fill="currentColor"
              d="M21.35 11.1H12v2.98h5.38c-.46 2.55-2.91 3.74-5.38 3.74a5.82 5.82 0 1 1 0-11.64c1.47 0 2.79.52 3.83 1.53l2.24-2.18A8.88 8.88 0 1 0 12 20.99c5.13 0 8.52-3.61 8.52-8.69 0-.58-.06-.92-.17-1.2Z"
            />
          </svg>

          <span>Continue with Google</span>
        </a>

        <div className="login-security">
          <ShieldCheck
            size={16}
            aria-hidden="true"
          />
          <span>
            Google authenticates your identity.
            The application does not store your
            Google password.
          </span>
        </div>

        <footer className="login-footer">
          <a href="/privacy">
            Privacy Policy
          </a>
          <span aria-hidden="true">·</span>
          <a href="/terms">
            Terms of Service
          </a>
        </footer>
      </section>
    </main>
  );
}
