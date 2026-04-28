"use client";

import AccountShell from "@/components/account/AccountShell";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface WindowItem {
  product_id: string;
  product_name: string;
  reason: string | null;
  photo_url: string | null;
  sale_price: number;
}

export default function AccountSelectionPage() {
  // For PR3 we render the manager's current window display proposal as a
  // public curation feed. The endpoint exists but is admin-only — we'd
  // expose a public mirror in PR4. For now display a static introduction.
  void API_URL;
  const items: WindowItem[] = [];
  return (
    <AccountShell
      title="Sélection du moment"
      intro="Les coups de cœur de l'équipe boutique cette semaine, choisis pour l'ambiance et la saison."
    >
      {items.length === 0 ? (
        <div className="bg-white rounded-2xl shadow-sm p-6">
          <p className="text-gray-700">
            La sélection de la semaine est mise à jour chaque lundi par
            l&apos;équipe boutique. Passez à Vernon pour découvrir les pièces
            choisies en vitrine.
          </p>
          <p className="text-sm text-gray-500 mt-3">
            6 rue Saint-Jacques · 27200 Vernon
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          {items.map((it) => (
            <article key={it.product_id} className="bg-white rounded-2xl overflow-hidden shadow-sm">
              <div className="aspect-square bg-gray-100">
                {it.photo_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={it.photo_url} alt={it.product_name} className="w-full h-full object-cover" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-4xl text-gray-300">👗</div>
                )}
              </div>
              <div className="p-3">
                <h3 className="text-sm font-medium text-black">{it.product_name}</h3>
                {it.reason && <p className="text-xs text-gray-500 mt-1">{it.reason}</p>}
                <p className="text-base font-semibold text-teal mt-2">{it.sale_price.toFixed(2)} €</p>
              </div>
            </article>
          ))}
        </div>
      )}
    </AccountShell>
  );
}
