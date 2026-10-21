// Client de l'API backend. Toutes les données affichées proviennent de l'API ; rien n'est inventé côté interface.

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
export const REFRESH_MS = 60_000; // actualisation périodique (pas de temps réel)

export type EntityRef = { id: number; name: string; kind: "entreprise" | "produit"; is_synthetic: boolean };

export type DocumentItem = {
  id: number;
  title: string;
  summary: string | null;
  canonical_url: string;
  domain: string;
  author: string | null;
  published_at: string | null;
  first_seen_at: string;
  last_checked_at: string;
  updated_at: string;
  language: string | null;
  source_country: string | null;
  countries: string[];
  categories: string[];
  event_type: string | null;
  relevance: number;
  confidence: number | null;
  status: string;
  version: number;
  is_synthetic: boolean;
  occurrence_count: number;
  source_name: string | null;
  collection_delay_minutes: number | null;
  entities: EntityRef[];
};

export type Occurrence = {
  id: number;
  source_id: number;
  source_name: string;
  url: string;
  raw_title: string | null;
  published_at: string | null;
  discovered_at: string;
  match_type: string;
  match_score: number | null;
};

export type ConfidenceComponent = { valeur: number | null; explication: string };

export type DocumentDetail = DocumentItem & {
  confidence_details: {
    score?: number | null;
    composantes?: Record<string, ConfidenceComponent>;
    ponderations?: Record<string, number>;
    non_evaluees?: string[];
    avertissement?: string;
    classification?: Record<string, string[]>;
  };
  occurrences: Occurrence[];
  versions: { version: number; title: string; summary: string | null; recorded_at: string }[];
};

export type DocumentPage = { total: number; page: number; page_size: number; items: DocumentItem[]; generated_at: string };

export type Source = {
  id: number;
  name: string;
  url: string;
  homepage: string | null;
  connector_type: string;
  source_type: string;
  reliability: number | null;
  country: string | null;
  language: string | null;
  categories: string[];
  enabled: boolean;
  priority: number;
  interval_minutes: number;
  verification_status: string;
  verification_note: string | null;
  is_synthetic: boolean;
  last_run_at: string | null;
  last_success_at: string | null;
  next_run_at: string | null;
  last_error: string | null;
  consecutive_failures: number;
  health: string;
  document_count: number;
};

export type Connector = {
  type: string;
  label: string;
  implemented: boolean;
  configured: boolean;
  status_message: string;
  access_method: string;
  limits: string;
  terms: string;
  default_interval_minutes: number;
  required_env: string[];
};

export type Run = {
  id: number;
  source_id: number;
  started_at: string;
  finished_at: string | null;
  status: string;
  not_modified: boolean;
  items_fetched: number;
  docs_created: number;
  docs_updated: number;
  duplicates: number;
  errors: number;
  error_message: string | null;
  error_kind: string | null;
  duration_ms: number | null;
};

export type Rule = {
  id: number;
  name: string;
  keywords: string[];
  exclude_keywords: string[];
  categories: string[];
  countries: string[];
  company_ids: number[];
  severity: string;
  enabled: boolean;
  created_at: string;
};

export type Alert = {
  id: number;
  rule_id: number;
  rule_name: string;
  document_id: number;
  document_title: string;
  document_is_synthetic: boolean;
  severity: string;
  reason: string;
  created_at: string;
  read_at: string | null;
};

export type Company = { id: number; name: string; aliases: string[]; country: string | null; website: string | null; is_synthetic: boolean; document_count: number };

export type Stats = {
  genere_le: string;
  mode_actualisation: string;
  totaux: {
    documents: number;
    nouveaux_24h: number;
    pertinents_aujourdhui: number;
    alertes_prioritaires_non_lues: number;
    occurrences: number;
    taux_deduplication: number | null;
  };
  sources: {
    par_etat: Record<string, number>;
    reelles_actives: number;
    derniere_collecte_reussie: string | null;
    en_erreur: { id: number; nom: string; erreur: string; echecs_consecutifs: number; synthetique: boolean }[];
  };
  par_categorie: { cle: string; n: number }[];
  par_pays: { cle: string; n: number }[];
  par_jour: { cle: string; n: number }[];
  par_jour_publication: { cle: string; n: number }[];
  entreprises_plus_citees: { cle: string; n: number }[];
};

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

const TOKEN_KEY = "ddw_admin_token";

export function getAdminToken(): string | null {
  try {
    return typeof window === "undefined" ? null : window.sessionStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setAdminToken(token: string | null): void {
  try {
    if (token) window.sessionStorage.setItem(TOKEN_KEY, token);
    else window.sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    /* stockage indisponible : le jeton reste en mémoire uniquement */
  }
}

export async function api<T>(path: string, init: RequestInit & { admin?: boolean } = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (init.admin) {
    const token = getAdminToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
  }
  const resp = await fetch(`${API_URL}${path}`, { ...init, headers, cache: "no-store" });
  if (!resp.ok) {
    let message = `Erreur ${resp.status}`;
    try {
      const body = await resp.json();
      if (typeof body.detail === "string") message = body.detail;
    } catch {
      /* corps non JSON */
    }
    throw new ApiError(resp.status, message);
  }
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}
