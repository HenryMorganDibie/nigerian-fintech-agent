/**
 * NaijaFinAI Greeting System
 * ===========================
 * Recommendation: English-first with optional Nigerian cultural layer.
 *
 * Rationale:
 * - This is a fraud detection / fintech product — trust and clarity come first
 * - Nigerian greetings add cultural authenticity without compromising professionalism
 * - Stripe-style professionalism + cultural expression are NOT mutually exclusive
 * - The greeting is the one place warmth can be expressed; the rest stays precise
 *
 * UX Pattern:
 * - Default: English time-based greeting (professional, always correct)
 * - Nigerian mode: adds language-specific greeting as a secondary line
 * - No automatic language assumption — user opts in or system uses detected language
 * - Never replaces English label — always additive
 */

const TIME_GREETINGS = {
  morning:   { en: "Good morning",   yoruba: "Ẹ káàárọ̀",  igbo: "Ụtụtụ ọma", hausa: "Ina kwana",  pidgin: "Eku morning" },
  afternoon: { en: "Good afternoon", yoruba: "Ẹ káàsán",   igbo: "Ehihie ọma", hausa: "Ina wuni",   pidgin: "How far"     },
  evening:   { en: "Good evening",   yoruba: "Ẹ káàlẹ́",   igbo: "Anyasị ọma", hausa: "Ina yini",   pidgin: "Eku evening" },
};

/**
 * Get the time period based on hour.
 */
function getTimePeriod() {
  const hour = new Date().getHours();
  if (hour < 12) return "morning";
  if (hour < 17) return "afternoon";
  return "evening";
}

/**
 * Get a greeting string.
 *
 * @param {object} options
 * @param {string}  options.language - "english" | "yoruba" | "igbo" | "hausa" | "pidgin" | null
 * @param {boolean} options.nigerianMode - if true, returns bilingual greeting
 * @returns {{ primary: string, secondary: string|null, period: string }}
 */
export function getGreeting({ language = null, nigerianMode = false } = {}) {
  const period = getTimePeriod();
  const greetings = TIME_GREETINGS[period];

  const primary = greetings.en;

  // Only show secondary if Nigerian mode is on AND we have a valid language
  let secondary = null;
  if (nigerianMode || language) {
    const lang = language?.toLowerCase();
    if (lang === "yoruba")  secondary = greetings.yoruba;
    else if (lang === "igbo")    secondary = greetings.igbo;
    else if (lang === "hausa")   secondary = greetings.hausa;
    else if (lang === "pidgin")  secondary = greetings.pidgin;
    // english → no secondary (already in primary)
  }

  return { primary, secondary, period };
}

/**
 * Returns the appropriate greeting emoji for the time of day.
 */
export function getGreetingEmoji() {
  const period = getTimePeriod();
  return { morning: "🌅", afternoon: "☀️", evening: "🌆" }[period];
}
