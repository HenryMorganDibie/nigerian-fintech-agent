const BASE = import.meta.env.VITE_API_URL || "/api";

// ── Chat ──────────────────────────────────────────────────────────────────────
export async function streamChat({ message, history, provider, onToken, onToolCall, onLanguage, onDone }) {
  const res = await fetch(`${BASE}/chat`, {
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
        if (d.type === "token")      onToken?.(d.content);
        else if (d.type === "tool_calls") onToolCall?.(d.tools);
        else if (d.type === "language")   onLanguage?.(d.language);
        else if (d.type === "done")       onDone?.(d);
      } catch {}
    }
  }
}

// ── Providers ─────────────────────────────────────────────────────────────────
export const fetchProviders = () =>
  fetch(`${BASE}/providers`).then(r => r.json()).catch(() => ({ providers: [] }));

// ── Eval ─────────────────────────────────────────────────────────────────────
export const runEval = (provider) =>
  fetch(`${BASE}/eval/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ use_synthetic: true, provider }),
  }).then(r => r.json());

// ── Workflows ─────────────────────────────────────────────────────────────────
export const runWorkflow = (scenario_id, provider) =>
  fetch(`${BASE}/workflows/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scenario_id, provider }),
  }).then(r => r.json());

export const listWorkflows = () =>
  fetch(`${BASE}/workflows/scenarios`).then(r => r.json());

// ── Media (voice + file) ──────────────────────────────────────────────────────
export async function uploadVoice(file, provider = "groq") {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("provider", provider);
  const r = await fetch(`${BASE}/media/voice`, { method: "POST", body: fd });
  if (!r.ok) throw new Error("Voice upload failed");
  return r.json();
}

export async function uploadFile(file, provider = "groq") {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("provider", provider);
  const r = await fetch(`${BASE}/media/upload`, { method: "POST", body: fd });
  if (!r.ok) throw new Error("File upload failed");
  return r.json();
}

// ── Fraud + Monitoring ────────────────────────────────────────────────────────
export const fetchDrift = () =>
  fetch(`${BASE}/fraud/drift`).then(r => r.json());

export const submitFeedback = (payload) =>
  fetch(`${BASE}/fraud/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }).then(r => r.json());

export const fetchEventStats = () =>
  fetch(`${BASE}/fraud/events/stats`).then(r => r.json());

// ── Simulation ────────────────────────────────────────────────────────────────
export const listSimulations = () =>
  fetch(`${BASE}/simulate/scenarios`).then(r => r.json());

export const runSimulation = (scenario_id, provider) =>
  fetch(`${BASE}/simulate/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scenario_id, provider }),
  }).then(r => r.json());

// ── A/B Testing ───────────────────────────────────────────────────────────────
export const listExperiments = () =>
  fetch(`${BASE}/ab/experiments`).then(r => r.json());

export const getExperimentResults = (experiment_id) =>
  fetch(`${BASE}/ab/results/${experiment_id}`).then(r => r.json());

// ── Case Queue ────────────────────────────────────────────────────────────────
export const listCases = (status) =>
  fetch(`${BASE}/cases/list${status ? `?status=${status}` : ""}`).then(r => r.json());

export const getCaseStats = () =>
  fetch(`${BASE}/cases/stats/summary`).then(r => r.json());

export const caseAction = (case_id, action, actor = "analyst", note = "") =>
  fetch(`${BASE}/cases/${case_id}/action`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, actor, note }),
  }).then(r => r.json());

// ── Health ────────────────────────────────────────────────────────────────────
export const fetchHealth = () =>
  fetch(`${BASE}/health`).then(r => r.json()).catch(() => null);
