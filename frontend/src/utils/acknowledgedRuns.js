// A list request may have started before creation was acknowledged. Resolve only
// locally acknowledged omissions through the existing tenant-scoped detail API.
export async function resolveAcknowledgedRuns(tasks, acknowledgedIds, getTask) {
  const listed = new Set(tasks.map(task => task.id));
  const missing = acknowledgedIds.filter(id => !listed.has(id));
  const resolved = await Promise.all(missing.map(async id => {
    try {return await getTask(id);} catch (error) {
      if (error.status === 404) return null;
      throw error; // Unavailable evidence is not proof of removal.
    }
  }));
  return [...tasks, ...resolved.filter(Boolean)];
}
