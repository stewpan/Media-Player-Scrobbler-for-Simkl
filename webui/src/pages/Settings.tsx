import { useEffect, useState } from "react";
import { api, AuthStatus, Settings as SettingsT } from "../api";
import { usePoll } from "../hooks";

function AuthPanel() {
  const { data: auth } = usePoll(api.authStatus, 3000);
  const [starting, setStarting] = useState(false);

  const start = async () => {
    setStarting(true);
    try {
      await api.authStart();
    } catch {
      /* status poll surfaces errors */
    } finally {
      setStarting(false);
    }
  };

  const a: AuthStatus | null = auth;
  return (
    <div className="card">
      <h3>Simkl account</h3>
      {a?.authenticated ? (
        <p className="ok">Connected{a.user_id ? ` (user ${a.user_id})` : ""}.</p>
      ) : a?.in_progress ? (
        <div>
          <p>Enter this code at <a href={a.pin_url || a.verification_url || "#"} target="_blank" rel="noreferrer">{a.verification_url || "simkl.com/pin"}</a>:</p>
          <div className="pin-code">{a.user_code}</div>
          <p className="muted">Waiting for authorization…</p>
        </div>
      ) : (
        <div>
          <p className="muted">Not connected.</p>
          {a?.error && <p className="err">Last attempt: {a.error}</p>}
          <button className="btn" onClick={start} disabled={starting}>
            {starting ? "Starting…" : "Connect to Simkl"}
          </button>
        </div>
      )}
    </div>
  );
}

export default function Settings() {
  const [settings, setSettings] = useState<SettingsT | null>(null);
  const [saved, setSaved] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getSettings().then(setSettings).catch((e) => setError(e.message));
  }, []);

  const save = async (patch: Partial<SettingsT>) => {
    try {
      await api.updateSettings(patch);
      setSettings((s) => (s ? { ...s, ...patch } : s));
      setSaved("Saved");
      setError(null);
      setTimeout(() => setSaved(null), 1500);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  if (error && !settings) return <div className="card err">Failed to load settings: {error}</div>;
  if (!settings) return <div className="card">Loading…</div>;

  return (
    <div className="stack">
      <AuthPanel />

      <div className="card">
        <h3>Scrobbling</h3>
        <label className="field">
          <span>Completion threshold: <strong>{settings.watch_completion_threshold}%</strong></span>
          <input
            type="range"
            min={1}
            max={100}
            value={settings.watch_completion_threshold}
            onChange={(e) => setSettings({ ...settings, watch_completion_threshold: Number(e.target.value) })}
            onMouseUp={(e) => save({ watch_completion_threshold: Number((e.target as HTMLInputElement).value) })}
          />
        </label>

        <label className="field row">
          <input
            type="checkbox"
            checked={settings.disable_notifications}
            onChange={(e) => save({ disable_notifications: e.target.checked })}
          />
          <span>Disable notifications</span>
        </label>

        <label className="field row">
          <input
            type="checkbox"
            checked={settings.skip_rewatch_scrobble}
            onChange={(e) => save({ skip_rewatch_scrobble: e.target.checked })}
          />
          <span>Skip re-scrobbling rewatches (don't count again on Simkl)</span>
        </label>

        <label className="field">
          <span>Auto-sync interval (seconds)</span>
          <input
            className="input"
            type="number"
            min={0}
            value={settings.auto_sync_interval}
            onChange={(e) => setSettings({ ...settings, auto_sync_interval: Number(e.target.value) })}
            onBlur={(e) => save({ auto_sync_interval: Number(e.target.value) })}
          />
        </label>
      </div>

      <div className="card">
        <h3>Directory filters</h3>
        <DirList
          label="Allow list (only scrobble inside these)"
          value={settings.allow_dirs}
          onSave={(dirs) => save({ allow_dirs: dirs })}
        />
        <DirList
          label="Deny list (never scrobble inside these)"
          value={settings.deny_dirs}
          onSave={(dirs) => save({ deny_dirs: dirs })}
        />
      </div>

      {saved && <div className="toast">{saved}</div>}
      {error && settings && <div className="toast err">{error}</div>}
    </div>
  );
}

function DirList({ label, value, onSave }: { label: string; value: string[]; onSave: (v: string[]) => void }) {
  const [text, setText] = useState(value.join("\n"));
  useEffect(() => setText(value.join("\n")), [value]);
  return (
    <label className="field">
      <span>{label}</span>
      <textarea
        className="input"
        rows={3}
        value={text}
        placeholder="One path per line"
        onChange={(e) => setText(e.target.value)}
        onBlur={() => onSave(text.split("\n").map((s) => s.trim()).filter(Boolean))}
      />
    </label>
  );
}
