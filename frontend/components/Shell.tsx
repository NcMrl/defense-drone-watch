"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import type { Stats } from "@/lib/api";
import { formatDateTime, relativeTime } from "@/lib/format";
import { useApi } from "@/lib/useApi";

const NAV = [
  { href: "/", label: "Tableau de bord" },
  { href: "/flux", label: "Flux & recherche" },
  { href: "/alertes", label: "Alertes & règles" },
  { href: "/entreprises", label: "Entreprises" },
  { href: "/sources", label: "Sources & collecte" },
];

export function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const synthetic = useApi<Stats>("/api/stats?synthetic=only");
  const all = useApi<Stats>("/api/stats");
  const syntheticCount = synthetic.data?.totaux.documents ?? 0;
  const lastCollect = all.data?.sources.derniere_collecte_reussie ?? null;

  return (
    <div className="flex min-h-screen">
      <aside className="hidden w-56 shrink-0 flex-col bg-ink text-slate-200 md:flex">
        <div className="border-b border-white/10 px-5 py-5">
          <div className="text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-400">Veille OSINT</div>
          <div className="mt-1 text-[15px] font-semibold leading-tight text-white">Defense Drone Watch</div>
        </div>
        <nav className="flex flex-col gap-0.5 p-3" aria-label="Navigation principale">
          {NAV.map((item) => {
            const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`rounded px-3 py-2 text-sm transition-colors ${active ? "bg-white/10 text-white" : "text-slate-300 hover:bg-white/5 hover:text-white"}`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="mt-auto border-t border-white/10 p-4 text-[11px] leading-relaxed text-slate-400">
          Sources ouvertes uniquement. Aucune donnée classifiée ni privée.
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex flex-wrap items-center gap-x-6 gap-y-1 border-b border-line bg-white px-4 py-2 text-xs text-muted md:px-6">
          <nav className="flex gap-3 md:hidden" aria-label="Navigation mobile">
            {NAV.map((item) => (
              <Link key={item.href} href={item.href} className="text-ink underline-offset-2 hover:underline">
                {item.label.split(" ")[0]}
              </Link>
            ))}
          </nav>
          <span title="L'interface interroge le serveur toutes les 60 secondes ; ce n'est pas du temps réel.">
            <span className="mr-1 inline-block h-1.5 w-1.5 rounded-full bg-slate-400 align-middle" />
            Actualisation périodique (60 s) · dernière : {all.fetchedAt ? all.fetchedAt.toLocaleTimeString("fr-FR") : "—"}
          </span>
          <span>
            Dernière collecte réussie (sources réelles) :{" "}
            <strong className="font-medium text-ink">{lastCollect ? `${formatDateTime(lastCollect)} (${relativeTime(lastCollect)})` : "aucune"}</strong>
          </span>
          {all.error && <span className="text-bad">API injoignable : {all.error}</span>}
        </header>

        {syntheticCount > 0 && (
          <div role="status" className="border-b border-synth/30 bg-synth/10 px-4 py-2 text-xs text-synth md:px-6">
            <strong>Mode démonstration actif :</strong> {syntheticCount} document(s) synthétique(s) présent(s) en base. Ils sont fictifs,
            marqués « DONNÉE SYNTHÉTIQUE » et préfixés « [DÉMO] ». Suppression : <code className="font-mono">python -m app.cli purge-demo</code>.
          </div>
        )}

        <main className="min-w-0 flex-1 px-4 py-5 md:px-6">{children}</main>
      </div>
    </div>
  );
}

export function PageTitle({ title, subtitle, children }: { title: string; subtitle?: string; children?: React.ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-0.5 text-sm text-muted">{subtitle}</p>}
      </div>
      {children}
    </div>
  );
}

export function Panel({ title, children, className = "", action }: { title?: string; children: React.ReactNode; className?: string; action?: React.ReactNode }) {
  return (
    <section className={`rounded-md border border-line bg-white ${className}`}>
      {title && (
        <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
          <h2 className="text-[13px] font-semibold uppercase tracking-wide text-muted">{title}</h2>
          {action}
        </div>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

export function Empty({ children }: { children: React.ReactNode }) {
  return <p className="py-6 text-center text-sm text-muted">{children}</p>;
}

export function ErrorBox({ message }: { message: string }) {
  return <p className="rounded border border-bad/30 bg-bad/5 px-3 py-2 text-sm text-bad">{message}</p>;
}
