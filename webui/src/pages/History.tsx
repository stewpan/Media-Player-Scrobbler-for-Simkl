import { useMemo, useState } from "react";
import { api } from "../api";
import { usePoll } from "../hooks";

const TYPES = ["all", "movie", "show", "anime"];

function normType(t?: string): string {
  const v = (t || "movie").toLowerCase();
  if (v === "tv" || v === "show") return "show";
  if (v === "anime") return "anime";
  return "movie";
}

export default function History() {
  const { data } = usePoll(api.history, 15000);
  const [query, setQuery] = useState("");
  const [type, setType] = useState("all");

  const rows = useMemo(() => {
    const entries = data?.entries ?? [];
    return entries.filter((e) => {
      if (type !== "all" && normType(e.type) !== type) return false;
      if (query && !(e.title || "").toLowerCase().includes(query.toLowerCase())) return false;
      return true;
    });
  }, [data, query, type]);

  return (
    <div className="stack">
      <div className="toolbar">
        <input
          className="input"
          placeholder="Search title…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <div className="segmented">
          {TYPES.map((t) => (
            <button
              key={t}
              className={type === t ? "active" : ""}
              onClick={() => setType(t)}
            >
              {t}
            </button>
          ))}
        </div>
        <span className="muted">{rows.length} of {data?.total ?? 0}</span>
      </div>

      <div className="card">
        <table className="table">
          <thead>
            <tr>
              <th>Title</th>
              <th>Type</th>
              <th>S/E</th>
              <th>Watched</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((e, i) => (
              <tr key={`${e.simkl_id ?? i}-${i}`}>
                <td>{e.title || "—"}{e.year ? ` (${e.year})` : ""}</td>
                <td><span className={`pill pill-${normType(e.type)}`}>{normType(e.type)}</span></td>
                <td>
                  {e.season != null || e.episode != null
                    ? `S${String(e.season ?? 0).padStart(2, "0")}E${String(e.episode ?? 0).padStart(2, "0")}`
                    : "—"}
                </td>
                <td className="muted">{(e.watched_at || "").slice(0, 10) || "—"}</td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr><td colSpan={4} className="muted center">No entries</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
