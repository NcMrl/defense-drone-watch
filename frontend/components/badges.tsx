import { confidenceLevel } from "@/lib/format";
import { label } from "@/lib/i18n";

const base = "inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-medium leading-4 whitespace-nowrap";

export function SyntheticBadge() {
  return (
    <span className={`${base} bg-synth text-white tracking-wide`} title="Donnée fictive du mode démonstration — ne pas utiliser comme information réelle">
      DONNÉE SYNTHÉTIQUE
    </span>
  );
}

export function ConfidenceBadge({ score }: { score: number | null }) {
  const level = confidenceLevel(score);
  const styles: Record<string, string> = {
    eleve: "bg-ok/10 text-ok ring-1 ring-ok/30",
    moyen: "bg-warn/10 text-warn ring-1 ring-warn/30",
    faible: "bg-bad/10 text-bad ring-1 ring-bad/30",
    inconnu: "bg-slate-100 text-muted ring-1 ring-slate-300",
  };
  return (
    <span className={`${base} ${styles[level]}`} title="Score explicable : voir la fiche du document">
      {label("confidence", level)}
      {score !== null && <span className="tabular opacity-80">{Math.round(score * 100)}</span>}
    </span>
  );
}

export function HealthBadge({ health }: { health: string }) {
  const styles: Record<string, string> = {
    ok: "bg-ok/10 text-ok",
    degradee: "bg-warn/10 text-warn",
    en_panne: "bg-bad/10 text-bad",
    jamais_collectee: "bg-slate-100 text-muted",
    desactivee: "bg-slate-100 text-muted",
    synthetique: "bg-synth/10 text-synth",
  };
  return <span className={`${base} ${styles[health] ?? "bg-slate-100"}`}>{label("health", health)}</span>;
}

export function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    a_verifier: "bg-warn/10 text-warn",
    corrobore: "bg-ok/10 text-ok",
    conteste: "bg-bad/10 text-bad",
  };
  return <span className={`${base} ${styles[status] ?? "bg-slate-100 text-muted"}`}>{label("statuses", status)}</span>;
}

export function SeverityBadge({ severity }: { severity: string }) {
  const styles: Record<string, string> = {
    critique: "bg-bad text-white",
    important: "bg-signal/15 text-signal",
    info: "bg-slate-100 text-muted",
  };
  return <span className={`${base} ${styles[severity] ?? ""}`}>{label("severities", severity)}</span>;
}

export function Tag({ children }: { children: React.ReactNode }) {
  return <span className={`${base} bg-white text-ink ring-1 ring-line`}>{children}</span>;
}
