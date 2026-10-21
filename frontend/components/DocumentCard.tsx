"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import type { DocumentItem } from "@/lib/api";
import { formatDateTime, isNew, safeExternalUrl } from "@/lib/format";
import { label } from "@/lib/i18n";

import { ConfidenceBadge, StatusBadge, SyntheticBadge, Tag } from "./badges";

const SAVED_KEY = "ddw_saved_documents";

function readSaved(): number[] {
  try {
    return JSON.parse(window.localStorage.getItem(SAVED_KEY) ?? "[]");
  } catch {
    return [];
  }
}

export function useSaved(): [number[], (id: number) => void] {
  const [saved, setSaved] = useState<number[]>([]);
  useEffect(() => setSaved(readSaved()), []);
  const toggle = (id: number) => {
    const next = saved.includes(id) ? saved.filter((x) => x !== id) : [...saved, id];
    setSaved(next);
    try {
      window.localStorage.setItem(SAVED_KEY, JSON.stringify(next));
    } catch {
      /* stockage indisponible */
    }
  };
  return [saved, toggle];
}

export function DocumentCard({ doc, saved, onToggleSave }: { doc: DocumentItem; saved: boolean; onToggleSave: () => void }) {
  const href = safeExternalUrl(doc.canonical_url);
  return (
    <article className={`rounded-md border bg-white p-4 ${doc.is_synthetic ? "border-synth/40" : "border-line"}`}>
      <div className="mb-1.5 flex flex-wrap items-center gap-1.5">
        {doc.is_synthetic && <SyntheticBadge />}
        {isNew(doc.first_seen_at) && <span className="rounded bg-ink px-1.5 py-0.5 text-[11px] font-medium text-white">Nouveau</span>}
        <ConfidenceBadge score={doc.confidence} />
        <StatusBadge status={doc.status} />
        {doc.occurrence_count > 1 && (
          <span className="text-[11px] text-muted">{doc.occurrence_count} sources associées</span>
        )}
      </div>

      <h3 className="text-[15px] font-semibold leading-snug">
        <Link href={`/documents/${doc.id}`} className="hover:underline">
          {doc.title}
        </Link>
      </h3>
      {doc.summary && <p className="mt-1 line-clamp-2 text-sm text-slate-700">{doc.summary}</p>}

      <dl className="mt-2 grid grid-cols-1 gap-x-4 gap-y-0.5 text-xs text-muted sm:grid-cols-3">
        <div>
          <dt className="inline">Source : </dt>
          <dd className="inline text-ink">{doc.source_name ?? doc.domain}</dd>
        </div>
        <div>
          <dt className="inline">Publié : </dt>
          <dd className="inline tabular">{formatDateTime(doc.published_at)}</dd>
        </div>
        <div>
          <dt className="inline">Collecté : </dt>
          <dd className="inline tabular">{formatDateTime(doc.first_seen_at)}</dd>
        </div>
      </dl>

      {(doc.categories.length > 0 || doc.entities.length > 0) && (
        <div className="mt-2 flex flex-wrap gap-1">
          {doc.categories.map((c) => (
            <Tag key={c}>{label("categories", c)}</Tag>
          ))}
          {doc.entities.map((e) => (
            <span key={`${e.kind}-${e.id}`} className="rounded bg-sky-50 px-1.5 py-0.5 text-[11px] text-sky-900 ring-1 ring-sky-200">
              {e.name}
            </span>
          ))}
        </div>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-3 text-xs">
        {href ? (
          <a href={href} target="_blank" rel="noopener noreferrer nofollow" className="font-medium text-blue-700 hover:underline">
            Ouvrir la source ↗
          </a>
        ) : (
          <span className="text-muted">Lien source invalide</span>
        )}
        <Link href={`/documents/${doc.id}`} className="text-blue-700 hover:underline">
          Fiche & sources associées
        </Link>
        <button type="button" onClick={onToggleSave} className="ml-auto rounded border border-line px-2 py-1 text-muted hover:bg-paper" aria-pressed={saved}>
          {saved ? "★ Enregistré" : "☆ Enregistrer"}
        </button>
      </div>
    </article>
  );
}
