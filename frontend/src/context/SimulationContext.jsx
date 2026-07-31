/**
 * context/SimulationContext.jsx
 *
 * Single source of truth for simulation data across the whole app.
 * Wraps useSimulationData() so any page/component can read agents,
 * tasks, messages, etc. without prop-drilling through AppShell.
 *
 * Usage:
 *   const { agents, tasks, selectedTaskId, selectTask } = useSimulation();
 */

import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { useSimulationData } from "../hooks/useSimulationData";

const SimulationContext = createContext(null);

export function SimulationProvider({ children }) {
  const data = useSimulationData();

  // UI-only state that isn't part of the data contract — which task is
  // currently shown in the Task Details panel, etc.
  const [selectedTaskId, setSelectedTaskId] = useState(null);

  // Real data arrives asynchronously (fetch resolves after connection
  // is established) — auto-select the first task once tasks actually
  // exist, instead of only checking on the very first render.
  useEffect(() => {
  if (data.tasks.length === 0) {
    setSelectedTaskId(null);
    return;
  }

  const latestTask = data.tasks[data.tasks.length - 1];

  if (latestTask.id !== selectedTaskId) {
    setSelectedTaskId(latestTask.id);
  }
}, [data.tasks]);

  const value = useMemo(
    () => ({
      ...data,
      selectedTaskId,
      selectTask: setSelectedTaskId,
      selectedTask: data.tasks?.find((t) => t.id === selectedTaskId) ?? null,
    }),
    [data, selectedTaskId]
  );

  return (
    <SimulationContext.Provider value={value}>
      {children}
    </SimulationContext.Provider>
  );
}

export function useSimulation() {
  const ctx = useContext(SimulationContext);
  if (!ctx) {
    throw new Error("useSimulation() must be used inside <SimulationProvider>");
  }
  return ctx;
}
