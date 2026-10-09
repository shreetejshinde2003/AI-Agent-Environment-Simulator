import {useState} from "react";
import Button from "../common/Button";
import {draftWorkflow} from "../../utils/hrWorkflow";

export default function HRJourney({snapshot, onNavigate}) {
  const [requirementId,setRequirementId]=useState("");
  const requirements=snapshot.records.requirements ?? [];
  const requirement=requirements.find(item=>item.id===requirementId) ?? requirements[0];
  const drafts=(snapshot.records["job-descriptions"] ?? []).filter(item=>item.content.requirement.id===requirement?.id);
  const draft=drafts.at(-1);
  const flow=draft ? draftWorkflow(draft,snapshot.reviews,snapshot.runs,snapshot.reviewCapabilities) : null;
  const submission=flow?.submission;
  const author=snapshot.capabilities.job_descriptions;
  const create=(kind)=>onNavigate({section:"create-record",kind});
  const open=(kind,record)=>onNavigate({section:"record",kind,id:record.id,revision:record.revision});
  const ai=snapshot.agents.find(item=>item.id==="hr_jd_draft"&&item.canExecute);
  const validation=snapshot.agents.find(item=>item.id==="hr_draft_validation"&&item.canExecute);
  return <section className="hr-journey" aria-label="Five-step hiring guide">
    <h2>From hiring need to an approved job description</h2><p>Follow the saved work below. AI can help with a proposal, but only authorized humans can review and approve it.</p>
    {!!requirements.length&&<label>Continue a saved hiring requirement<select aria-label="Continue a saved hiring requirement" value={requirement?.id ?? ""} onChange={e=>setRequirementId(e.target.value)}>{requirements.map(item=><option key={item.id} value={item.id}>{item.content.title} · {item.content.status}</option>)}</select></label>}
    <ol className="hr-step-list">
      <li><h3>1. Define the hiring requirement</h3><p>Describe the role, why it is needed and the work it involves. For example: a Software Engineer to build internal services.</p>
        {requirement ? <><p className="step-saved">Saved: {requirement.content.title}</p><Button variant="primary" onClick={()=>open("requirements",requirement)}>Open requirement</Button></> : <Button variant="primary" disabled={!snapshot.capabilities.requirements} onClick={()=>create("requirements")}>Define a requirement</Button>}
        <p className="muted">Recruiters can create and edit requirements. Reviewers and Approvers can read them.</p>
        {requirement&&snapshot.capabilities.requirements&&<Button onClick={()=>create("requirements")}>Start another requirement</Button>}</li>
      <li><h3>2. Create the job description</h3><p>Write a draft from the saved requirement, or request an AI proposal and deliberately apply the suggestions yourself.</p>
        {draft ? <><p className="step-saved">Saved: {draft.content.title} · {flow.status}</p><Button variant="primary" onClick={()=>open("job-descriptions",draft)}>Open saved job description</Button></> : <Button variant="primary" disabled={!requirement||!author||["closed","archived"].includes(requirement?.content.status)} onClick={()=>onNavigate({section:"create-draft",id:requirement.id,revision:requirement.revision})}>Write job description</Button>}
        {requirement&&ai&&<Button onClick={()=>onNavigate({section:"assistance",action:"hr_jd_draft",requirement})}>Prepare AI proposal</Button>}
        <p className="muted">A Recruiter saves the draft. AI generation uses the configured provider only after you explicitly start it.</p></li>
      <li><h3>3. Review suggestions and role knowledge</h3><p>Check organizational facts, skills and any AI suggestions against the linked sources. Role knowledge is optional; it is never inferred from a title.</p>
        <Button variant="primary" disabled={!draft} onClick={()=>onNavigate({section:"assistance",...(validation ? {action:"hr_draft_validation",draft} : {})})}>{validation ? "Check saved draft with AI" : "Review AI suggestions"}</Button>
        {draft&&<p className="step-saved">{flow.evidence.length} completed AI runs match this description's exact sources. AI is optional and does not approve the draft.</p>}
        {draft?.content.roleKnowledge&&<Button onClick={()=>onNavigate({section:"record",kind:"role-knowledge",...draft.content.roleKnowledge})}>Open linked role knowledge</Button>}
        {snapshot.capabilities.role_knowledge&&<Button onClick={()=>create("role-knowledge")}>Add role knowledge</Button>}
        <p className="muted">Recruiters manage sources. Draft validation requires Reviewer or Approver responsibility.</p></li>
      <li><h3>4. Submit for human review</h3><p>Submit the saved description. Reviewers see that exact version and its sources. Later edits need a new submission.</p>
        {submission&&<p className="step-saved">Saved submission: {flow.status}{submission.stale ? " · a new version needs its own review" : ""}.</p>}
        <Button variant="primary" disabled={!draft || (!submission && (!snapshot.reviewCapabilities.submit || draft.content.status !== "draft"))} onClick={()=>onNavigate({section:"reviews",...(submission ? {submissionId:submission.id} : {draftId:draft.id})})}>{submission ? "Open saved review request" : "Submit saved description"}</Button>
        <p className="muted">Only Recruiters submit. Saving a draft alone does not request approval.</p></li>
      <li><h3>5. Record a human decision</h3><p>A Reviewer recommends the submitted description or requests changes. An Approver then approves or rejects it. Final changes require the appropriate combined responsibilities.</p>
        <Button variant="primary" disabled={!submission} onClick={()=>onNavigate({section:"reviews",submissionId:submission.id})}>{submission?.status === "approved" ? "View approval and history" : submission?.status === "reviewed" ? "Open approval decision" : "Open review and decisions"}</Button>
        {submission&&<p className="step-saved">Current saved outcome: {flow.status}. {flow.next?.section === "record" && "A Recruiter must save a revised description and submit it again."}</p>}
        <p className="muted">Owner/Admin access does not grant any HR responsibility. Earlier approvals never transfer to a changed description.</p></li>
    </ol>
    {!author&&<p role="status">Your HR access is read-only for drafting. The enabled review actions depend on your assigned Reviewer/Approver responsibilities.</p>}
  </section>;
}
