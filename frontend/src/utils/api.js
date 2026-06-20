// Hardcoded fallback ensures it works even if VITE_API_URL isn't injected at build time
const BASE = import.meta.env.VITE_API_URL
  || "https://nigerian-fintech-agent-production.up.railway.app";

const API = `${BASE}/api`;

// ── Chat ──────────────────────────────────────────────────────────────────────
export async function streamChat({ message, history, provider, onToken, onToolCall, onLanguage, onDone }) {
  const res = await fetch(`${API}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history, provider, stream: true }),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    for (const line of dec.decode(value).split("\n").filter(l => l.startsWith("data: "))) {
      try {
        const d = JSON.parse(line.slice(6));
        if (d.type === "token")           onToken?.(d.content);
        else if (d.type === "tool_calls") onToolCall?.(d.tools);
        else if (d.type === "language")   onLanguage?.(d.language);
        else if (d.type === "done")       onDone?.(d);
      } catch {}
    }
  }
}

// ── Providers ─────────────────────────────────────────────────────────────────
export const fetchProviders = () =>
  fetch(`${API}/providers`).then(r => r.json()).catch(() => ({ providers: [] }));

// ── Eval ──────────────────────────────────────────────────────────────────────
export const runEval = (provider) =>
  fetch(`${API}/eval/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ use_synthetic: true, provider }),
  }).then(r => r.json());

export async function uploadEvalCsv(file, provider) {
  const fd = new FormData();
  fd.append("file", file);
  const url = `${API}/eval/upload${provider ? `?provider=${encodeURIComponent(provider)}` : ""}`;
  const res = await fetch(url, { method: "POST", body: fd });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Upload failed");
  return data;
}

export const evalCsvTemplateUrl = `${API}/eval/upload/template`;

// ── Workflows ─────────────────────────────────────────────────────────────────
export const runWorkflow = (scenario_id, provider) =>
  fetch(`${API}/workflows/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scenario_id, provider }),
  }).then(r => r.json());

export const listWorkflows = () =>
  fetch(`${API}/workflows/scenarios`).then(r => r.json());

// ── Media ─────────────────────────────────────────────────────────────────────
export async function uploadVoice(file, provider = "groq") {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("provider", provider);
  const r = await fetch(`${API}/media/voice`, { method: "POST", body: fd });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

export async function uploadFile(file, provider = "groq") {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("provider", provider);
  const r = await fetch(`${API}/media/upload`, { method: "POST", body: fd });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

// ── Fraud + Monitoring ────────────────────────────────────────────────────────
export const fetchDrift = () =>
  fetch(`${API}/fraud/drift`).then(r => r.json());

export const submitFeedback = (payload) =>
  fetch(`${API}/fraud/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }).then(r => r.json());

export const fetchEventStats = () =>
  fetch(`${API}/fraud/events/stats`).then(r => r.json());

// ── Simulation ────────────────────────────────────────────────────────────────
export const listSimulations = () =>
  fetch(`${API}/simulate/scenarios`).then(r => r.json());

export const runSimulation = (scenario_id, provider) =>
  fetch(`${API}/simulate/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scenario_id, provider }),
  }).then(r => r.json());

// ── A/B Testing ───────────────────────────────────────────────────────────────
export const listExperiments = () =>
  fetch(`${API}/ab/experiments`).then(r => r.json());

export const getExperimentResults = (experiment_id) =>
  fetch(`${API}/ab/results/${experiment_id}`).then(r => r.json());

// ── Case Queue ────────────────────────────────────────────────────────────────
export const listCases = (status) =>
  fetch(`${API}/cases/list${status ? `?status=${status}` : ""}`).then(r => r.json());

export const getCaseStats = () =>
  fetch(`${API}/cases/stats/summary`).then(r => r.json());

export const caseAction = (case_id, action, actor = "analyst", note = "") =>
  fetch(`${API}/cases/${case_id}/action`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, actor, note }),
  }).then(r => r.json());

// ── Health ────────────────────────────────────────────────────────────────────
export const fetchHealth = () =>
  fetch(`${API}/health`).then(r => r.json()).catch(() => null);
