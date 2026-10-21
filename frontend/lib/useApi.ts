"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { api, REFRESH_MS } from "./api";

export type ApiState<T> = {
  data: T | null;
  error: string | null;
  loading: boolean;
  fetchedAt: Date | null;
  reload: () => void;
};

/** Charge une ressource et la rafraîchit périodiquement (actualisation périodique, pas temps réel). */
export function useApi<T>(path: string | null, refreshMs: number | null = REFRESH_MS): ApiState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [fetchedAt, setFetchedAt] = useState<Date | null>(null);
  const current = useRef(path);
  current.current = path;

  const load = useCallback(async () => {
    if (!path) return;
    try {
      const result = await api<T>(path);
      if (current.current === path) {
        setData(result);
        setError(null);
        setFetchedAt(new Date());
      }
    } catch (e) {
      if (current.current === path) setError(e instanceof Error ? e.message : "Erreur inconnue");
    } finally {
      if (current.current === path) setLoading(false);
    }
  }, [path]);

  useEffect(() => {
    setLoading(true);
    void load();
    if (!refreshMs) return;
    const id = window.setInterval(() => void load(), refreshMs);
    return () => window.clearInterval(id);
  }, [load, refreshMs]);

  return { data, error, loading, fetchedAt, reload: load };
}
