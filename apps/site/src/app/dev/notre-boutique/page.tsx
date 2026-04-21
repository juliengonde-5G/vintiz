import Link from "next/link";
import Placeholder from "../_components/Placeholder";
import AddressBlock from "../_components/AddressBlock";

const REVIEWS = [
  {
    text: "Depuis de nombreuses années, c'est de loin ma friperie préférée. Des fringues à tous les prix et de l'extrême gentillesse 🛍️🫶",
    name: "Marie S.",
  },
  {
    text: "Une des meilleures boutiques de Rouen (si ce n'est LA meilleure 😍) !! Vêtements et accessoires parfaits pour toutes occasions, tout est d'un goût parfait ! Et que dire de l'accueil, toute l'équipe est adorable !",
    name: "Clara B.",
  },
  {
    text: "Boutique indépendante de qualité, dont la sélection de vêtements est variée et accessible ; j'y fais toutes les semaines si ce n'est plus. J'y fais un tour régulièrement 💚",
    name: "Léa T.",
  },
];

export default function NotreBoutique() {
  return (
    <main className="bg-cream">
      {/* HERO STOREFRONT */}
      <section className="relative">
        <Placeholder tone="storefront" label="Façade NAF NAF — future Vintiz" className="h-[420px] md:h-[520px] w-full">
          <div className="absolute inset-0 flex flex-col items-center justify-center text-center px-6">
            <h1 className="font-mockSerif italic text-white text-5xl md:text-7xl drop-shadow-[0_2px_10px_rgba(0,0,0,0.6)]">
              Notre boutique
            </h1>
            <Link
              href="https://www.google.com/maps/place/6+Rue+St+Jacques,+27200+Vernon"
              className="mt-8 inline-flex items-center rounded-full bg-cream/95 px-8 py-3.5 text-sm tracking-widest text-black hover:bg-white transition-colors"
            >
              6 RUE ST JACQUES, 27200 VERNON
            </Link>
          </div>
        </Placeholder>
      </section>

      {/* NOTRE CONCEPT */}
      <section className="max-w-7xl mx-auto px-6 py-20 grid lg:grid-cols-2 gap-12 items-start">
        <h2 className="font-mockSerif text-5xl md:text-6xl text-teal">Notre concept</h2>
        <div className="space-y-5 text-black/85 leading-relaxed font-mockSerif text-xl italic">
          <p>
            Vintiz est née d&apos;une idée simple : proposer une seconde main chic
            et tendance, où chaque pièce est choisie pour sa qualité et son
            style.
          </p>
          <div className="not-italic font-sans text-base text-black/80 space-y-4 pt-2">
            <p>
              Vintiz, c&apos;est l&apos;envie de consommer autrement sans renoncer au
              plaisir de s&apos;habiller avec style. C&apos;est une boutique où l&apos;on vient
              chercher des pièces coup de cœur, dans une ambiance chaleureuse, le
              tout avec une vision plus consciente de la mode.
            </p>
          </div>
          <div className="pt-2 not-italic">
            <Link
              href="https://www.google.com/maps/place/6+Rue+St+Jacques,+27200+Vernon"
              className="inline-flex items-center rounded-full bg-pink px-8 py-3 text-sm tracking-widest font-sans text-black hover:bg-pink-400 transition-colors"
            >
              ME RENDRE À LA BOUTIQUE
            </Link>
          </div>
        </div>
      </section>

      {/* UNE MODE QUI A DU SENS — 1 */}
      <section className="bg-cream">
        <div className="grid lg:grid-cols-2">
          <Placeholder tone="model-brown" label="Chemise marron — look Vintiz" className="aspect-[4/5]" />
          <div className="flex flex-col justify-center px-8 md:px-16 py-16 text-center lg:text-left">
            <h2 className="font-mockSerif text-5xl text-teal leading-tight">
              Une mode qui
              <br />a du sens
            </h2>
            <p className="mt-6 text-base md:text-lg text-black/80 leading-relaxed max-w-lg">
              Une gamme de vêtements, accessoires et chaussures de seconde main
              soigneusement sélectionnés pour leur qualité, leur style et leur
              intemporalité.
            </p>
            <p className="mt-4 text-base md:text-lg text-black/80 leading-relaxed max-w-lg">
              En choisissant Vintiz, vous incarnez une vision moderne de la mode :
              durable, qualitative et accessible pour se faire plaisir tout en
              minimisant son impact environnemental.
            </p>
          </div>
        </div>
      </section>

      {/* UNE MODE QUI A DU SENS — 2 / SOLIDARITÉ TEXTILES */}
      <section className="bg-cream">
        <div className="grid lg:grid-cols-2">
          <div className="flex flex-col justify-center px-8 md:px-16 py-16 lg:order-1 text-center lg:text-left">
            <h2 className="font-mockSerif text-5xl text-teal leading-tight">
              Une mode qui
              <br />a du sens
            </h2>
            <p className="mt-6 text-base md:text-lg text-black/80 leading-relaxed max-w-lg">
              Les vêtements, chaussures et accessoires sont soigneusement
              sélectionnés pour leur qualité par notre partenaire Solidarité
              Textiles, centre de tri textile situé au Houlme.
            </p>
            <p className="mt-4 text-base md:text-lg text-black/80 leading-relaxed max-w-lg">
              Les vêtements sont collectés dans des bornes de collecte réparties
              sur la Métropole Rouen Normandie, puis triés manuellement par des
              salariés en insertion.
            </p>
            <Link
              href="https://solidaritetextiles.com"
              className="mt-8 inline-flex self-center lg:self-start items-center rounded-full bg-pink px-8 py-3 text-sm tracking-widest text-black hover:bg-pink-400 transition-colors"
            >
              DÉCOUVRIR SOLIDARITÉ TEXTILES
            </Link>
          </div>
          <Placeholder tone="model-white" label="Polo blanc — partenaire" className="aspect-[4/5] lg:order-2" />
        </div>
      </section>

      {/* REVIEWS */}
      <section className="bg-cream py-20">
        <div className="max-w-6xl mx-auto px-6 text-center">
          <p className="text-[11px] tracking-[0.3em] uppercase text-black/60">
            NOTÉ 4,7/5 <span aria-hidden>★</span> SUR GOOGLE
          </p>
          <h2 className="mt-3 font-mockSerif text-3xl md:text-4xl text-teal flex items-center justify-center gap-2">
            Ce que pensent nos clientes <span aria-hidden>💖</span>
          </h2>
          <p className="mt-2 text-sm text-black/70">
            Chez Jade &amp; Lisa, la satisfaction client est notre priorité !
          </p>

          <div className="mt-10 grid md:grid-cols-3 gap-8">
            {REVIEWS.map((r, i) => (
              <blockquote key={i} className={`${i === 1 ? "" : "opacity-80"} text-sm md:text-base text-black/80`}>
                <p className="text-yellow-500 tracking-widest text-sm" aria-hidden>★★★★★</p>
                <p className="mt-4 leading-relaxed">{r.text}</p>
                <footer className="mt-4 text-black/60">— {r.name}</footer>
              </blockquote>
            ))}
          </div>

          <div className="mt-8 flex items-center justify-center gap-2" aria-hidden>
            <span className="h-2 w-2 rounded-full bg-black/15" />
            <span className="h-2 w-2 rounded-full bg-black/15" />
            <span className="h-2 w-2 rounded-full bg-black" />
          </div>
        </div>
      </section>

      {/* FOOTER ADDRESS */}
      <section className="bg-cream border-t border-black/5">
        <div className="max-w-7xl mx-auto px-6 py-14 grid md:grid-cols-3 gap-10 items-start">
          <div>
            <p className="font-mockSerif text-4xl text-teal tracking-[0.35em]">V I N T I Z</p>
            <div className="mt-6">
              <AddressBlock />
            </div>
          </div>
          <Placeholder tone="pink-shop" label="Boutique rose" className="aspect-[3/4] rounded-md" />
          <Placeholder tone="mirrors" label="Cabines d'essayage" className="aspect-[3/4] rounded-md" />
        </div>
      </section>
    </main>
  );
}
