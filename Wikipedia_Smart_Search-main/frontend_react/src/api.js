const BASE = "/api";

function authHeaders(token) {
  const h = { "Content-Type": "application/json" };
  if (token) h["Authorization"] = `Bearer ${token}`;
  return h;
}

export async function ask(query, { top_k = 5, num_articles = 2, rerank = true, token = "" } = {}) {
  const res = await fetch(`${BASE}/ask`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ query, top_k, num_articles, rerank }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

/**
 * Streaming version — async generator that yields SSE event objects.
 * Event shapes:
 *   { type: "status",  content: "..." }
 *   { type: "token",   content: "..." }
 *   { type: "done",    answer, passages, scores, ... }
 *   { type: "error",   content: "..." }
 */
export async function* askStream(query, { top_k = 5, num_articles = 2, rerank = true, token = "", history = [], signal = null } = {}) {
  const res = await fetch(`${BASE}/ask/stream`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ query, top_k, num_articles, rerank, history }),
    signal,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      if (line.startsWith("data: ")) {
        try { yield JSON.parse(line.slice(6)); } catch { /* skip malformed */ }
      }
    }
  }
}

export async function register(username, password) {
  const res = await fetch(`${BASE}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function login(username, password) {
  const res = await fetch(`${BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function fetchHistory(token) {
  const res = await fetch(`${BASE}/auth/history`, {
    headers: authHeaders(token),
  });
  if (!res.ok) return [];
  const data = await res.json();
  return data.history ?? [];
}

export async function checkHealth() {
  try {
    const res = await fetch(`${BASE}/health`, { cache: "no-store" });
    return res.ok;
  } catch {
    return false;
  }
}
