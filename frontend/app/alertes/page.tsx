"use client";

import Link from "next/link";
import { useState } from "react";

import { AdminToken } from "@/components/AdminToken";
import { SeverityBadge, SyntheticBadge } from "@/components/badges";
import { Empty, PageTitle, Panel } from "@/components/Shell";
import { api, type Alert, type Rule } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { dict, label } from "@/lib/i18n";
import { useApi } from "@/lib/useApi";

const input = "w-full rounded border border-line px-2 py-1.5 text-sm";
const split = (v: string) => v.split(",").map((x) => x.trim()).filter(Boolean);

type DryRun = { documents_evalues: number; correspondances: number; exemples: { document_id: number; titre: string; raison: string; synthetique: boolean }[] };

export default function AlertesPage() {
  const alerts = useApi<Alert[]>("/api/alerts?limit=100");
  const rules = useApi<Rule[]>("/api/rules", null);
  const [form, setForm] = useState({ name: "", keywords: "", exclude_keywords: "", category: "", countries: "", severity: "important" });
  const [dry, setDry] = useState<DryRun | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const payload = () => ({
    name: form.name || "Simulation",
    keywords: split(form.keywords),
    exclude_keywords: split(form.exclude_keywords),
    categories: form.category ? [form.category] : [],
    countries: split(form.countries).map((c) => c.toUpperCase()),
    severity: form.severity,
  });

  const run = async (fn: () => Promise<unknown>, ok: string) => {
    try {
      await fn();
      setMsg({ ok: true, text: ok });
      rules.reload();
      alerts.reload();
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : "Échec" });
    }
  };

  const ruleNames = Object.fromEntries((rules.data ?? []).map((r) => [r.id, r.name]));

  return (
    <>
      <PageTitle title="Alertes & règles de veille" subtitle="Les règles sont évaluées à l'ingestion de chaque nouveau document. Une règle ne notifie qu'une fois par document, doublons fusionnés compris.">
        <AdminToken />
      </PageTitle>
      {msg && <p className={`mb-3 rounded border px-3 py-2 text-sm ${msg.ok ? "border-ok/30 bg-ok/5 text-ok" : "border-bad/30 bg-bad/5 text-bad"}`}>{msg.text}</p>}

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Panel title="Alertes" className="xl:col-span-2">
          {alerts.data?.length ? (
            <ul className="divide-y divide-line">
              {alerts.data.map((a) => (
                <li key={a.id} className={`flex gap-3 py-2.5 ${a.read_at ? "opacity-60" : ""}`}>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <SeverityBadge severity={a.severity} />
                      {a.document_is_synthetic && <SyntheticBadge />}
                      <span className="text-xs text-muted">{a.rule_name} · {formatDateTime(a.created_at)}</span>
                    </div>
                    <Link href={`/documents/${a.document_id}`} className="mt-1 block text-sm font-medium hover:underline">{a.document_title}</Link>
                    <div className="text-xs text-muted">Déclenchée par : {a.reason}</div>
                  </div>
                  {!a.read_at && (
                    <button type="button" className="self-start rounded border border-line px-2 py-1 text-xs hover:bg-paper" onClick={() => run(() => api(`/api/alerts/${a.id}/read`, { method: "POST" }), "Alerte marquée comme lue")}>
                      Marquer lue
                    </button>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <Empty>Aucune alerte.</Empty>
          )}
          <p className="mt-3 border-t border-line pt-2 text-[11px] text-muted">
            Notifications dans l'application uniquement. L'envoi par e-mail et les intégrations de messagerie sont prévus en phase 5.
          </p>
        </Panel>

        <div className="space-y-4">
          <Panel title="Nouvelle règle">
            <form className="space-y-2.5" onSubmit={(e) => { e.preventDefault(); run(() => api("/api/rules", { method: "POST", body: JSON.stringify(payload()), admin: true }), "Règle créée"); }}>
              <label className="block text-xs text-muted">Nom<input required minLength={2} className={`${input} mt-1`} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
              <label className="block text-xs text-muted">Mots-clés (séparés par des virgules, l'un d'eux suffit)<input className={`${input} mt-1`} value={form.keywords} onChange={(e) => setForm({ ...form, keywords: e.target.value })} placeholder="munitions rôdeuses, loitering munition" /></label>
              <label className="block text-xs text-muted">Termes exclus<input className={`${input} mt-1`} value={form.exclude_keywords} onChange={(e) => setForm({ ...form, exclude_keywords: e.target.value })} /></label>
              <label className="block text-xs text-muted">Catégorie
                <select className={`${input} mt-1`} value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
                  <option value="">Toutes</option>
                  {Object.entries(dict().categories).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select>
              </label>
              <label className="block text-xs text-muted">Pays cités (codes, virgules)<input className={`${input} mt-1`} value={form.countries} onChange={(e) => setForm({ ...form, countries: e.target.value })} placeholder="FR, EU" /></label>
              <label className="block text-xs text-muted">Importance
                <select className={`${input} mt-1`} value={form.severity} onChange={(e) => setForm({ ...form, severity: e.target.value })}>
                  {Object.entries(dict().severities).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select>
              </label>
              <div className="flex gap-2 pt-1">
                <button type="button" className="flex-1 rounded border border-line px-3 py-1.5 text-sm" onClick={() => run(async () => setDry(await api<DryRun>("/api/rules/test", { method: "POST", body: JSON.stringify(payload()) })), "Simulation effectuée")}>
                  Tester (sans créer d'alerte)
                </button>
                <button type="submit" className="flex-1 rounded bg-ink px-3 py-1.5 text-sm font-medium text-white">Créer</button>
              </div>
            </form>
            {dry && (
              <div className="mt-3 border-t border-line pt-2 text-xs">
                <p><strong>{dry.correspondances}</strong> correspondance(s) sur {dry.documents_evalues} document(s) récents.</p>
                <ul className="mt-1 space-y-1">
                  {dry.exemples.slice(0, 5).map((x) => (
                    <li key={x.document_id}><Link href={`/documents/${x.document_id}`} className="text-blue-700 hover:underline">{x.titre}</Link> <span className="text-muted">— {x.raison}</span></li>
                  ))}
                </ul>
              </div>
            )}
          </Panel>

          <Panel title="Règles actives">
            {rules.data?.length ? (
              <ul className="space-y-2 text-sm">
                {rules.data.map((r) => (
                  <li key={r.id} className="flex items-start gap-2">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-1.5"><SeverityBadge severity={r.severity} /><span className="font-medium">{ruleNames[r.id]}</span></div>
                      <div className="text-xs text-muted">
                        {[r.keywords.length && `mots-clés : ${r.keywords.join(", ")}`, r.categories.length && `catégories : ${r.categories.map((c) => label("categories", c)).join(", ")}`, r.countries.length && `pays : ${r.countries.join(", ")}`, r.exclude_keywords.length && `exclus : ${r.exclude_keywords.join(", ")}`].filter(Boolean).join(" · ")}
                      </div>
                    </div>
                    <button type="button" className="text-xs text-bad hover:underline" onClick={() => run(() => api(`/api/rules/${r.id}`, { method: "DELETE", admin: true }), "Règle supprimée")}>Supprimer</button>
                  </li>
                ))}
              </ul>
            ) : (
              <Empty>Aucune règle.</Empty>
            )}
          </Panel>
        </div>
      </div>
    </>
  );
}
