import { Activity, ClipboardList, Users, MessageSquare, ScrollText, RotateCcw, Settings, Bot, LogOut, Building2 } from "lucide-react";
import SimulationInfoPanel from "../components/dashboard/SimulationInfoPanel";
import WorkspaceSwitcher from "./WorkspaceSwitcher";
import "./Sidebar.css";

const NAV_ITEMS = [
  { id: "live", label: "Live Simulation", icon: Activity },
  { id: "task-summary", label: "Simulation History", icon: ClipboardList },
  { id: "agents", label: "Agents", icon: Users },
  { id: "messages", label: "Messages", icon: MessageSquare },
  { id: "logs", label: "Logs", icon: ScrollText },
  { id: "replay", label: "Event History", icon: RotateCcw },
  { id: "organizations", label: "Organizations", icon: Building2 },
  { id: "settings", label: "Settings", icon: Settings },
];

/**
 * Sidebar
 * Left navigation rail + user account footer.
 *
 * Props:
 *  - activePage: string — id of the currently active nav item
 *  - onNavigate: (id: string) => void
 *  - user: { name: string, role: string, avatarUrl?: string }
 *  - stats: SimulationStats | undefined — if provided, renders the
 *    "Simulation Info" block above the user footer (see reference image)
 */
export default function Sidebar({ activePage = "live", onNavigate = () => {}, user, workspace, stats }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="sidebar-brand-icon">
          <Bot size={20} strokeWidth={2} />
        </div>
        <div className="sidebar-brand-text">
          <span className="sidebar-brand-title">Multi-Agent AI</span>
          <span className="sidebar-brand-subtitle">Environment Simulator</span>
        </div>
      </div>

      <WorkspaceSwitcher
        workspaces={workspace?.workspaces}
        activeWorkspace={workspace?.activeWorkspace}
        status={workspace?.status}
        error={workspace?.error}
        onSelect={workspace?.selectWorkspace}
      />

      <nav className="sidebar-nav" aria-label="Main navigation">
        {NAV_ITEMS.map(({ id, label, icon: Icon }) => {
          const isActive = id === activePage;
          return (
            <button
              key={id}
              type="button"
              className={`sidebar-nav-item${isActive ? " is-active" : ""}`}
              aria-current={isActive ? "page" : undefined}
              title={label}
              onClick={() => onNavigate(id)}
            >
              <Icon size={17} strokeWidth={2} />
              <span>{label}</span>
            </button>
          );
        })}
      </nav>

      {stats && <SimulationInfoPanel stats={stats} />}

      <div className="sidebar-footer">
        <div className="sidebar-user">
          <div
            className="sidebar-user-avatar"
            aria-hidden="true"
          >
            {user?.avatarUrl ? (
              <img
                src={user.avatarUrl}
                alt=""
              />
            ) : (
              <span>
                {(user?.name ?? "?").charAt(0)}
              </span>
            )}
          </div>

          <div className="sidebar-user-info">
            <span className="sidebar-user-name">
              {user?.name ?? "Guest"}
            </span>
            <span className="sidebar-user-role">
              {user?.role ?? "Viewer"}
            </span>
          </div>
        </div>

        {user?.onLogout && (
          <button
            type="button"
            className="sidebar-logout"
            onClick={user.onLogout}
          >
            <LogOut
              size={15}
              strokeWidth={2}
            />
            <span>Sign out</span>
          </button>
        )}

        <div className="sidebar-legal-links">
          <a href="/privacy">Privacy</a>
          <span aria-hidden="true">·</span>
          <a href="/terms">Terms</a>
        </div>
      </div>
    </aside>
  );
}
