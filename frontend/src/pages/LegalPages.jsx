import "./LegalPages.css";

const LAST_UPDATED = "7 October 2026";

function LegalLayout({ title, children }) {
  return (
    <main className="legal-page">
      <section className="legal-card">
        <header className="legal-header">
          <div>
            <p className="legal-eyebrow">Agent Environment Simulator</p>
            <h1>{title}</h1>
            <p className="legal-updated">Last updated: {LAST_UPDATED}</p>
          </div>

          <a className="legal-home-link" href="/">
            Back to application
          </a>
        </header>

        <div className="legal-content">
          {children}
        </div>

        <footer className="legal-footer">
          <a href="/privacy">Privacy Policy</a>
          <span aria-hidden="true">·</span>
          <a href="/terms">Terms of Service</a>
        </footer>
      </section>
    </main>
  );
}

export function PrivacyPolicy() {
  return (
    <LegalLayout title="Privacy Policy">
      <p>
        Agent Environment Simulator is an academic multi-agent AI research
        application. This policy explains what information the application
        receives when you sign in with Google and how that information is used.
      </p>

      <h2>Information we receive</h2>
      <p>
        When you choose to sign in with Google, the application may receive
        your Google account identifier, email address, display name, profile
        picture, and whether Google reports the email address as verified.
      </p>

      <h2>How we use the information</h2>
      <p>
        This information is used only to authenticate you, create or locate
        your local application account, maintain your signed-in session, and
        provide access to application features.
      </p>

      <h2>Information stored by the application</h2>
      <p>
        The application stores a local user record and a revocable application
        session record. Session credentials are stored server-side as a
        one-way digest rather than as the original browser session token.
      </p>
      <p>
        The application also stores workspace memberships, separate HR roles,
        simulation and research execution evidence, custom agent revisions,
        hiring requirements, organization knowledge, job description revisions,
        and attributed human review decisions. Organization records are shared
        with authorized active members according to their permissions.
      </p>

      <h2>Google credentials and services</h2>
      <p>
        The application does not store your Google password. It also does not
        persist Google access tokens, refresh tokens, or ID tokens in the
        application database.
      </p>

      <p>
        The application currently requests only basic identity permissions:
        OpenID identity, email address, and profile information. It does not
        request access to Gmail, Google Drive, Google Calendar, Google
        Contacts, or other Google account content.
      </p>

      <h2>Sharing of information</h2>
      <p>
        Authentication information is not sold to advertisers. Information is
        used only for operating the application and is not intentionally shared
        with unrelated third parties, except for infrastructure providers
        required to host and operate the service.
      </p>

      <h2>AI processing</h2>
      <p>
        Google profile information is not intentionally sent to the
        application's AI model provider as part of normal authentication.
        Authentication and AI workflow execution are separate parts of the
        system.
      </p>
      <p>
        Running AI assistance sends the selected saved HR source revisions to
        Groq. Simulation and research runs send their directives and prepared
        reference context to the configured Groq model. Do not include secrets
        or confidential personal information in demonstration inputs. AI
        proposals do not automatically update or approve human-authored records.
      </p>

      <h2>Data retention and account access</h2>
      <p>
        Local user and session records may be retained for application
        operation, testing, security, and academic demonstration purposes.
        Sessions can be revoked by signing out.
      </p>
      <p>
        Signing out does not delete saved application records. The recycle bin
        can hide and restore simulation runs; permanent deletion is restricted
        to eligible records without retained execution evidence. Automatic
        retention and account erasure are not implemented.
      </p>

      <h2>Security</h2>
      <p>
        The application uses Google OAuth/OpenID Connect for authentication,
        server-side session handling, HTTPS in production, and HttpOnly session
        cookies.
      </p>

      <h2>Contact</h2>
      <p>
        Questions about this policy can be sent to the developer support email
        listed on the application's Google sign-in consent screen.
      </p>
    </LegalLayout>
  );
}

export function TermsOfService() {
  return (
    <LegalLayout title="Terms of Service">
      <p>
        These Terms of Service apply to use of Agent Environment Simulator,
        an academic and research-oriented multi-agent AI application.
      </p>

      <h2>Purpose of the application</h2>
      <p>
        The application is intended for educational, research, demonstration,
        and software-development purposes. It may include experimental AI
        workflows, simulations, evaluation features, and human-reviewed
        application workflows.
      </p>

      <h2>Account access</h2>
      <p>
        You may sign in using a supported Google account. You are responsible
        for the security of your Google account and for activity performed
        through your authenticated application session.
      </p>

      <h2>Acceptable use</h2>
      <p>
        You must not attempt to bypass authentication, access another user's
        or organization's private data, disrupt the service, abuse system
        resources, or use the application for unlawful purposes.
      </p>

      <h2>AI-generated output</h2>
      <p>
        AI-generated responses may be incomplete, inaccurate, or unsuitable
        for a particular purpose. Outputs should be reviewed by a human before
        being relied upon for consequential decisions.
      </p>

      <h2>Human review</h2>
      <p>
        HR assistance produces proposals for authorized humans to inspect.
        Recruiters author and submit saved job descriptions, Reviewers assess
        them, and Approvers make explicit decisions about the submitted revision.
        Approval does not transfer to later revisions. Publication and autonomous
        hiring decisions are not implemented.
      </p>

      <h2>Availability</h2>
      <p>
        The service is provided on an academic and experimental basis.
        Availability, features, integrations, and stored demonstration data
        may change during development.
      </p>

      <h2>Privacy</h2>
      <p>
        Use of authentication information is described in the
        {" "}
        <a href="/privacy">Privacy Policy</a>.
      </p>

      <h2>Changes to these terms</h2>
      <p>
        These terms may be updated as the project develops. The latest version
        will be published on this page with an updated date.
      </p>

      <h2>Contact</h2>
      <p>
        Questions about these terms can be sent to the developer support email
        listed on the application's Google sign-in consent screen.
      </p>
    </LegalLayout>
  );
}
