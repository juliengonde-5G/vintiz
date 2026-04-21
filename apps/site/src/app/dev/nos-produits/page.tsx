import Link from "next/link";
import Placeholder from "../_components/Placeholder";

const PRODUCTS = [
  { name: "Bonnet en crochet", price: "18,00 €", tone: "product" as const },
  { name: "Foulard en dentelle", price: "14,00 €", tone: "rack" as const },
  { name: "Foulard en crochet", price: "18,00 €", tone: "counter" as const },
  { name: "Pantalon « gigi »", price: "49,00 €", tone: "model-brown" as const },
  { name: "Chemise en lin", price: "24,00 €", tone: "model-white" as const },
  { name: "Veste en cuir", price: "69,00 €", tone: "street-male" as const },
  { name: "Robe longue", price: "39,00 €", tone: "pink-shop" as const },
  { name: "Trench beige", price: "55,00 €", tone: "street-female" as const },
];

export default function NosProduits() {
  return (
    <main className="bg-cream">
      <section className="max-w-7xl mx-auto px-6 py-16 lg:py-24">
        <h1 className="font-mockSerif italic text-teal text-5xl md:text-7xl">Nos produits</h1>
        <p className="mt-6 max-w-2xl text-black/80 text-base md:text-lg leading-relaxed">
          Une sélection renouvelée chaque semaine — vêtements, chaussures et
          accessoires de seconde main chinés par notre équipe.
        </p>

        <div className="mt-12 grid grid-cols-2 md:grid-cols-4 gap-4 md:gap-6">
          {PRODUCTS.map((p) => (
            <article key={p.name}>
              <Placeholder tone={p.tone} label={p.name} className="aspect-[3/4] rounded-md" />
              <div className="mt-3">
                <p className="text-sm text-black">{p.name}</p>
                <p className="text-sm text-black/60">{p.price}</p>
              </div>
            </article>
          ))}
        </div>

        <div className="mt-16 text-center">
          <Link href="/dev" className="text-sm text-teal underline underline-offset-4 hover:text-teal-600">
            ← Retour à l&apos;accueil
          </Link>
        </div>
      </section>
    </main>
  );
}
