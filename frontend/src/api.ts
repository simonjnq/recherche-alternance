import type {
  ApplicationStatus,
  CV,
  CVEditable,
  CVStructured,
  CVStyle,
  CVTemplateInfo,
  Offer,
  OfferDetail,
  Profile,
  Progress,
  Source,
} from "./types";

const API_BASE = "/api";

async function request<T>(
  path: string,
  init?: RequestInit & { params?: Record<string, string | number | boolean | undefined> }
): Promise<T> {
  const { params, ...rest } = init ?? {};
  let url = `${API_BASE}${path}`;
  if (params) {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v === undefined || v === null || v === "") continue;
      qs.set(k, String(v));
    }
    const s = qs.toString();
    if (s) url += `?${s}`;
  }
  const res = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...(rest.headers ?? {}),
    },
    ...rest,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      // ignore
    }
    throw new Error(`${res.status} ${detail}`);
  }
  if (res.status === 204) return undefined as T;
  const ct = res.headers.get("content-type") ?? "";
  if (ct.includes("application/json")) return (await res.json()) as T;
  return (await res.text()) as unknown as T;
}

export interface ListOffersParams {
  min_score?: number;
  favorites_only?: boolean;
  source?: Source | "";
  search?: string;
  new_only?: boolean;
  sort?: "score" | "recent" | "company";
  generated?: boolean;
  contract?: string;
  location?: string;
  days_max?: number;
  limit?: number;
}

export function reorderOffers(orderedIds: number[]): Promise<void> {
  return request<void>("/offers/reorder", {
    method: "POST",
    body: JSON.stringify({ ordered_ids: orderedIds }),
  });
}

export function cleanupOffers(
  mode: "old" | "unscored",
  days = 30
): Promise<{ ok: boolean; hidden: number }> {
  return request<{ ok: boolean; hidden: number }>("/offers/cleanup", {
    method: "POST",
    params: { mode, days },
  });
}

export function listOffers(params: ListOffersParams = {}): Promise<Offer[]> {
  return request<Offer[]>("/offers", { params: { limit: 500, ...params } });
}

export function getOffer(id: number): Promise<OfferDetail> {
  return request<OfferDetail>(`/offers/${id}`);
}

export function setFavorite(id: number, value: boolean): Promise<void> {
  return request<void>(`/offers/${id}/favorite`, {
    method: "POST",
    params: { value },
  });
}

export function hideOffer(id: number): Promise<void> {
  return request<void>(`/offers/${id}/hide`, { method: "POST" });
}

export function unhideOffer(id: number): Promise<void> {
  return request<void>(`/offers/${id}/unhide`, { method: "POST" });
}

export function setOfferStatus(
  id: number,
  value: ApplicationStatus
): Promise<void> {
  return request<void>(`/offers/${id}/status`, {
    method: "POST",
    params: { value },
  });
}

export interface OfferTracking {
  applied_at?: string | null;
  follow_up_at?: string | null;
  notes?: string | null;
  contact?: string | null;
  checklist?: Record<string, boolean>;
}

export function updateOfferTracking(
  id: number,
  fields: OfferTracking
): Promise<void> {
  return request<void>(`/offers/${id}/tracking`, {
    method: "POST",
    body: JSON.stringify(fields),
  });
}

export function generateOffer(id: number): Promise<void> {
  return request<void>(`/offers/${id}/generate`, { method: "POST" });
}

export function exportCsvUrl(favoritesOnly = true): string {
  return `${API_BASE}/offers/export.csv?favorites_only=${favoritesOnly ? "true" : "false"}`;
}

export function downloadCVUrl(id: number): string {
  return `${API_BASE}/offers/${id}/cv`;
}

export function downloadLetterUrl(id: number): string {
  return `${API_BASE}/offers/${id}/letter`;
}

export function downloadCVPdfUrl(id: number): string {
  return `${API_BASE}/offers/${id}/cv/pdf`;
}

export function downloadLetterPdfUrl(id: number): string {
  return `${API_BASE}/offers/${id}/letter/pdf`;
}

