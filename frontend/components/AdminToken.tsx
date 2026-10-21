"use client";

import { useEffect, useState } from "react";

import { getAdminToken, setAdminToken } from "@/lib/api";

/** Saisie du jeton d'administration, conservé uniquement pour la session de l'onglet. */
export function AdminToken() {
  const [has, setHas] = useState(false);
  const [value, setValue] = useState("");
  useEffect(() => setHas(Boolean(getAdminToken())), []);

  if (has) {
    return (
      <div className="flex items-center gap-2 text-xs">
        <span className="text-ok">● Jeton d'administration chargé (session)</span>
        <button type="button" className="text-muted underline" onClick={() => { setAdminToken(null); setHas(false); }}>
          Oublier
        </button>
      </div>
    );
  }
  return (
    <form
      className="flex items-center gap-2 text-xs"
      onSubmit={(e) => {
        e.preventDefault();
        if (value.trim()) {
          setAdminToken(value.trim());
          setValue("");
          setHas(true);
        }
      }}
    >
      <label htmlFor="admin-token" className="text-muted">Jeton d'administration</label>
      <input id="admin-token" type="password" autoComplete="off" className="w-48 rounded border border-line px-2 py-1" value={value} onChange={(e) => setValue(e.target.value)} />
      <button type="submit" className="rounded bg-ink px-2.5 py-1 text-white">Utiliser</button>
    </form>
  );
}
