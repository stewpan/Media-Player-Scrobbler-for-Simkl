// Tiny typed fetch wrapper around the embedded Flask API.

export interface Status {
  monitor_running: boolean;
  tracking: boolean;
  title?: string | null;
  raw_title?: string | null;
  media_type?: string | null;
  season?: number | null;
  episode?: number | null;
  state?: string | null;
  completed?: boolean;
  is_rewatch?: boolean;
  progress_percent?: number | null;
  position_seconds?: number | null;
  duration_seconds?: number | null;
  completion_threshold?: number | null;
}

export interface HistoryEntry {
  simkl_id?: number;
  title?: string;
  type?: string;
  watched_at?: string;
  year?: number;
  poster_url?: string;
  season?: number;
  episode?: number;
}

export interface Stats {
  movie: number;
  show: number;
  anime: number;
  total: number;
}

export interface Settings {
  watch_completion_threshold: number;
  disable_notifications: boolean;
  skip_rewatch_scrobble: boolean;
  auto_sync_interval: number;
  allow_dirs: string[];
  deny_dirs: string[];
}

export interface AuthStatus {
  authenticated: boolean;
  user_id?: number | string | null;
  in_progress: boolean;
  user_code?: string | null;
  verification_url?: string | null;
  pin_url?: string | null;
  error?: string | null;
}

async function getJSON<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url} -> ${res.status}`);
  return res.json() as Promise<T>;
}

async function postJSON<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = (await res.json().catch(() => ({}))) as T;
  if (!res.ok) throw new Error((data as { error?: string })?.error || `${url} -> ${res.status}`);
  return data;
}

export const api = {
  status: () => getJSON<Status>("/api/status"),
  history: (limit = 200) =>
    getJSON<{ entries: HistoryEntry[]; total: number }>(`/api/history?limit=${limit}`),
  stats: () => getJSON<Stats>("/api/stats"),
  getSettings: () => getJSON<Settings>("/api/settings"),
  updateSettings: (patch: Partial<Settings>) => postJSON<{ updated: Partial<Settings> }>("/api/settings", patch),
  authStatus: () => getJSON<AuthStatus>("/api/auth/status"),
  authStart: () => postJSON<AuthStatus & { started: boolean }>("/api/auth/start", {}),
};
