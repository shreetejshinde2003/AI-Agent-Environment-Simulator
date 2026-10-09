import Button from "../common/Button";

export default function HRAccessRequired({onManage, onRetry, refreshing = false}) {
  return <section aria-labelledby="hr-access-title">
    <h2 id="hr-access-title">HR responsibility needed</h2>
    <p>An active HR Recruiter, Reviewer or Approver role is required. Your account has organization access, but no active hiring responsibility here.</p>
    <p>In Organizations, keep this workspace selected, find Member management, then expand Hiring responsibilities for the member. An Owner or Admin can assign Recruiter, Reviewer or Approver duties. Owner/Admin access alone does not grant HR permission.</p>
    <p>If you cannot manage members, ask an Owner or Admin to assign the appropriate responsibility. After it is assigned, return here and check access again.</p>
    <Button variant="primary" onClick={onManage}>Open Organizations</Button>{" "}
    <Button disabled={refreshing} onClick={onRetry}>{refreshing ? "Checking HR access…" : "Check HR access again"}</Button>
  </section>;
}
