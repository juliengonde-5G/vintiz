import Link from "next/link";
import Placeholder from "./_components/Placeholder";
import NewsletterCard from "./_components/NewsletterCard";
import AddressBlock from "./_components/AddressBlock";

const PRODUCTS = [
  { name: "Bonnet en crochet", price: "18,00 €", tone: "product" as const },
  { name: "Foulard en dentelle", price: "14,00 €", tone: "rack" as const },
  { name: "Foulard en crochet", price: "18,00 €", tone: "counter" as const },
  { name: "Pantalon « gigi »", price: "49,00 €", tone: "model-brown" as const },
];

export default function DevHome() {
  return (
    <main className="bg-cream">
      {/* HERO */}
      <section className="max-w-7xl mx-auto px-6 pt-10 pb-16 lg:pt-16 lg:pb-24">
        <div className="grid lg:grid-cols-2 gap-10 lg:gap-16 items-center">
          <div>
            <h1 className="font-mockSerif text-5xl md:text-6xl lg:text-7xl text-teal leading-[1.05]">
              Vintiz,
              <br />
              <span className="italic">une mode qui fait sens.</span>
            </h1>
            <p className="mt-6 text-base md:text-lg text-black/80 leading-relaxed max-w-xl">
              La boutique de seconde main à Vernon pour celle et ceux qui aiment
              la mode chic et tendance.
              <br />
              Une gamme de vêtements, accessoires et chaussures de seconde main
              soigneusement sélectionnés pour leur qualité, leur style et leur
              intemporalité.
            </p>
            <Link
              href="/dev/notre-boutique"
              className="mt-8 inline-flex items-center justify-center rounded-full bg-pink px-8 py-3.5 text-sm font-medium text-black hover:bg-pink-400 transition-colors"
            >
              Découvrir la boutique
            </Link>
          </div>
          <Placeholder
            tone="storefront"
            label="Devanture Vintiz — 6 rue St Jacques"
            className="aspect-[4/3] rounded-xl"
          >
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="bg-white/90 px-6 py-4 rounded-lg shadow text-center">
                <p className="font-mockSerif text-3xl text-teal">VINTIZ</p>
                <p className="text-xs tracking-widest text-black/70 mt-1">OUVERTURE PROCHAINE</p>
                <p className="text-[10px] text-black/50 mt-1">
                  VOTRE NOUVELLE DESTINATION
                  <br />SLOW FASHION
                </p>
              </div>
            </div>
          </Placeholder>
        </div>
      </section>

      {/* MOSAIQUE 4 BOUTIQUE */}
      <section className="w-full">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 md:gap-3 px-2 md:px-3">
          <Placeholder tone="pink-shop" label="Showroom rose" className="aspect-[3/4]" />
          <Placeholder tone="rack" label="Portants accessoires" className="aspect-[3/4]" />
          <Placeholder tone="counter" label="Comptoir caisse" className="aspect-[3/4]" />
          <Placeholder tone="mirrors" label="Cabines d'essayage" className="aspect-[3/4]" />
        </div>
      </section>

      {/* COUPS DE COEUR */}
      <section className="max-w-7xl mx-auto px-6 py-16 lg:py-20">
        <div className="flex items-end justify-between mb-6">
          <h2 className="font-mockSerif text-3xl md:text-4xl text-teal flex items-center gap-3">
            <span aria-hidden>❤️</span> Nos coups de cœur en boutique
          </h2>
          <Link href="/dev/nos-produits" className="text-xs uppercase tracking-widest text-black/70 hover:text-teal underline underline-offset-4">
            Voir toutes les nouveautés →
          </Link>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 md:gap-6">
          {PRODUCTS.map((p) => (
            <article key={p.name} className="group">
              <Placeholder tone={p.tone} label={p.name} className="aspect-square rounded-md" />
              <div className="mt-3">
                <p className="text-sm text-black">{p.name}</p>
                <p className="text-sm text-black/60">{p.price}</p>
              </div>
            </article>
          ))}
        </div>
        <div className="mt-8 flex items-center justify-center gap-2" aria-hidden>
          <span className="h-[2px] w-10 bg-black/60" />
          <span className="h-[2px] w-10 bg-black/10" />
          <span className="h-[2px] w-10 bg-black/10" />
        </div>
      </section>

      {/* CITATION */}
      <section className="bg-cream py-14">
        <p className="max-w-4xl mx-auto px-6 text-center font-mockSerif text-2xl md:text-3xl lg:text-4xl text-teal leading-snug">
          Vintiz incarne une vision moderne de la mode :<br />
          durable, qualitative et accessible pour se faire plaisir<br />
          tout en minimisant son impact environnemental.
        </p>
      </section>

      {/* MARQUEE TEAL */}
      <section className="bg-teal overflow-hidden">
        <div className="flex whitespace-nowrap animate-[marquee_22s_linear_infinite] py-5 text-white text-sm tracking-[0.25em]">
          {Array.from({ length: 6 }).map((_, i) => (
            <span key={i} className="mx-6 flex items-center gap-6">
              · LES VESTES À -50 %
              <span className="font-mockSerif italic tracking-widest text-base">VINTIZ</span>
            </span>
          ))}
        </div>
      </section>

      {/* NOTRE CONCEPT */}
      <section className="max-w-7xl mx-auto px-6 py-16 lg:py-24">
        <div className="grid lg:grid-cols-2 gap-10 lg:gap-16 items-start">
          <div>
            <h2 className="font-mockSerif text-4xl md:text-5xl text-teal mb-6">Notre concept</h2>
            <Placeholder tone="shop-interior" label="Intérieur boutique" className="aspect-[4/3] rounded-md" />
          </div>
          <div className="pt-6 lg:pt-20 text-center lg:text-left">
            <p className="text-base md:text-lg text-black/80 leading-relaxed">
              Vintiz la boutique de seconde main chic et tendance qui propose une
              sélection de vêtements, chaussures et accessoires de qualité et à
              petits prix pour se faire plaisir tout en respectant la planète.
            </p>
            <p className="mt-6 text-base md:text-lg text-black/80 leading-relaxed">
              Nous sélectionnons soigneusement les pièces de seconde main auprès
              de notre partenaire exclusif Solidarité Textiles.
            </p>
            <Link
              href="/dev/notre-boutique"
              className="mt-8 inline-flex items-center justify-center rounded-full bg-teal px-8 py-3.5 text-sm font-medium text-white hover:bg-teal-600 transition-colors"
            >
              Découvrir notre concept
            </Link>
          </div>
        </div>
      </section>

      {/* NEWSLETTER */}
      <section className="pb-20">
        <NewsletterCard />
      </section>

      {/* ZONE ADRESSE */}
      <section className="bg-cream border-t border-black/5">
        <div className="max-w-7xl mx-auto px-6 py-14 grid md:grid-cols-3 gap-10 items-center">
          <div>
            <p className="font-mockSerif text-4xl text-teal tracking-[0.35em]">V I N T I Z</p>
            <div className="mt-6">
              <AddressBlock />
            </div>
          </div>
          <Placeholder tone="street-female" label="Look femme Vintiz" className="aspect-[3/4] rounded-md" />
          <Placeholder tone="street-male" label="Look homme Vintiz" className="aspect-[3/4] rounded-md" />
        </div>
      </section>
    </main>
  );
}
