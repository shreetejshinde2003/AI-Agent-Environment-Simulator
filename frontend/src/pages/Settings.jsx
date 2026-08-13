import { useEffect, useState } from "react";
import { useSimulation } from "../context/SimulationContext";
import Card from "../components/common/Card";
import "./Settings.css";

/**
 * Settings — app-level configuration: API base URL, live-updates
 * (WebSocket) toggle, theme, and account info. Persisted to
 * localStorage so it survives a refresh; nothing here talks to a
 * backend endpoint (there isn't a settings API yet).
 */

const STORAGE_KEY = "orchestra.settings";

// ONE-LINE TODO: confirm VITE_API_BASE_URL is the env var your Vite
// config actually uses (it's already referenced as the demo-mode
// pattern in LiveSimulation.jsx via VITE_DEMO_MODE).
const DEFAULT_SETTINGS = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL || "http://localhost:8000",
  liveUpdatesEnabled: true,
  theme: "dark",
};

function loadSettings() {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_SETTINGS;
    return { ...DEFAULT_SETTINGS, ...JSON.parse(raw) };
  } catch {
    return DEFAULT_SETTINGS;
  }
}

export default function Settings() {
  const simulation = useSimulation();
  // ONE-LINE TODO: once auth exists, replace this with the real user
  // object from context, e.g. `simulation.user`.
  const user = simulation?.user ?? simulation?.currentUser ?? null;

  const [settings, setSettings] = useState(loadSettings);
  const [savedMessage, setSavedMessage] = useState("");

  useEffect(() => {
    // Light theme CSS doesn't exist yet — this just sets the attribute
    // so it's ready to style whenever it does.
    document.documentElement.setAttribute("data-theme", settings.theme);
  }, [settings.theme]);

  const updateField = (field, value) => {
    setSettings((prev) => ({ ...prev, [field]: value }));
    setSavedMessage("");
  };

  const handleSave = () => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
    setSavedMessage("Saved ✓");
    setTimeout(() => setSavedMessage(""), 2000);
  };

  const handleReset = () => {
    setSettings(DEFAULT_SETTINGS);
    window.localStorage.removeItem(STORAGE_KEY);
    setSavedMessage("Reset to defaults");
    setTimeout(() => setSavedMessage(""), 2000);
  };

  return (
    <div className="settings-page">
      <Card title="Connection">
        <div className="settings-field">
          <label className="settings-label" htmlFor="apiBaseUrl">
            API Base URL
          </label>
          <input
            id="apiBaseUrl"
            type="text"
            className="settings-input"
            value={settings.apiBaseUrl}
            onChange={(e) => updateField("apiBaseUrl", e.target.value)}
            placeholder="http://localhost:8000"
          />
          <p className="settings-hint">
            Overrides <code>VITE_API_BASE_URL</code> for this browser only.
          </p>
        </div>

        <div className="settings-field settings-field-row">
          <div>
            <label className="settings-label" htmlFor="liveUpdates">
              Live updates (WebSocket)
            </label>
            <p className="settings-hint">
              Turn off to stop the dashboard from opening a WebSocket connection.
            </p>
          </div>
          <input
            id="liveUpdates"
            type="checkbox"
            className="settings-toggle"
            checked={settings.liveUpdatesEnabled}
            onChange={(e) => updateField("liveUpdatesEnabled", e.target.checked)}
          />
        </div>
      </Card>

      <Card title="Appearance">
        <div className="settings-field">
          <label className="settings-label" htmlFor="theme">
            Theme
          </label>
          <select
            id="theme"
            className="settings-input"
            value={settings.theme}
            onChange={(e) => updateField("theme", e.target.value)}
          >
            <option value="dark">Dark</option>
            <option value="light">Light (experimental)</option>
          </select>
          <p className="settings-hint">
            Light theme CSS isn't built yet — this just sets <code>data-theme</code> on{" "}
            <code>&lt;html&gt;</code> for when it is.
          </p>
        </div>
      </Card>

      <Card title="Account">
        {user ? (
          <div className="settings-field">
            <span className="settings-label">Signed in as</span>
            <p className="settings-account-name">{user.name ?? user.email ?? "Unknown user"}</p>
          </div>
        ) : (
          <p className="settings-hint">No account system wired up yet.</p>
        )}
      </Card>

      <div className="settings-actions">
        <button type="button" className="settings-btn settings-btn-primary" onClick={handleSave}>
          Save Settings
        </button>
        <button type="button" className="settings-btn" onClick={handleReset}>
          Reset to Defaults
        </button>
        {savedMessage && <span className="settings-saved-message">{savedMessage}</span>}
      </div>
    </div>
  );
}
