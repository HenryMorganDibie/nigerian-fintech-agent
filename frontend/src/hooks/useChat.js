import { useState, useCallback } from "react";
import { streamChat } from "../utils/api";

const GREETING = {
  role: "assistant",
  content: "**Welcome to NaijaFinAI** 🇳🇬\n\nI'm built from the ground up for Nigerian fintechs.\n\nI speak your stack: CBN circulars, NIBSS NIP, BVN/NIN KYC tiers, NFIU STR deadlines, SIM swap patterns, Pidgin English.\n\nHow can I help you today?",
  timestamp: new Date(),
  language: "english",
};

export function useChat(provider) {
  const [messages, setMessages] = useState([GREETING]);
  const [loading, setLoading] = useState(false);
  const [tools, setTools] = useState([]);
  const [language, setLanguage] = useState("english");

  const send = useCallback(async (text) => {
    if (!text.trim() || loading) return;
    setLoading(true);
    setTools([]);

    const userMsg = { role: "user", content: text, timestamp: new Date() };
    const history = messages.map(({ role, content }) => ({ role, content }));

    setMessages(prev => [
      ...prev,
      userMsg,
      { role: "assistant", content: "", timestamp: new Date(), streaming: true },
    ]);

    let buf = "";
    try {
      await streamChat({
        message: text,
        history,
        provider: provider || "groq",
        onLanguage: (lang) => setLanguage(lang),
        onToken: (tok) => {
          buf += tok;
          setMessages(prev => {
            const next = [...prev];
            next[next.length - 1] = { ...next[next.length - 1], content: buf };
            return next;
          });
        },
        onToolCall: (t) => setTools(t),
        onDone: (d) => {
          setMessages(prev => {
            const next = [...prev];
            next[next.length - 1] = {
              ...next[next.length - 1],
              streaming: false,
              audit_id: d?.audit_id,
            };
            return next;
          });
        },
      });
    } catch (err) {
      const raw = err?.message || "";
      let errMsg;

      if (raw.includes("Failed to fetch") || raw.includes("NetworkError") || raw.includes("ERR_NETWORK")) {
        errMsg = "Cannot reach backend. Railway may be sleeping — wait 30 seconds and try again.";
      } else if (raw.includes("502") || raw.includes("503") || raw.includes("504")) {
        errMsg = "Backend is starting up (Railway cold start). Wait 20–30 seconds and try again.";
      } else if (raw.includes("404")) {
        errMsg = "Endpoint not found (404). The backend may not have the latest code — try again shortly.";
      } else if (raw.includes("422")) {
        errMsg = "Invalid request (422). Please try rephrasing your message.";
      } else if (raw.includes("401") || raw.includes("403")) {
        errMsg = `Auth error (${raw.match(/\d{3}/)?.[0]}). Check Railway environment variables.`;
      } else if (raw.match(/4\d\d/)) {
        errMsg = `Request error (${raw.match(/\d{3}/)?.[0]}). Check the backend logs on Railway.`;
      } else if (raw.match(/5\d\d/)) {
        errMsg = `Server error (${raw.match(/\d{3}/)?.[0]}). Check Railway deploy logs.`;
      } else {
        errMsg = raw ? `Error: ${raw}` : "Something went wrong. Check Railway is deployed and running.";
      }

      setMessages(prev => {
        const next = [...prev];
        next[next.length - 1] = {
          role: "assistant",
          content: errMsg,
          streaming: false,
          error: true,
          timestamp: new Date(),
        };
        return next;
      });
    } finally {
      setLoading(false);
    }
  }, [messages, loading, provider]);

  const clear = useCallback(() => {
    setMessages([GREETING]);
    setTools([]);
  }, []);

  return { messages, send, loading, tools, language, clear };
}
