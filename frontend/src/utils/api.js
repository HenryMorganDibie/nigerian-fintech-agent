const BASE = import.meta.env.VITE_API_URL || "/api";

export async function streamChat({ message, history, provider, onToken, onToolCall, onLanguage, onDone }) {
  const res = await fetch(`${BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history, provider, stream: true }),
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    for (const line of dec.decode(value).split("\n").filter(l => l.startsWith("data: "))) {
      try {
        const d = JSON.parse(line.slice(6));
        if (d.type === "token") onToken?.(d.content);
        else if (d.type === "tool_calls") onToolCall?.(d.tools);
        else if (d.type === "language") onLanguage?.(d.language);
        else if (d.type === "done") onDone?.(d);
      } catch {}
    }
  }
}

export const fetchProviders = () =>
  fetch(`${BASE}/providers`).then(r => r.json()).catch(() => ({ providers: [] }));

export const runEval = (provider) =>
  fetch(`${BASE}/eval/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ use_synthetic: true, provider }),
  }).then(r => r.json());

export const runWorkflow = (scenario_id, provider) =>
  fetch(`${BASE}/workflows/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scenario_id, provider }),
  }).then(r => r.json());

export const listWorkflows = () =>
  fetch(`${BASE}/workflows/scenarios`).then(r => r.json());

export async function uploadVoice(file, provider) {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("provider", provider || "groq");
  const r = await fetch(`${BASE}/media/voice`, { method: "POST", body: fd });
  if (!r.ok) throw new Error("Voice upload failed");
  return r.json();
}

export async function uploadFile(file, provider) {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("provider", provider || "groq");
  const r = await fetch(`${BASE}/media/upload`, { method: "POST", body: fd });
  if (!r.ok) throw new Error("File upload failed");
  return r.json();
}
