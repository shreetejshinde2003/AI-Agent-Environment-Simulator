import { createContext, useContext, useEffect, useState } from "react";
import { useSimulationData } from "../hooks/useSimulationData";
const SimulationContext = createContext(null);
export function SimulationProvider({ children }) {
  const data = useSimulationData();
  const [selectedTaskId, selectTask] = useState(() => localStorage.getItem("simulation-id"));
  useEffect(() => {
    if (data.tasks.length && !data.tasks.some(t => t.id === selectedTaskId))
      selectTask(data.tasks.at(-1).id);
  }, [data.tasks, selectedTaskId]);
  useEffect(() => {
    if (selectedTaskId) localStorage.setItem("simulation-id", selectedTaskId);
  }, [selectedTaskId]);
  const selectedTask = data.tasks.find(t => t.id === selectedTaskId) ?? null;
  return <SimulationContext.Provider value={{...data, selectedTaskId, selectTask, selectedTask,
    messages: selectedTask?.messages ?? [], activity: selectedTask?.activities ?? [],
    timeline: selectedTask?.events ?? []}}>{children}</SimulationContext.Provider>;
}
export function useSimulation() {
  const context = useContext(SimulationContext);
  if (!context) throw new Error("SimulationProvider required");
  return context;
}
