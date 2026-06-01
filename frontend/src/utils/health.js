const BASE = import.meta.env.VITE_API_URL
  || "https://nigerian-fintech-agent-production.up.railway.app";

export async function checkBackendHealth() {
  try {
    const res = await fetch(`${BASE}/api/health`, { signal: AbortSignal.timeout(8000) });
    if (res.ok) return { ok: true };
    return { ok: false, reason: `HTTP ${res.status}` };
  } catch (e) {
    if (e.name === "TimeoutError" || e.name === "AbortError") {
      return { ok: false, reason: "Backend sleeping (Railway free tier). Try again in 30s." };
    }
    return { ok: false, reason: "Cannot reach backend." };
  }
}
