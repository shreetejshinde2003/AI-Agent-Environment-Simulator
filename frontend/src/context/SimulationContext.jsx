import { createContext, useContext, useEffect, useState } from "react";
import { useSimulationData } from "../hooks/useSimulationData";
import {useWorkspace} from "../hooks/useWorkspace";
import { newestRuns } from "../utils/runs";
const SimulationContext = createContext(null);
function savedRun(workspaceId) {
  try {return workspaceId ? localStorage.getItem(`simulation-id:${workspaceId}`) : null;} catch {return null;}
}
export function SimulationProvider({ children }) {
  const data = useSimulationData();
  const {activeWorkspaceId} = useWorkspace();
  const [executionView, setExecutionView] = useState("output");
  useEffect(() => {selectTask(savedRun(activeWorkspaceId));setExecutionView("output");}, [activeWorkspaceId]);
  const [activePage, setActivePage] = useState("live");
  const [selectedTaskId, selectTask] = useState(null);
  useEffect(() => {
    if (data.tasks.length && !data.tasks.some(t => t.id === selectedTaskId))
      selectTask(newestRuns(data.tasks)[0].id);
  }, [data.tasks, selectedTaskId]);
  useEffect(() => {
    if (selectedTaskId && data.tasks.some(task => task.id === selectedTaskId)) {
      try {localStorage.setItem(`simulation-id:${activeWorkspaceId}`, selectedTaskId);} catch { /* Optional convenience. */ }
    }
  }, [selectedTaskId, activeWorkspaceId, data.tasks]);
  const selectedTask = data.tasks.find(t => t.id === selectedTaskId) ?? null;
  function openCreatedRun(run) {
    if (!data.acceptRun(run)) return;
    selectTask(run.id);
    setExecutionView("output");
    setActivePage("live");
    data.refresh();
  }
  return <SimulationContext.Provider value={{...data, selectedTaskId, selectTask: id => {selectTask(id);setExecutionView("output");}, selectedTask,
    activePage, setActivePage, executionView, setExecutionView, openCreatedRun,
    messages: selectedTask?.messages ?? [], activity: selectedTask?.activities ?? [],
    timeline: selectedTask?.events ?? []}}>{children}</SimulationContext.Provider>;
}
export function useSimulation() {
  const context = useContext(SimulationContext);
  if (!context) throw new Error("SimulationProvider required");
  return context;
}
