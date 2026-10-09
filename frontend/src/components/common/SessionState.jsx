import Button from "./Button";
import { sessionPresentation } from "../../utils/sessionPresentation";
import { AUTH_LOGIN_URL } from "../../services/authClient";
import "../../pages/Login.css";

export default function SessionState({title, description, error, onRetry, context = "session"}) {
  const feedback = error ? sessionPresentation(error, context) : null;
  return <main className="login-page">
    <section className="login-panel" aria-busy={!error}>
      <p className="login-eyebrow">Agent Environment Simulator</p>
      <h1>{feedback?.title ?? title}</h1>
      <p className="login-description" role={error ? "alert" : "status"}>{feedback?.message ?? description}</p>
      {error && (feedback.signIn ? <a className="google-login-button" href={AUTH_LOGIN_URL}>Sign in again</a> :
        <Button variant="primary" onClick={onRetry}>Try again</Button>)}
    </section>
  </main>;
}
