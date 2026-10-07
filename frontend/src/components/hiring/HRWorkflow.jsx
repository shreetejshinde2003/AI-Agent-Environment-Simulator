import Button from "../common/Button";
import Card from "../common/Card";
import {draftWorkflow, relatedDrafts, relatedRuns} from "../../utils/hrWorkflow";
import {reviewLabels} from "../../utils/hrReviews";

export default function HRWorkflow({snapshot, record, kind, linkedDrafts, onNavigate}) {
  if (!snapshot) return null;
  const {records, reviews, runs, reviewCapabilities, capabilities} = snapshot;
  const drafts = record ? linkedDrafts !== undefined && kind !== "job-descriptions" ? linkedDrafts ?? [] : relatedDrafts(kind, record, records["job-descriptions"] ?? []) : records["job-descriptions"] ?? [];
  const sourceButton = (sourceKind, ref, label) => ref && <Button onClick={() => onNavigate({section:"record",kind:sourceKind,...ref})}>{label} · revision {ref.revision}</Button>;
  const runButton = run => <li key={run.id}><Button onClick={() => onNavigate({section:"assistance",runId:run.id})}>{run.assignedAgentId} · {run.status} · {run.id}</Button>
    <small>AI-generated evidence · {run.hrExecution.sources.map(source => `${source.kind} revision ${source.revision}`).join(" · ")}</small></li>;
  const sourceHead = record && records[kind]?.find(item => item.id === record.id);
  const content = <>
    {!record && <><p>Status comes from saved revisions and human submission history. AI proposals never change an authoritative JD.</p>
      <ul className="hiring-records">{(records.requirements ?? []).map(requirement => <li key={requirement.id}>
        <Button onClick={() => onNavigate({section:"record",kind:"requirements",id:requirement.id,revision:requirement.revision})}>{requirement.content.title}<small>Requirement {requirement.content.status} · revision {requirement.revision} · {(records["job-descriptions"] ?? []).filter(jd => jd.content.requirement.id === requirement.id).length} linked JDs</small></Button>
      </li>)}</ul>
      {!records.requirements?.length && <p>Create a hiring requirement in Source records and drafts to begin.</p>}
    </>}
    {record && kind === "requirements" && capabilities.job_descriptions && !["closed","archived"].includes(sourceHead?.content.status ?? record.content.status) && <Button onClick={() => onNavigate({section:"create-draft",id:record.id,revision:record.revision})}>Create human JD from requirement revision {record.revision}</Button>}
    {record && kind === "requirements" && <div className="hiring-tabs">{snapshot.agents.filter(agent => agent.canExecute && agent.id !== "hr_draft_validation").map(agent => <Button key={agent.id} onClick={() => onNavigate({section:"assistance",action:agent.id,requirement:record})}>{agent.title}</Button>)}</div>}
    {record && kind === "requirements" && <p>Role knowledge is explicitly linked through saved JD sources or AI runs. No role association is inferred from titles.</p>}
    {record && kind !== "job-descriptions" && <h3>JDs using this exact source revision</h3>}
    {drafts.map(draft => {
      const flow = draftWorkflow(draft, reviews, runs, reviewCapabilities, records["job-descriptions"]?.find(item => item.id === draft.id)?.revision);
      return <article className="hr-workflow-row" key={`${draft.id}@${draft.revision}`}>
        <h3>{draft.content.title} · revision {draft.revision}</h3><p role="status">{flow.status}</p>
        <div className="hiring-tabs">{sourceButton("job-descriptions",{id:draft.id,revision:draft.revision},"Inspect JD")}
          {sourceButton("requirements",draft.content.requirement,"Source requirement")}
          {sourceButton("role-knowledge",draft.content.roleKnowledge,"Source role knowledge")}</div>
        <p>Human editor: {draft.updatedByUserId} · {new Date(draft.updatedAt).toLocaleString()}</p>
        {!!flow.priorApprovals.length && <p>Earlier approval applies only to revision {flow.priorApprovals.map(item => item.jobDescription.revision).join(", ")}. This revision has its own review status.</p>}
        {flow.next ? <Button variant="primary" onClick={() => onNavigate({...flow.next,id:draft.id})}>Next action: {flow.next.label}</Button> : <p className="muted">{flow.status === "Approved" ? "Approved revision retained with its decision history." : "No decision or authoring action is currently available for your HR permissions."}</p>}
        <div className="hiring-tabs">{snapshot.agents.filter(agent => agent.canExecute).map(agent => <Button key={agent.id} onClick={() => onNavigate({section:"assistance",action:agent.id,draft})}>{agent.title}</Button>)}</div>
        <details><summary>AI evidence ({flow.evidence.length}) · proposals only</summary><ul className="hiring-records">{flow.evidence.map(runButton)}</ul>{!flow.evidence.length && <p>No completed AI run matches these exact sources.</p>}</details>
        <details><summary>Submission and decision history ({flow.history.length})</summary><ul className="hiring-records">{flow.history.map(item => <li key={item.id}><Button onClick={() => onNavigate({section:"reviews",submissionId:item.id})}>{reviewLabels[item.status]} · JD revision {item.jobDescription.revision}{item.stale ? " · historical" : ""}</Button><small>Submitted by {item.requestedByUserId} · {new Date(item.submittedAt).toLocaleString()}</small></li>)}</ul></details>
      </article>;
    })}
    {record && kind !== "job-descriptions" && linkedDrafts === null ? <p role="status">Loading linked JD revisions…</p> : !drafts.length && <p>No linked job descriptions yet.</p>}
    {record && <><h3>Related AI run history</h3><p>Includes failed and historical runs. Matching source revisions establish relevance, not adoption.</p><ul className="hiring-records">{relatedRuns(kind, record, runs).map(runButton)}</ul></>}
  </>;
  return record ? <section aria-label="Record relationships and workflow">{content}</section> : <Card title="Hiring workflow">{content}</Card>;
}
