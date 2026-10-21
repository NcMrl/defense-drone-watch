"use client";

import { useState } from "react";

import { AdminToken } from "@/components/AdminToken";
import { HealthBadge } from "@/components/badges";
import { Empty, ErrorBox, PageTitle, Panel } from "@/components/Shell";
import { api, type Connector, type Run, type Source } from "@/lib/api";
import { formatDateTime, relativeTime } from "@/lib/format";
import { dict, label } from "@/lib/i18n";
import { useApi } from "@/lib/useApi";

const input = "w-full rounded border border-line px-2 py-1.5 text-sm";

export default function SourcesPage() {
  const sources = useApi<Source[]>("/api/sources");
  const connectors = useApi<Connector[]>("/api/connectors", null);
  const runs = useApi<Run[]>("/api/runs?limit=30");
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState<number | null>(null);
  const [form, setForm] = useState({ name: "", url: "", source_type: "media_specialise", country: "", language: "", interval_minutes: 30 });

  const act = async (fn: () => Promise<unknown>, ok: string) => {
    try {
      await fn();
      setMessage({ ok: true, text: ok });
      sources.reload();
      runs.reload();
    } catch (e) {
      setMessage({ ok: false, text: e instanceof Error ? e.message : "Échec" });
    }
  };

  const runNow = async (s: Source) => {
    setBusy(s.id);
    await act(async () => {
      const r = await api<Run>(`/api/sources/${s.id}/run`, { method: "POST", admin: true });
      if (r.status === "echec") throw new Error(`Collecte échouée : ${r.error_message}`);
      setMessage({ ok: true, text: `${s.name} : ${r.items_fetched} élément(s), ${r.docs_created} nouveau(x), ${r.duplicates} doublon(s)${r.not_modified ? " (flux non modifié)" : ""}.` });
    }, "Collecte terminée");
    setBusy(null);
  };

  const names = Object.fromEntries((sources.data ?? []).map((s) => [s.id, s.name]));

  return (
    <>
      <PageTitle title="Sources & collecte" subtitle="Catalogue administrable, état des connecteurs et journal des collectes.">
        <AdminToken />
      </PageTitle>
      {message && (
        <p className={`mb-3 rounded border px-3 py-2 text-sm ${message.ok ? "border-ok/30 bg-ok/5 text-ok" : "border-bad/30 bg-bad/5 text-bad"}`}>{message.text}</p>
      )}

      <Panel title="Sources">
        {sources.error && <ErrorBox message={sources.error} />}
        <div className="-mx-4 overflow-x-auto">
          <table className="w-full min-w-[900px] text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs text-muted">
                <th className="px-4 py-2 font-medium">Source</th>
                <th className="px-2 py-2 font-medium">Type</th>
                <th className="px-2 py-2 font-medium">État</th>
                <th className="px-2 py-2 font-medium">Vérification</th>
                <th className="px-2 py-2 font-medium">Dernière collecte réussie</th>
                <th className="px-2 py-2 font-medium">Prochaine</th>
                <th className="px-2 py-2 text-right font-medium">Docs</th>
                <th className="px-4 py-2 text-right font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {(sources.data ?? []).map((s) => (
                <tr key={s.id} className="border-b border-line/70 align-top">
                  <td className="px-4 py-2">
                    <div className="font-medium">{s.name}</div>
                    <div className="max-w-xs truncate text-xs text-muted" title={s.url}>{s.connector_type.toUpperCase()} · {s.url}</div>
                    {s.last_error && <div className="mt-0.5 max-w-md text-xs text-bad">{s.last_error} ({s.consecutive_failures} échec(s))</div>}
                  </td>
                  <td className="px-2 py-2 text-xs">{label("sourceTypes", s.source_type)}</td>
                  <td className="px-2 py-2"><HealthBadge health={s.health} /></td>
                  <td className="px-2 py-2 text-xs" title={s.verification_note ?? ""}>{s.verification_status.replace("_", " ")}</td>
                  <td className="px-2 py-2 text-xs tabular">{s.last_success_at ? `${formatDateTime(s.last_success_at)}` : "jamais"}</td>
                  <td className="px-2 py-2 text-xs">{s.enabled && !s.is_synthetic ? relativeTime(s.next_run_at) : "—"}<div className="text-muted">tous les {s.interval_minutes} min</div></td>
                  <td className="px-2 py-2 text-right tabular">{s.document_count}</td>
                  <td className="px-4 py-2 text-right">
                    {!s.is_synthetic && (
                      <div className="flex justify-end gap-1.5 text-xs">
                        <button type="button" disabled={busy === s.id} className="rounded border border-line px-2 py-1 hover:bg-paper disabled:opacity-50" onClick={() => runNow(s)}>
                          {busy === s.id ? "Collecte…" : "Collecter / tester"}
                        </button>
                        <button
                          type="button"
                          className="rounded border border-line px-2 py-1 hover:bg-paper"
                          onClick={() => act(() => api(`/api/sources/${s.id}`, { method: "PATCH", body: JSON.stringify({ enabled: !s.enabled }), admin: true }), s.enabled ? "Source désactivée" : "Source activée")}
                        >
                          {s.enabled ? "Désactiver" : "Activer"}
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {sources.data && !sources.data.length && <Empty>Aucune source. Importez le catalogue initial : python -m app.cli import-catalog</Empty>}
      </Panel>

      <div className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Panel title="Ajouter une source (flux RSS / Atom)">
          <form
            className="grid grid-cols-2 gap-2.5"
            onSubmit={(e) => {
              e.preventDefault();
              act(
                () => api("/api/sources", {
                  method: "POST",
                  admin: true,
                  body: JSON.stringify({ ...form, country: form.country || null, language: form.language || null, interval_minutes: Number(form.interval_minutes) }),
                }),
                "Source ajoutée. Lancez « Collecter / tester » pour la vérifier.",
              );
            }}
          >
            <label className="col-span-2 text-xs text-muted">Nom<input required minLength={2} className={`${input} mt-1`} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
            <label className="col-span-2 text-xs text-muted">URL du flux<input required type="url" className={`${input} mt-1`} value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} placeholder="https://…/feed" /></label>
            <label className="text-xs text-muted">Type de source
              <select className={`${input} mt-1`} value={form.source_type} onChange={(e) => setForm({ ...form, source_type: e.target.value })}>
                {Object.entries(dict().sourceTypes).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </label>
            <label className="text-xs text-muted">Fréquence (minutes)<input type="number" min={5} className={`${input} mt-1`} value={form.interval_minutes} onChange={(e) => setForm({ ...form, interval_minutes: Number(e.target.value) })} /></label>
            <label className="text-xs text-muted">Pays de la source (code)<input maxLength={8} className={`${input} mt-1`} value={form.country} onChange={(e) => setForm({ ...form, country: e.target.value.toUpperCase() })} placeholder="FR" /></label>
            <label className="text-xs text-muted">Langue (code)<input maxLength={8} className={`${input} mt-1`} value={form.language} onChange={(e) => setForm({ ...form, language: e.target.value.toLowerCase() })} placeholder="fr" /></label>
            <button type="submit" className="col-span-2 mt-1 rounded bg-ink px-3 py-1.5 text-sm font-medium text-white">Ajouter</button>
          </form>
        </Panel>

        <Panel title="Connecteurs">
          <ul className="space-y-3">
            {(connectors.data ?? []).map((c) => (
              <li key={c.type} className="text-sm">
                <div className="flex items-center gap-2">
                  <span className="font-medium">{c.label}</span>
                  <span className={`rounded px-1.5 py-0.5 text-[11px] ${c.configured ? "bg-ok/10 text-ok" : "bg-warn/10 text-warn"}`}>
                    {c.configured ? "Opérationnel" : c.implemented ? "Non configuré" : "Non implémenté"}
                  </span>
                </div>
                {!c.configured && <p className="text-xs text-warn">{c.status_message}</p>}
                <p className="text-xs text-muted"><strong className="font-medium">Accès :</strong> {c.access_method}</p>
                <p className="text-xs text-muted"><strong className="font-medium">Limites :</strong> {c.limits}</p>
                <p className="text-xs text-muted"><strong className="font-medium">Conditions :</strong> {c.terms}</p>
              </li>
            ))}
          </ul>
        </Panel>
      </div>

      <Panel title="Journal des collectes (30 dernières)" className="mt-4">
        {runs.data?.length ? (
          <div className="-mx-4 overflow-x-auto">
            <table className="w-full min-w-[760px] text-xs">
              <thead>
                <tr className="border-b border-line text-left text-muted">
                  <th className="px-4 py-1.5 font-medium">Début</th>
                  <th className="px-2 py-1.5 font-medium">Source</th>
                  <th className="px-2 py-1.5 font-medium">Statut</th>
                  <th className="px-2 py-1.5 text-right font-medium">Éléments</th>
                  <th className="px-2 py-1.5 text-right font-medium">Nouveaux</th>
                  <th className="px-2 py-1.5 text-right font-medium">Doublons</th>
                  <th className="px-2 py-1.5 text-right font-medium">Durée</th>
                  <th className="px-4 py-1.5 font-medium">Erreur</th>
                </tr>
              </thead>
              <tbody>
                {runs.data.map((r) => (
                  <tr key={r.id} className="border-b border-line/60">
                    <td className="px-4 py-1.5 tabular">{formatDateTime(r.started_at)}</td>
                    <td className="px-2 py-1.5">{names[r.source_id] ?? r.source_id}</td>
                    <td className={`px-2 py-1.5 ${r.status === "echec" ? "text-bad" : r.status === "succes" ? "text-ok" : "text-warn"}`}>
                      {r.status}{r.not_modified ? " (304)" : ""}
                    </td>
                    <td className="px-2 py-1.5 text-right tabular">{r.items_fetched}</td>
                    <td className="px-2 py-1.5 text-right tabular">{r.docs_created}</td>
                    <td className="px-2 py-1.5 text-right tabular">{r.duplicates}</td>
                    <td className="px-2 py-1.5 text-right tabular">{r.duration_ms != null ? `${r.duration_ms} ms` : "—"}</td>
                    <td className="max-w-sm truncate px-4 py-1.5 text-bad" title={r.error_message ?? ""}>{r.error_message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty>Aucune collecte exécutée.</Empty>
        )}
      </Panel>
    </>
  );
}
