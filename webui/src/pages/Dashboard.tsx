import { api, Status } from "../api";
import { usePoll, formatTime } from "../hooks";

function NowPlaying({ status }: { status: Status }) {
  if (!status.tracking) {
    return (
      <div className="card nowplaying idle">
        <div className="np-state">Nothing playing</div>
        <p className="muted">
          {status.monitor_running
            ? "Monitoring is active — start a video in a supported player."
            : "Monitoring is not running."}
        </p>
      </div>
    );
  }

  const pct = Math.max(0, Math.min(100, status.progress_percent ?? 0));
  const se =
    status.season != null || status.episode != null
      ? ` · S${String(status.season ?? 0).padStart(2, "0")}E${String(status.episode ?? 0).padStart(2, "0")}`
      : "";

  return (
    <div className="card nowplaying">
      <div className="np-head">
        <span className={`badge state-${(status.state || "").toLowerCase()}`}>
          {status.state || "Playing"}
        </span>
        <span className="muted">{status.media_type}</span>
        {status.is_rewatch && <span className="badge rewatch">Rewatch</span>}
      </div>
      <h2 className="np-title">
        {status.title || status.raw_title}
        <span className="muted">{se}</span>
      </h2>
      <div className="progress">
        <div className="progress-fill" style={{ width: `${pct}%` }} />
      </div>
      <div className="np-meta">
        <span>{formatTime(status.position_seconds)} / {formatTime(status.duration_seconds)}</span>
        <span>{pct.toFixed(0)}%{status.completed ? " · scrobbled" : ""}</span>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const { data: status } = usePoll(api.status, 2000);
  const { data: stats } = usePoll(api.stats, 10000);

  return (
    <div className="stack">
      {status ? <NowPlaying status={status} /> : <div className="card">Loading…</div>}

      <div className="stat-grid">
        <div className="card stat">
          <div className="stat-num">{stats?.total ?? "–"}</div>
          <div className="stat-label">Total watched</div>
        </div>
        <div className="card stat">
          <div className="stat-num">{stats?.movie ?? "–"}</div>
          <div className="stat-label">Movies</div>
        </div>
        <div className="card stat">
          <div className="stat-num">{stats?.show ?? "–"}</div>
          <div className="stat-label">Shows</div>
        </div>
        <div className="card stat">
          <div className="stat-num">{stats?.anime ?? "–"}</div>
          <div className="stat-label">Anime</div>
        </div>
      </div>
    </div>
  );
}