export function getGeneratedCV(id: number): Promise<{ html: string }> {
  return request<{ html: string }>(`/offers/${id}/cv/content`);
}

export function putGeneratedCV(id: number, html: string): Promise<void> {
  return request<void>(`/offers/${id}/cv/content`, {
    method: "PUT",
    body: JSON.stringify({ html }),
  });
}

export function aiEditCV(
  id: number,
  instruction: string
): Promise<{ html: string }> {
  return request<{ html: string }>(`/offers/${id}/cv/ai-edit`, {
    method: "POST",
    body: JSON.stringify({ instruction }),
  });
}

export function getGeneratedLetter(id: number): Promise<{ markdown: string }> {
  return request<{ markdown: string }>(`/offers/${id}/letter/content`);
}

export function putGeneratedLetter(
  id: number,
  markdown: string
): Promise<void> {
  return request<void>(`/offers/${id}/letter/content`, {
    method: "PUT",
    body: JSON.stringify({ markdown }),
  });
}

export function aiEditLetter(
  id: number,
  instruction: string
): Promise<{ markdown: string }> {
  return request<{ markdown: string }>(`/offers/${id}/letter/ai-edit`, {
    method: "POST",
    body: JSON.stringify({ instruction }),
  });
}

// --- Visual CV editor (v2) ---

export function getCVEditable(id: number): Promise<CVEditable> {
  return request<CVEditable>(`/offers/${id}/cv/editable`);
}

export function putCVEditable(
  id: number,
  structured: CVStructured,
  style: CVStyle
): Promise<{ ok: boolean; html: string }> {
  return request<{ ok: boolean; html: string }>(`/offers/${id}/cv/editable`, {
    method: "PUT",
    body: JSON.stringify({ structured, style }),
  });
}

export function renderCVPreview(
  id: number,
  structured: CVStructured,
  style: CVStyle
): Promise<{ html: string }> {
  return request<{ html: string }>(`/offers/${id}/cv/render-preview`, {
    method: "POST",
    body: JSON.stringify({ structured, style }),
  });
}

export function aiRewriteBullet(
  id: number,
  bullet: string,
  instruction: string
): Promise<{ bullet: string }> {
  return request<{ bullet: string }>(`/offers/${id}/cv/ai-bullet`, {
    method: "POST",
    body: JSON.stringify({ bullet, instruction }),
  });
}

export function aiRewriteBlock(
  id: number,
  path: string,
  value: string,
  instruction: string
): Promise<{ value: string }> {
  return request<{ value: string }>(`/offers/${id}/cv/ai-block`, {
    method: "POST",
    body: JSON.stringify({ path, value, instruction }),
  });
}

export function listCVTemplates(): Promise<CVTemplateInfo[]> {
  return request<CVTemplateInfo[]>("/cv-templates");
}

export interface CVInspiration {
  url: string;
  source: string;
  title: string;
}

export function listCVInspirations(limit = 60): Promise<{ items: CVInspiration[] }> {
  return request<{ items: CVInspiration[] }>("/cv-templates/inspirations", {
    params: { limit },
  });
}

export function cloneStyleFromImage(imageUrl: string): Promise<{ style: CVStyle & { notes?: string } }> {
  return request<{ style: CVStyle & { notes?: string } }>("/cv-templates/clone-style", {
    method: "POST",
    body: JSON.stringify({ image_url: imageUrl }),
  });
}

export function aiRewriteGlobal(
  id: number,
  structured: CVStructured,
  instruction: string
): Promise<{ structured: CVStructured }> {
  return request<{ structured: CVStructured }>(`/offers/${id}/cv/ai-global`, {
    method: "POST",
    body: JSON.stringify({ structured, instruction }),
  });
}

export function listCVs(): Promise<CV[]> {
  return request<CV[]>("/cvs");
}

