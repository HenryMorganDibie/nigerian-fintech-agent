import { useState, useCallback } from "react";
import { streamChat } from "../utils/api";

const GREETING = {
  role: "assistant",
  content: "**Ẹ káàbọ̀. Welcome.**\n\nI'm NaijaFinAI — built from the ground up for Nigerian fintechs.\n\nI speak your stack: CBN circulars, NIBSS NIP, BVN/NIN KYC tiers, NFIU STR deadlines, SIM swap patterns, Pidgin English.\n\nHow can I help you today?",
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

    setMessages(prev => [...prev, userMsg, { role: "assistant", content: "", timestamp: new Date(), streaming: true }]);

    let buf = "";
    try {
      await streamChat({
        message: text,
        history,
        provider,
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
            next[next.length - 1] = { ...next[next.length - 1], streaming: false, audit_id: d?.audit_id };
            return next;
          });
        },
      });
    } catch {
      setMessages(prev => {
        const next = [...prev];
        next[next.length - 1] = { role: "assistant", content: "Error connecting to agent. Check your API keys.", streaming: false, error: true, timestamp: new Date() };
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
