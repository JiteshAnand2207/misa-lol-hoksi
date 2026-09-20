export interface AskItem {
  id: string;
  ownerId: string;
  q: string;
  a: string;
  status: "pending" | "published";
  at: string;
}

export interface GuestbookItem {
  id: string;
  ownerId: string;
  line: string;
  name: string;
  status: "pending" | "approved";
  at: string;
}

export interface DoodleItem {
  id: string;
  ownerId: string;
  svg: string;
  status: "pending" | "approved";
  at: string;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1/me${path}`, {
    ...init,
    credentials: "include",
    cache: "no-store",
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  const body = await response.json().catch(() => ({})) as { detail?: string; error?: string };
  if (!response.ok) throw new Error(String(body.detail || body.error || "Request failed."));
  return body as T;
}

export function listAsks() {
  return request<{ waiting: AskItem[]; answered: AskItem[] }>("/asks");
}

export function answerAsk(askId: string, answer: string) {
  return request<{ ok: boolean; ask: AskItem }>(`/asks/${encodeURIComponent(askId)}/answer`, {
    method: "POST",
    body: JSON.stringify({ answer }),
  });
}

export function binAsk(askId: string) {
  return request<{ ok: boolean }>(`/asks/${encodeURIComponent(askId)}`, { method: "DELETE" });
}

export function listGuestbook() {
  return request<{ pending: GuestbookItem[]; approved: GuestbookItem[] }>("/guestbook");
}

export function approveSignature(signatureId: string) {
  return request<{ ok: boolean; signature: GuestbookItem }>(`/guestbook/${encodeURIComponent(signatureId)}/approve`, { method: "POST" });
}

export function binSignature(signatureId: string) {
  return request<{ ok: boolean }>(`/guestbook/${encodeURIComponent(signatureId)}`, { method: "DELETE" });
}

export function listDoodles() {
  return request<{ pending: DoodleItem[]; approved: DoodleItem[] }>("/doodles");
}

export function approveDoodle(doodleId: string) {
  return request<{ ok: boolean; doodle: DoodleItem }>(`/doodles/${encodeURIComponent(doodleId)}/approve`, { method: "POST" });
}

export function binDoodle(doodleId: string) {
  return request<{ ok: boolean }>(`/doodles/${encodeURIComponent(doodleId)}`, { method: "DELETE" });
}

export function clearTally() {
  return request<{ ok: boolean; total: number }>("/tally", { method: "DELETE" });
}