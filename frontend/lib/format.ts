// Fonctions de formatage pures (testées dans tests/format.test.ts).

const TZ = "Europe/Paris";

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return new Intl.DateTimeFormat("fr-FR", {
    timeZone: TZ,
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(d);
}

export function relativeTime(iso: string | null | undefined, now: Date = new Date()): string {
  if (!iso) return "jamais";
  const diffS = Math.round((now.getTime() - new Date(iso).getTime()) / 1000);
  const future = diffS < 0;
  const s = Math.abs(diffS);
  let out: string;
  if (s < 60) out = "quelques secondes";
  else if (s < 3600) out = `${Math.floor(s / 60)} min`;
  else if (s < 86400) out = `${Math.floor(s / 3600)} h`;
  else out = `${Math.floor(s / 86400)} j`;
  return future ? `dans ${out}` : `il y a ${out}`;
}

export function formatDelay(minutes: number | null | undefined): string {
  if (minutes === null || minutes === undefined) return "non calculable";
  if (minutes < 60) return `${Math.round(minutes)} min`;
  if (minutes < 1440) return `${(minutes / 60).toFixed(1).replace(".", ",")} h`;
  return `${Math.round(minutes / 1440)} j`;
}

export function confidenceLevel(score: number | null | undefined): "inconnu" | "faible" | "moyen" | "eleve" {
  if (score === null || score === undefined) return "inconnu";
  if (score >= 0.75) return "eleve";
  if (score >= 0.5) return "moyen";
  return "faible";
}

export function isNew(firstSeenIso: string, now: Date = new Date(), hours = 24): boolean {
  return now.getTime() - new Date(firstSeenIso).getTime() < hours * 3600 * 1000;
}

/** N'autorise que http(s) pour les liens sortants (défense contre javascript: et data:). */
export function safeExternalUrl(url: string): string | null {
  try {
    const u = new URL(url);
    return u.protocol === "http:" || u.protocol === "https:" ? u.toString() : null;
  } catch {
    return null;
  }
}

export function buildQuery(params: Record<string, string | number | boolean | null | undefined>): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === null || v === undefined || v === "") continue;
    q.set(k, String(v));
  }
  const s = q.toString();
  return s ? `?${s}` : "";
}
