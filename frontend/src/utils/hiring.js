export const hiringKinds = [
  {key: "requirements", label: "Hiring requirements", fields: ["title", "department", "purpose", "responsibilities", "requiredSkills", "preferredSkills", "experience", "qualifications", "location", "employmentArrangement", "openings", "constraints"]},
  {key: "role-knowledge", label: "Role knowledge", fields: ["title", "responsibilities", "requiredSkills", "preferredSkills", "experience", "qualifications", "competencies", "terminology", "evaluationCriteria"]},
  {key: "job-descriptions", label: "Job descriptions", fields: ["title", "summary", "responsibilities", "requiredSkills", "preferredSkills", "experience", "qualifications"]},
];
export const listFields = new Set(["responsibilities", "requiredSkills", "preferredSkills", "constraints", "competencies", "terminology", "evaluationCriteria"]);
export const hiringLabels = {status: "Lifecycle status", requirement: "Source hiring requirement", roleKnowledge: "Source role knowledge", title: "Position title", department: "Department / team", purpose: "Hiring purpose", responsibilities: "Responsibilities", requiredSkills: "Required skills", preferredSkills: "Preferred skills", experience: "Experience expectations", qualifications: "Qualifications", location: "Location", employmentArrangement: "Employment arrangement", openings: "Number of openings", constraints: "Constraints", competencies: "Competencies", terminology: "Organization terminology", evaluationCriteria: "Evaluation criteria", summary: "Summary"};
export function hiringForm(kind, content) {
  const definition = hiringKinds.find(item => item.key === kind);
  const values = Object.fromEntries(definition.fields.map(field => [field,
    listFields.has(field) ? (content?.[field] ?? []).join("\n") : content?.[field] ?? (field === "openings" ? "1" : "")]));
  return {...values, status: content?.status ?? (kind === "role-knowledge" ? "active" : "draft"),
    requirement: content?.requirement ? `${content.requirement.id}@${content.requirement.revision}` : "",
    roleKnowledge: content?.roleKnowledge ? `${content.roleKnowledge.id}@${content.roleKnowledge.revision}` : ""};
}
function source(value) {
  const [id, revision] = value.split("@");
  if (!id || !Number.isInteger(Number(revision)) || Number(revision) < 1) throw new Error("Choose a source revision.");
  return {id, revision: Number(revision)};
}
export function hiringPayload(kind, form, expectedRevision) {
  const fields = hiringKinds.find(item => item.key === kind).fields;
  const payload = Object.fromEntries(fields.map(field => [field,
    listFields.has(field) ? String(form[field]).split("\n").map(line => line.trim()).filter(Boolean)
      : field === "openings" ? Number(form[field]) : String(form[field]).trim()]));
  if (!payload.title || (kind === "requirements" && !payload.purpose) || (kind === "job-descriptions" && !payload.summary)) throw new Error("Complete the required fields.");
  if (kind === "requirements" && (!Number.isInteger(payload.openings) || payload.openings < 1 || payload.openings > 10000)) throw new Error("Openings must be a whole number between 1 and 10000.");
  for (const field of fields) {
    const value = payload[field];
    if (listFields.has(field)) {
      if (value.length > 80 || value.some(item => item.length > 4000)) throw new Error(`${hiringLabels[field]} allows up to 80 items of 4000 characters each.`);
    } else if (typeof value === "string") {
      const limit = ["title", "department", "location", "employmentArrangement"].includes(field) ? 200 : field === "summary" ? 8000 : 4000;
      if (value.length > limit) throw new Error(`${hiringLabels[field]} exceeds ${limit} characters.`);
    }
  }
  payload.status = form.status;
  if (kind === "job-descriptions") {
    payload.requirement = source(form.requirement);
    payload.roleKnowledge = form.roleKnowledge ? source(form.roleKnowledge) : null;
  }
  if (expectedRevision) payload.expectedRevision = expectedRevision;
  return payload;
}
export function hiringStatuses(kind, current) {
  if (current === "archived") return ["archived"];
  if (kind === "requirements") return current === "active" ? ["active", "closed", "archived"] : current === "closed" ? ["closed", "archived"] : ["draft", "active", "archived"];
  return kind === "role-knowledge" ? ["active", "archived"] : ["draft", "archived"];
}