export async function uploadCV(file: File, setDefault = false): Promise<CV> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(
    `${API_BASE}/cvs?set_default=${setDefault ? "true" : "false"}`,
    { method: "POST", body: form }
  );
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      // ignore
    }
    throw new Error(`${res.status} ${detail}`);
  }
  return (await res.json()) as CV;
}

export function deleteCV(id: number): Promise<void> {
  return request<void>(`/cvs/${id}`, { method: "DELETE" });
}

export function setDefaultCV(id: number): Promise<void> {
  return request<void>(`/cvs/${id}/default`, { method: "POST" });
}

export function getCVContent(
  id: number
): Promise<{ id: number; filename: string; html: string }> {
  return request<{ id: number; filename: string; html: string }>(
    `/cvs/${id}/content`
  );
}

export function backupUrl(): string {
  return `${API_BASE}/backup`;
}

export async function importBackup(json: unknown): Promise<{ ok: boolean; restored: Record<string, number> }> {
  const res = await fetch(`${API_BASE}/backup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(json),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return (await res.json()) as { ok: boolean; restored: Record<string, number> };
}

export function getProfile(): Promise<Profile> {
  return request<Profile>("/profile");
}

export function updateProfile(profile: Profile): Promise<Profile> {
  return request<Profile>("/profile", {
    method: "PUT",
    body: JSON.stringify(profile),
  });
}

export function getProfilePhotoUrl(cacheBust?: number | string): string {
  const cb = cacheBust !== undefined ? `?t=${cacheBust}` : "";
  return `${API_BASE}/profile/photo${cb}`;
}

export async function uploadProfilePhoto(
  file: File
): Promise<{ ok: boolean; filename: string; size: number }> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/profile/photo`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      // ignore
    }
    throw new Error(`${res.status} ${detail}`);
  }
  return (await res.json()) as { ok: boolean; filename: string; size: number };
}

export function deleteProfilePhoto(): Promise<void> {
  return request<void>("/profile/photo", { method: "DELETE" });
}

export function startSearch(): Promise<void> {
  return request<void>("/search/start", { method: "POST" });
}

export function getSearchStatus(): Promise<{
  running: boolean;
  last_progress: Progress | null;
}> {
  return request<{ running: boolean; last_progress: Progress | null }>(
    "/search/status"
  );
}

export interface SearchStats {
  total: number;
  avg_score: number;
  high_score: number;
  generated: number;
  new_count: number;
  overdue_count: number;
  by_source: { source: string; count: number; avg_score: number }[];
  last_run: {
    started_at: string;
    finished_at: string | null;
    status: string;
    stats: Record<string, number>;
  } | null;
}

export function getSearchStats(): Promise<SearchStats> {
  return request<SearchStats>("/search/stats");
}

export function getTimeline(
  days = 21
): Promise<{ days: { day: string; count: number }[] }> {
  return request<{ days: { day: string; count: number }[] }>("/search/timeline", {
    params: { days },
  });
}

export function addLinkedIn(
  url: string
): Promise<{ ok: boolean; offer_id: number }> {
  return request<{ ok: boolean; offer_id: number }>("/linkedin/add", {
    method: "POST",
    body: JSON.stringify({ url }),
  });
}

export function connectProgressWS(
  onMessage: (msg: Progress) => void
): () => void {
  let ws: WebSocket | null = null;
  let retry = 0;
  let closed = false;
  let timer: number | null = null;

  const connect = () => {
    if (closed) return;
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${proto}//${window.location.host}/api/ws`;
    ws = new WebSocket(url);

    ws.onopen = () => {
      retry = 0;
    };
    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data) as Progress;
        onMessage(data);
      } catch {
        // ignore malformed messages
      }
    };
    ws.onclose = () => {
      if (closed) return;
      retry += 1;
      const delay = Math.min(15000, 500 * 2 ** Math.min(retry, 5));
      timer = window.setTimeout(connect, delay);
    };
    ws.onerror = () => {
      ws?.close();
    };
  };

  connect();

  return () => {
    closed = true;
    if (timer !== null) window.clearTimeout(timer);
    ws?.close();
  };
}
