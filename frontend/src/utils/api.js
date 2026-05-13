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

export const fetchProviders = () => fetch(`${BASE}/providers`).then(r => r.json()).catch(() => ({ providers: [] }));

export async function analyzeFraud(payload) {
  const r = await fetch(`${BASE}/fraud/analyze`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  if (!r.ok) throw new Error("Fraud API failed");
  return r.json();
}
