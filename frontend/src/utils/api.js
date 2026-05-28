const BASE = import.meta.env.VITE_API_URL;

if (!BASE) {
  throw new Error("VITE_API_URL is not defined in environment");
}

/* ---------------- CHAT STREAM ---------------- */
export async function streamChat({
  message,
  history,
  provider,
  onToken,
  onToolCall,
  onLanguage,
  onDone,
}) {
  const res = await fetch(`${BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      history,
      provider,
      tenant_id: "default",
      stream: true,
    }),
  });

  if (!res.ok) throw new Error(`API ${res.status}`);

  const reader = res.body.getReader();
  const dec = new TextDecoder();

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    const lines = dec
      .decode(value)
      .split("\n")
      .filter((l) => l.startsWith("data: "));

    for (const line of lines) {
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

/* ---------------- PROVIDERS ---------------- */
export const fetchProviders = () =>
  fetch(`${BASE}/api/providers`)
    .then((r) => r.json())
    .catch(() => ({ providers: [] }));

/* ---------------- EVAL (FIX FOR YOUR BUILD ERROR) ---------------- */
export const runEval = (provider) =>
  fetch(`${BASE}/api/eval/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      use_synthetic: true,
      provider,
    }),
  }).then((r) => r.json());

/* ---------------- WORKFLOWS ---------------- */
export const runWorkflow = (scenario_id, provider) =>
  fetch(`${BASE}/api/workflows/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scenario_id, provider }),
  }).then((r) => r.json());

export const listWorkflows = () =>
  fetch(`${BASE}/api/workflows/scenarios`).then((r) => r.json());

/* ---------------- MEDIA ---------------- */
export async function uploadVoice(file, provider = "groq") {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("provider", provider);

  const r = await fetch(`${BASE}/api/media/voice`, {
    method: "POST",
    body: fd,
  });

  if (!r.ok) throw new Error("Voice upload failed");
  return r.json();
}

export async function uploadFile(file, provider = "groq") {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("provider", provider);

  const r = await fetch(`${BASE}/api/media/upload`, {
    method: "POST",
    body: fd,
  });

  if (!r.ok) throw new Error("File upload failed");
  return r.json();
}
