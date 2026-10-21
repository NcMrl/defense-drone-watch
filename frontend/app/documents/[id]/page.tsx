"use client";

import Link from "next/link";
import { useParams } from "next/navigation";

import { ConfidenceBadge, StatusBadge, SyntheticBadge, Tag } from "@/components/badges";
import { Empty, ErrorBox, PageTitle, Panel } from "@/components/Shell";
import type { DocumentDetail } from "@/lib/api";
import { formatDateTime, formatDelay, safeExternalUrl } from "@/lib/format";
import { label } from "@/lib/i18n";
import { useApi } from "@/lib/useApi";

const COMPONENT_LABELS: Record<string, string> = {
  fiabilite_source: "Fiabilité de la source",
  solidite_preuve: "Solidité de la preuve",
  corroboration: "Corroboration",
  fraicheur: "Fraîcheur",
};

export default function DocumentPage() {
  const { id } = useParams<{ id: string }>();
  const { data: doc, error, loading } = useApi<DocumentDetail>(`/api/documents/${encodeURIComponent(id)}`);

  if (error) return <ErrorBox message={error} />;
  if (loading || !doc) return <p className="text-sm text-muted">Chargement…</p>;

  const href = safeExternalUrl(doc.canonical_url);
  const details = doc.confidence_details;
  const first = doc.occurrences[0];

  return (
    <>
      <div className="mb-2 text-xs">
        <Link href="/flux" className="text-blue-700 hover:underline">← Flux</Link>
      </div>
      {doc.is_synthetic && (
        <div className="mb-3 rounded border border-synth/40 bg-synth/10 px-3 py-2 text-sm text-synth">
          Ce document est <strong>fictif</strong> (mode démonstration). Il ne décrit aucun fait réel.
        </div>
      )}
      <PageTitle title={doc.title}>
        {href && (
          <a href={href} target="_blank" rel="noopener noreferrer nofollow" className="rounded bg-ink px-3 py-1.5 text-sm font-medium text-white hover:bg-ink-2">
            Ouvrir le document source ↗
          </a>
        )}
      </PageTitle>

      <div className="mb-4 flex flex-wrap items-center gap-1.5">
        {doc.is_synthetic && <SyntheticBadge />}
        <ConfidenceBadge score={doc.confidence} />
        <StatusBadge status={doc.status} />
        {doc.categories.map((c) => <Tag key={c}>{label("categories", c)}</Tag>)}
        {doc.countries.map((c) => <Tag key={c}>{label("countries", c)}</Tag>)}
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <div className="space-y-4 xl:col-span-2">
          <Panel title="Résumé fourni par la source">
            {doc.summary ? <p className="text-sm leading-relaxed">{doc.summary}</p> : <Empty>Aucun résumé fourni par le flux.</Empty>}
            <p className="mt-3 text-[11px] text-muted">
              Texte issu du flux de la source (titre et chapô). Le texte intégral n'est pas stocké ; consultez la publication d'origine.
              Langue d'origine : {doc.language ?? "inconnue"}.
            </p>
          </Panel>

          <Panel title={`Sources associées (${doc.occurrences.length})`}>
            <ol className="space-y-3">
              {doc.occurrences.map((o, i) => {
                const oh = safeExternalUrl(o.url);
                return (
                  <li key={o.id} className="flex gap-3 text-sm">
                    <span className="tabular mt-0.5 h-5 w-5 shrink-0 rounded-full bg-paper text-center text-[11px] leading-5 text-muted">{i + 1}</span>
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-medium">{o.source_name}</span>
                        <span className="rounded bg-paper px-1.5 py-0.5 text-[11px] text-muted">
                          {label("matchTypes", o.match_type)}
                          {o.match_score != null && o.match_type === "titre_similaire" ? ` (${Math.round(o.match_score * 100)} %)` : ""}
                        </span>
                      </div>
                      {o.raw_title && o.raw_title !== doc.title && <div className="text-xs text-slate-600">« {o.raw_title} »</div>}
                      <div className="text-xs text-muted">
                        Découvert le {formatDateTime(o.discovered_at)} · publié le {formatDateTime(o.published_at)}
                      </div>
                      {oh && <a href={oh} target="_blank" rel="noopener noreferrer nofollow" className="break-all text-xs text-blue-700 hover:underline">{oh}</a>}
                    </div>
                  </li>
                );
              })}
            </ol>
            <p className="mt-3 text-[11px] text-muted">
              Plusieurs reprises d'un même communiqué ne constituent pas des corroborations indépendantes. Les contradictions seront
              détectées en phase 4 (analyse des affirmations).
            </p>
          </Panel>

          {doc.versions.length > 0 && (
            <Panel title="Historique des versions">
              <ul className="space-y-2 text-sm">
                {doc.versions.map((v) => (
                  <li key={v.version}>
                    <span className="font-medium">Version {v.version}</span> — remplacée le {formatDateTime(v.recorded_at)}
                    <div className="text-xs text-muted">{v.summary}</div>
                  </li>
                ))}
                <li className="text-xs text-muted">Version actuelle : {doc.version}</li>
              </ul>
            </Panel>
          )}
        </div>

        <div className="space-y-4">
          <Panel title="Horodatage">
            <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 text-sm">
              <dt className="text-muted">Publication</dt><dd className="tabular">{formatDateTime(doc.published_at)}</dd>
              <dt className="text-muted">Première collecte</dt><dd className="tabular">{formatDateTime(doc.first_seen_at)}</dd>
              <dt className="text-muted">Dernière vérification</dt><dd className="tabular">{formatDateTime(doc.last_checked_at)}</dd>
              <dt className="text-muted">Dernière mise à jour</dt><dd className="tabular">{formatDateTime(doc.updated_at)}</dd>
              <dt className="text-muted">Retard de collecte</dt><dd>{formatDelay(doc.collection_delay_minutes)}</dd>
              <dt className="text-muted">Première source</dt><dd>{first?.source_name ?? "—"}</dd>
            </dl>
          </Panel>

          <Panel title="Explication du score de confiance">
            <p className="text-sm">
              Score : <strong className="tabular">{details.score != null ? Math.round(details.score * 100) : "—"}</strong> / 100
            </p>
            <ul className="mt-2 space-y-2">
              {Object.entries(details.composantes ?? {}).map(([k, c]) => (
                <li key={k} className="text-xs">
                  <div className="flex justify-between">
                    <span className="font-medium text-ink">{COMPONENT_LABELS[k] ?? k}</span>
                    <span className="tabular">
                      {c.valeur != null ? Math.round(c.valeur * 100) : "non évaluée"}
                      {details.ponderations?.[k] != null && <span className="text-muted"> · poids {details.ponderations[k]}</span>}
                    </span>
                  </div>
                  <div className="text-muted">{c.explication}</div>
                </li>
              ))}
            </ul>
            {details.avertissement && <p className="mt-3 border-t border-line pt-2 text-[11px] text-muted">{details.avertissement}</p>}
          </Panel>

          {details.classification && Object.keys(details.classification).length > 0 && (
            <Panel title="Pourquoi ces catégories">
              <ul className="space-y-1 text-xs">
                {Object.entries(details.classification).map(([cat, terms]) => (
                  <li key={cat}><span className="font-medium">{label("categories", cat)}</span> : {terms.join(", ")}</li>
                ))}
              </ul>
            </Panel>
          )}

          {doc.entities.length > 0 && (
            <Panel title="Entités détectées">
              <ul className="space-y-1 text-sm">
                {doc.entities.map((e) => (
                  <li key={`${e.kind}-${e.id}`}>
                    {e.kind === "entreprise" ? (
                      <Link href={`/flux?company_id=${e.id}`} className="text-blue-700 hover:underline">{e.name}</Link>
                    ) : (
                      e.name
                    )}{" "}
                    <span className="text-xs text-muted">({e.kind})</span>
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-[11px] text-muted">Détection par dictionnaire de noms déclarés, non par IA.</p>
            </Panel>
          )}
        </div>
      </div>
    </>
  );
}
