"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { DocumentCard, useSaved } from "@/components/DocumentCard";
import { Empty, ErrorBox, PageTitle, Panel } from "@/components/Shell";
import { api, API_URL, type Company, type DocumentPage, type Source } from "@/lib/api";
import { buildQuery } from "@/lib/format";
import { dict } from "@/lib/i18n";
import { useApi } from "@/lib/useApi";

const FIELDS = [
  "q", "category", "country", "language", "status", "source_id", "company_id", "min_confidence",
  "published_from", "published_to", "collected_from", "collected_to", "synthetic", "sort",
] as const;
type Field = (typeof FIELDS)[number];
type Filters = Partial<Record<Field, string>>;

const input = "w-full rounded border border-line bg-white px-2 py-1.5 text-sm";

function FluxInner() {
  const router = useRouter();
  const params = useSearchParams();
  const initial: Filters = {};
  FIELDS.forEach((f) => {
    const v = params.get(f);
    if (v) initial[f] = v;
  });
  const [draft, setDraft] = useState<Filters>(initial);
  const page = Number(params.get("page") ?? "1");
  const query = buildQuery({ ...initial, page, page_size: 20 });
  const result = useApi<DocumentPage>(`/api/documents${query}`);
  const sources = useApi<Source[]>("/api/sources", null);
  const companies = useApi<Company[]>("/api/companies", null);
  const views = useApi<{ id: number; name: string; filters: Filters }[]>("/api/views", null);
  const [saved, toggleSave] = useSaved();
  const [viewMsg, setViewMsg] = useState<string | null>(null);
  const d = dict();

  useEffect(() => setDraft(initial), [params.toString()]); // eslint-disable-line react-hooks/exhaustive-deps

  const apply = (f: Filters, p = 1) => {
    const normalized: Filters = { ...f };
    // Une date de fin saisie seule couvre toute la journée
    (["published_to", "collected_to"] as const).forEach((k) => {
      const v = normalized[k];
      if (v && v.length === 10) normalized[k] = `${v}T23:59:59Z`;
    });
    router.push(`/flux${buildQuery({ ...normalized, page: p > 1 ? p : undefined })}`);
  };
  const set = (k: Field) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setDraft({ ...draft, [k]: e.target.value });

  const saveView = async () => {
    const name = window.prompt("Nom de la vue sauvegardée ?");
    if (!name) return;
    try {
      await api("/api/views", { method: "POST", body: JSON.stringify({ name, filters: initial }), admin: true });
      setViewMsg("Vue enregistrée.");
      views.reload();
    } catch (e) {
      setViewMsg(e instanceof Error ? e.message : "Échec");
    }
  };

  const total = result.data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / 20));

  return (
    <>
      <PageTitle title="Flux & recherche" subtitle='Syntaxe : mots-clés, "expression exacte", -exclusion, a or b. Accents ignorés.'>
        <div className="flex gap-2 text-xs">
          <a className="rounded border border-line bg-white px-2.5 py-1.5 hover:bg-paper" href={`${API_URL}/api/export${buildQuery({ ...initial, format: "csv" })}`}>Export CSV</a>
          <a className="rounded border border-line bg-white px-2.5 py-1.5 hover:bg-paper" href={`${API_URL}/api/export${buildQuery({ ...initial, format: "json" })}`}>Export JSON</a>
        </div>
      </PageTitle>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[280px_1fr]">
        <form
          className="space-y-3"
          onSubmit={(e) => {
            e.preventDefault();
            apply(draft);
          }}
        >
          <Panel>
            <label className="block text-xs font-medium text-muted" htmlFor="q">Recherche plein texte</label>
            <input id="q" className={`${input} mt-1`} value={draft.q ?? ""} onChange={set("q")} placeholder='ex. "munitions rôdeuses" -salon' />

            <div className="mt-3 grid grid-cols-1 gap-2.5">
              <Select label="Catégorie" value={draft.category} onChange={set("category")} options={Object.entries(d.categories)} />
              <Select label="Pays cité" value={draft.country} onChange={set("country")} options={Object.entries(d.countries)} />
              <Select label="Langue" value={draft.language} onChange={set("language")} options={[["fr", "Français"], ["en", "Anglais"]]} />
              <Select label="Statut" value={draft.status} onChange={set("status")} options={Object.entries(d.statuses)} />
              <Select label="Source" value={draft.source_id} onChange={set("source_id")} options={(sources.data ?? []).map((s) => [String(s.id), s.name])} />
              <Select label="Entreprise" value={draft.company_id} onChange={set("company_id")} options={(companies.data ?? []).map((c) => [String(c.id), c.name])} />
              <Select label="Confiance minimale" value={draft.min_confidence} onChange={set("min_confidence")} options={[["0.5", "≥ moyenne (0,5)"], ["0.75", "≥ élevée (0,75)"]]} />
              <DateRange label="Publication" from={draft.published_from} to={draft.published_to} onFrom={set("published_from")} onTo={set("published_to")} />
              <DateRange label="Collecte" from={draft.collected_from} to={draft.collected_to} onFrom={set("collected_from")} onTo={set("collected_to")} />
              <Select label="Données synthétiques" value={draft.synthetic} onChange={set("synthetic")} placeholder="Incluses" options={[["exclude", "Exclues"], ["only", "Uniquement"]]} />
              <Select label="Tri" value={draft.sort} onChange={set("sort")} placeholder="Plus récents (collecte)" options={[["publication", "Date de publication"], ["pertinence", "Pertinence (avec recherche)"]]} />
            </div>
            <div className="mt-4 flex gap-2">
              <button type="submit" className="flex-1 rounded bg-ink px-3 py-1.5 text-sm font-medium text-white hover:bg-ink-2">Appliquer</button>
              <button type="button" className="rounded border border-line px-3 py-1.5 text-sm" onClick={() => apply({})}>Réinitialiser</button>
            </div>
          </Panel>

          <Panel title="Vues sauvegardées" action={<button type="button" onClick={saveView} className="text-xs text-blue-700 hover:underline">+ Enregistrer la vue</button>}>
            {viewMsg && <p className="mb-2 text-xs text-muted">{viewMsg}</p>}
            {views.data?.length ? (
              <ul className="space-y-1 text-sm">
                {views.data.map((v) => (
                  <li key={v.id}>
                    <button type="button" className="text-left text-blue-700 hover:underline" onClick={() => apply(v.filters)}>{v.name}</button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-muted">Aucune vue. L'enregistrement nécessite le jeton d'administration (page Sources).</p>
            )}
          </Panel>
        </form>

        <div className="min-w-0 space-y-3">
          <div className="flex items-center justify-between text-xs text-muted">
            <span className="tabular">{result.loading && !result.data ? "Chargement…" : `${total} résultat(s)`}</span>
            {pages > 1 && (
              <span className="flex items-center gap-2">
                <button type="button" disabled={page <= 1} className="rounded border border-line px-2 py-1 disabled:opacity-40" onClick={() => apply(initial, page - 1)}>‹ Préc.</button>
                <span className="tabular">{page} / {pages}</span>
                <button type="button" disabled={page >= pages} className="rounded border border-line px-2 py-1 disabled:opacity-40" onClick={() => apply(initial, page + 1)}>Suiv. ›</button>
              </span>
            )}
          </div>
          {result.error && <ErrorBox message={result.error} />}
          {result.data?.items.map((doc) => (
            <DocumentCard key={doc.id} doc={doc} saved={saved.includes(doc.id)} onToggleSave={() => toggleSave(doc.id)} />
          ))}
          {result.data && !result.data.items.length && <Panel><Empty>Aucun document ne correspond à ces critères.</Empty></Panel>}
        </div>
      </div>
    </>
  );
}

function Select({ label, value, onChange, options, placeholder = "Tous" }: {
  label: string; value?: string; onChange: (e: React.ChangeEvent<HTMLSelectElement>) => void; options: [string, string][]; placeholder?: string;
}) {
  return (
    <label className="block text-xs font-medium text-muted">
      {label}
      <select className={`${input} mt-1`} value={value ?? ""} onChange={onChange}>
        <option value="">{placeholder}</option>
        {options.map(([v, l]) => (
          <option key={v} value={v}>{l}</option>
        ))}
      </select>
    </label>
  );
}

function DateRange({ label, from, to, onFrom, onTo }: {
  label: string; from?: string; to?: string; onFrom: (e: React.ChangeEvent<HTMLInputElement>) => void; onTo: (e: React.ChangeEvent<HTMLInputElement>) => void;
}) {
  return (
    <fieldset className="text-xs font-medium text-muted">
      <legend>{label} (du / au)</legend>
      <div className="mt-1 grid grid-cols-2 gap-1.5">
        <input type="date" aria-label={`${label} — début`} className={input} value={from?.slice(0, 10) ?? ""} onChange={onFrom} />
        <input type="date" aria-label={`${label} — fin`} className={input} value={to?.slice(0, 10) ?? ""} onChange={onTo} />
      </div>
    </fieldset>
  );
}

export default function FluxPage() {
  return (
    <Suspense fallback={<p className="text-sm text-muted">Chargement…</p>}>
      <FluxInner />
    </Suspense>
  );
}
