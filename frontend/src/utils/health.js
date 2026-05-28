const BASE = import.meta.env.VITE_API_URL || "";

export async function checkBackendHealth() {
  try {
    const res = await fetch(`${BASE}/api/health`, { signal: AbortSignal.timeout(8000) });
    if (res.ok) return { ok: true };
    return { ok: false, reason: `HTTP ${res.status}` };
  } catch (e) {
    if (e.name === "TimeoutError") return { ok: false, reason: "Backend timeout — Railway may be waking up (free tier sleeps). Try again in 30s." };
    return { ok: false, reason: "Cannot reach backend. Check Railway is deployed and CORS includes this origin." };
  }
}
