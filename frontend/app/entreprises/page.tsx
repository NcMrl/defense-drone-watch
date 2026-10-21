"use client";

import Link from "next/link";

import { SyntheticBadge } from "@/components/badges";
import { Empty, ErrorBox, PageTitle, Panel } from "@/components/Shell";
import type { Company } from "@/lib/api";
import { label } from "@/lib/i18n";
import { useApi } from "@/lib/useApi";

export default function EntreprisesPage() {
  const { data, error } = useApi<Company[]>("/api/companies");
  return (
    <>
      <PageTitle
        title="Entreprises suivies"
        subtitle="Référentiel des entreprises détectées par dictionnaire de noms. Les fiches complètes (produits, contrats, chronologie, faits/annonces distingués) arrivent en phase 4."
      />
      {error && <ErrorBox message={error} />}
      <Panel>
        {data?.length ? (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs text-muted">
                <th className="py-2 font-medium">Entreprise</th>
                <th className="py-2 font-medium">Variantes de nom</th>
                <th className="py-2 font-medium">Pays</th>
                <th className="py-2 text-right font-medium">Documents</th>
              </tr>
            </thead>
            <tbody>
              {data.map((c) => (
                <tr key={c.id} className="border-b border-line/70">
                  <td className="py-2">
                    <Link href={`/flux?company_id=${c.id}`} className="font-medium text-blue-700 hover:underline">{c.name}</Link>{" "}
                    {c.is_synthetic && <SyntheticBadge />}
                  </td>
                  <td className="py-2 text-xs text-muted">{c.aliases.join(", ") || "—"}</td>
                  <td className="py-2 text-xs">{c.country ? label("countries", c.country) : "non documenté"}</td>
                  <td className="py-2 text-right tabular">{c.document_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <Empty>Aucune entreprise au référentiel.</Empty>
        )}
      </Panel>
    </>
  );
}
