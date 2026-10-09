import { useEffect, useRef, useState } from "react";
import Sidebar from "./Sidebar";
import Topbar from "./Topbar";
import { useSimulation } from "../context/SimulationContext";
import "./AppShell.css";

/**
 * AppShell
 * Top-level layout: Sidebar (left) + Topbar (top) + page content (right).
 * This is the only place that should know about "pages" — individual page
 * components stay dumb and just receive whatever data they need as props.
 *
 * Props:
 *  - activePage / onNavigate: forwarded to Sidebar
 *  - topbarProps: forwarded to Topbar (goal, playback state, etc.)
 *  - user: forwarded to Sidebar footer
 *  - children: the active page's content
 */
export default function AppShell({
  activePage,
  onNavigate,
  topbarProps = {},
  user,
  workspace,
  children,
}) {
  // AppShell is the one place allowed to reach into context directly —
  // it's the layout root, so this is where "global" data (like sim
  // stats needed by the Sidebar's info panel) gets pulled in and handed
  // down as plain props. Individual layout pieces stay context-free.
  const contentRef=useRef(null);
  useEffect(()=>{const content=contentRef.current;if(content){content.scrollTop=0;content.focus({preventScroll:true});}},[activePage,workspace?.activeWorkspaceId]);
  const { stats, backendStatus, workspaceStatus, socketStatus, isLoading, error, isRefreshing, lastRefreshedAt, refresh } = useSimulation();

  return (
    <div className="app-shell">
      <Sidebar
        activePage={activePage}
        onNavigate={onNavigate}
        user={user}
        workspace={workspace}
        stats={stats}
      />
      <div className="app-shell-main">
        <Topbar {...topbarProps} dataStatus={error ? "error" : isLoading ? "loading" : "ready"} backendStatus={backendStatus} workspaceStatus={workspaceStatus} socketStatus={socketStatus} isRefreshing={isRefreshing} lastRefreshedAt={lastRefreshedAt} onRefresh={refresh} authError={error?.status === 401} />
        <main ref={contentRef} className="app-shell-content" tabIndex={-1}>{children}</main>
      </div>
    </div>
  );
}

/**
 * Convenience hook so pages can be swapped without lifting state into App.jsx
 * yet. Once SimulationContext exists, this can be replaced/extended.
 */
export function useActivePage(initial = "live") {
  const [activePage, setActivePage] = useState(initial);
  return [activePage, setActivePage];
}
