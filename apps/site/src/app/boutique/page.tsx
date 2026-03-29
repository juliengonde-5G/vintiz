import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "La Boutique | Vintiz - Vernon",
  description: "Decouvrez notre boutique de seconde main premium au 6 rue Saint-Jacques a Vernon. Selection rigoureuse, cadre elegant, pieces uniques.",
};

const categories = [
  {
    name: "Robes",
    desc: "Du casual au cocktail, des robes de marque en parfait etat.",
    icon: (
      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M6 2L3 6v14a2 2 0 002 2h14a2 2 0 002-2V6l-3-4z" />
        <line x1="3" y1="6" x2="21" y2="6" />
        <path d="M16 10a4 4 0 01-8 0" />
      </svg>
    ),
  },
  {
    name: "Hauts & Chemises",
    desc: "Pulls, blouses, chemises et tops de marques premium.",
    icon: (
      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M20.38 3.46L16 2 12 5 8 2l-4.38 1.46a2 2 0 00-1.34 2.23l.58 3.47A1 1 0 003.85 10H6v10a2 2 0 002 2h8a2 2 0 002-2V10h2.15a1 1 0 00.99-1.16l.58-3.47a2 2 0 00-1.34-2.23z" />
      </svg>
    ),
  },
  {
    name: "Pantalons & Jupes",
    desc: "Jeans, pantalons habilles, jupes mi-longues et courtes.",
    icon: (
      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M4 2h16v6a4 4 0 01-4 4h-8a4 4 0 01-4-4V2z" />
        <path d="M8 12v10M16 12v10" />
      </svg>
    ),
  },
  {
    name: "Manteaux & Vestes",
    desc: "Blazers, trenchs, manteaux d'hiver et vestes de mi-saison.",
    icon: (
      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M12 22s-8-4.5-8-11.8A8 8 0 0112 2a8 8 0 018 8.2c0 7.3-8 11.8-8 11.8z" />
      </svg>
    ),
  },
  {
    name: "Accessoires",
    desc: "Sacs, ceintures, foulards et bijoux de marques recherchees.",
    icon: (
      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <circle cx="12" cy="12" r="10" />
        <path d="M12 2a14.5 14.5 0 000 20 14.5 14.5 0 000-20" />
        <line x1="2" y1="12" x2="22" y2="12" />
      </svg>
    ),
  },
  {
    name: "Chaussures",
    desc: "Escarpins, bottines, sandales et sneakers premium.",
    icon: (
      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M2 18l1.5-4.5L7 12l3 1.5 4-2 5 1 3 5.5H2z" />
      </svg>
    ),
  },
];

export default function BoutiquePage() {
  return (
    <>
      <Navbar />

      {/* Hero */}
      <section className="pt-28 pb-16 px-6 bg-vintiz-bg">
        <div className="max-w-4xl mx-auto text-center">
          <h1 className="font-serif text-4xl sm:text-5xl text-vintiz-black mb-4">
            La <em className="text-vintiz-teal">Boutique</em>
          </h1>
          <p className="text-lg text-vintiz-black/60 max-w-2xl mx-auto leading-relaxed">
            Un ecrin de 98m&sup2; en plein coeur de Vernon, dedie a la mode de seconde main premium. Chaque piece est selectionnee, verifiee et presentee avec soin.
          </p>
        </div>
      </section>

      {/* Concept photos */}
      <section className="py-16 px-6 bg-white">
        <div className="max-w-6xl mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div className="rounded-2xl bg-vintiz-pink/10 h-64 flex items-center justify-center">
              <div className="text-center p-6">
                <p className="font-serif text-2xl text-vintiz-black mb-2">98 m&sup2;</p>
                <p className="text-sm text-vintiz-black/50">d&apos;espace shopping</p>
              </div>
            </div>
            <div className="rounded-2xl bg-vintiz-teal/10 h-64 flex items-center justify-center">
              <div className="text-center p-6">
                <p className="font-serif text-2xl text-vintiz-black mb-2">+200</p>
                <p className="text-sm text-vintiz-black/50">pieces selectionnees en boutique</p>
              </div>
            </div>
            <div className="rounded-2xl bg-vintiz-pink/10 h-64 flex items-center justify-center">
              <div className="text-center p-6">
                <p className="font-serif text-2xl text-vintiz-black mb-2">100%</p>
                <p className="text-sm text-vintiz-black/50">verifiees et nettoyees</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Categories */}
      <section className="py-20 px-6 bg-vintiz-bg">
        <div className="max-w-6xl mx-auto">
          <h2 className="font-serif text-3xl text-center text-vintiz-black mb-12">
            Nos <em className="text-vintiz-teal">Categories</em>
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {categories.map((c) => (
              <div key={c.name} className="bg-white rounded-2xl p-8 hover:shadow-lg transition-shadow">
                <div className="w-14 h-14 rounded-full bg-vintiz-pink/20 flex items-center justify-center text-vintiz-teal mb-4">
                  {c.icon}
                </div>
                <h3 className="font-serif text-xl font-semibold text-vintiz-black mb-2">{c.name}</h3>
                <p className="text-sm text-vintiz-black/50 leading-relaxed">{c.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing philosophy */}
      <section className="py-20 px-6 bg-white">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="font-serif text-3xl text-vintiz-black mb-4">
            Des <em className="text-vintiz-teal">prix justes</em>
          </h2>
          <p className="text-vintiz-black/60 leading-relaxed mb-8 max-w-2xl mx-auto">
            Nos prix sont calcules en fonction de la marque, de l&apos;etat et de la tendance du moment.
            Decouvrez des pieces de grandes marques a 50-70% de leur prix neuf.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 max-w-3xl mx-auto">
            <div className="p-6 bg-vintiz-bg rounded-2xl">
              <p className="font-serif text-2xl text-vintiz-teal mb-1">5 - 25 &euro;</p>
              <p className="text-sm text-vintiz-black/50">Entree de gamme</p>
            </div>
            <div className="p-6 bg-vintiz-bg rounded-2xl">
              <p className="font-serif text-2xl text-vintiz-teal mb-1">25 - 80 &euro;</p>
              <p className="text-sm text-vintiz-black/50">Milieu de gamme</p>
            </div>
            <div className="p-6 bg-vintiz-bg rounded-2xl">
              <p className="font-serif text-2xl text-vintiz-teal mb-1">80 - 200 &euro;</p>
              <p className="text-sm text-vintiz-black/50">Premium</p>
            </div>
          </div>
        </div>
      </section>

      <Footer />
    </>
  );
}
