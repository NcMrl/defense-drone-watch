"use client";

import Link from "next/link";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { HealthBadge, SeverityBadge, SyntheticBadge } from "@/components/badges";
import { DocumentCard, useSaved } from "@/components/DocumentCard";
import { Empty, ErrorBox, PageTitle, Panel } from "@/components/Shell";
import type { Alert, DocumentPage, Stats } from "@/lib/api";
import { relativeTime } from "@/lib/format";
import { label } from "@/lib/i18n";
import { useApi } from "@/lib/useApi";

const INK = "#16233a";

function Kpi({ label: text, value, hint, tone }: { label: string; value: string | number; hint?: string; tone?: "signal" }) {
  return (
    <div className="rounded-md border border-line bg-white px-4 py-3">
      <div className="text-xs text-muted">{text}</div>
      <div className={`tabular mt-1 text-2xl font-semibold ${tone === "signal" ? "text-signal" : ""}`}>{value}</div>
      {hint && <div className="mt-0.5 text-[11px] text-muted">{hint}</div>}
    </div>
  );
}

function HBars({ data, labeller }: { data: { cle: string; n: number }[]; labeller: (k: string) => string }) {
  if (!data.length) return <Empty>Aucune donnée.</Empty>;
  const rows = data.slice(0, 8).map((d) => ({ name: labeller(d.cle), n: d.n }));
  return (
    <ResponsiveContainer width="100%" height={rows.length * 30 + 10}>
      <BarChart data={rows} layout="vertical" margin={{ left: 0, right: 16, top: 0, bottom: 0 }}>
        <XAxis type="number" hide allowDecimals={false} />
        <YAxis type="category" dataKey="name" width={150} tick={{ fontSize: 12, fill: "#334155" }} axisLine={false} tickLine={false} />
        <Tooltip cursor={{ fill: "#f1f5f9" }} formatter={(v) => [v, "Documents"]} />
        <Bar dataKey="n" fill={INK} radius={[0, 3, 3, 0]} barSize={14} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export default function Dashboard() {
  const stats = useApi<Stats>("/api/stats");
  const important = useApi<DocumentPage>("/api/documents?min_relevance=0.6&page_size=5");
  const alerts = useApi<Alert[]>("/api/alerts?unread_only=true&limit=6");
  const [saved, toggleSave] = useSaved();

  if (stats.error) return <ErrorBox message={`Impossible de charger le tableau de bord : ${stats.error}`} />;
  const s = stats.data;

  return (
    <>
      <PageTitle title="Tableau de bord" subtitle="Vue d'ensemble de la veille. Toutes les valeurs sont calculées à partir de la base." />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <Kpi label="Documents en base" value={s?.totaux.documents ?? "…"} hint={`${s?.totaux.occurrences ?? "…"} occurrences`} />
        <Kpi label="Nouveaux (24 h)" value={s?.totaux.nouveaux_24h ?? "…"} />
        <Kpi label="Pertinents aujourd'hui" value={s?.totaux.pertinents_aujourdhui ?? "…"} hint="pertinence ≥ 0,6" />
        <Kpi label="Alertes prioritaires non lues" value={s?.totaux.alertes_prioritaires_non_lues ?? "…"} tone="signal" />
        <Kpi
          label="Taux de déduplication"
          value={s?.totaux.taux_deduplication != null ? `${Math.round(s.totaux.taux_deduplication * 100)} %` : "—"}
          hint="occurrences fusionnées"
        />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Panel title="Volume collecté (30 jours, par jour de détection)" className="xl:col-span-2">
          {s && s.par_jour.length ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={s.par_jour.map((d) => ({ jour: d.cle.slice(5), n: d.n }))} margin={{ left: -20, right: 8, top: 4 }}>
                <CartesianGrid vertical={false} stroke="#eef1f5" />
                <XAxis dataKey="jour" tick={{ fontSize: 11, fill: "#5b6678" }} tickLine={false} axisLine={{ stroke: "#dfe4ec" }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "#5b6678" }} tickLine={false} axisLine={false} />
                <Tooltip formatter={(v) => [v, "Documents"]} />
                <Bar dataKey="n" fill={INK} radius={[3, 3, 0, 0]} maxBarSize={28} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <Empty>Aucun document collecté sur la période.</Empty>
          )}
        </Panel>

        <Panel title="État des sources" action={<Link href="/sources" className="text-xs text-blue-700 hover:underline">Administrer</Link>}>
          {s ? (
            <>
              <div className="flex flex-wrap gap-2">
                {Object.entries(s.sources.par_etat).map(([h, n]) => (
                  <span key={h} className="flex items-center gap-1.5 text-sm">
                    <HealthBadge health={h} /> <span className="tabular">{n}</span>
                  </span>
                ))}
              </div>
              <p className="mt-3 text-xs text-muted">{s.sources.reelles_actives} source(s) réelle(s) active(s).</p>
              <h3 className="mt-4 text-xs font-semibold uppercase tracking-wide text-muted">Indisponibles</h3>
              {s.sources.en_erreur.length ? (
                <ul className="mt-1.5 space-y-1.5">
                  {s.sources.en_erreur.slice(0, 5).map((e) => (
                    <li key={e.id} className="text-xs">
                      <span className="font-medium">{e.nom}</span>
                      {e.synthetique && <span className="ml-1 text-synth">(démo)</span>}
                      <div className="truncate text-bad" title={e.erreur}>{e.erreur}</div>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-1 text-xs text-ok">Aucune source en erreur.</p>
              )}
            </>
          ) : (
            <Empty>Chargement…</Empty>
          )}
        </Panel>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Panel title="Répartition par catégorie">{s && <HBars data={s.par_categorie} labeller={(k) => label("categories", k)} />}</Panel>
        <Panel title="Répartition géographique (pays cités)">{s && <HBars data={s.par_pays} labeller={(k) => label("countries", k)} />}</Panel>
        <Panel title="Entreprises les plus citées">{s && <HBars data={s.entreprises_plus_citees} labeller={(k) => k} />}</Panel>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-3">
        <div className="space-y-3 xl:col-span-2">
          <h2 className="text-[13px] font-semibold uppercase tracking-wide text-muted">Publications importantes récentes</h2>
          {important.data?.items.length ? (
            important.data.items.map((d) => <DocumentCard key={d.id} doc={d} saved={saved.includes(d.id)} onToggleSave={() => toggleSave(d.id)} />)
          ) : (
            <Panel><Empty>Aucune publication pertinente pour l'instant.</Empty></Panel>
          )}
        </div>
        <Panel title="Alertes non lues" action={<Link href="/alertes" className="text-xs text-blue-700 hover:underline">Tout voir</Link>}>
          {alerts.data?.length ? (
            <ul className="divide-y divide-line">
              {alerts.data.map((a) => (
                <li key={a.id} className="py-2 text-sm">
                  <div className="flex items-center gap-1.5">
                    <SeverityBadge severity={a.severity} />
                    {a.document_is_synthetic && <SyntheticBadge />}
                    <span className="ml-auto text-[11px] text-muted">{relativeTime(a.created_at)}</span>
                  </div>
                  <Link href={`/documents/${a.document_id}`} className="mt-1 block leading-snug hover:underline">{a.document_title}</Link>
                  <div className="text-[11px] text-muted">{a.rule_name} — {a.reason}</div>
                </li>
              ))}
            </ul>
          ) : (
            <Empty>Aucune alerte non lue.</Empty>
          )}
        </Panel>
      </div>
    </>
  );
}
