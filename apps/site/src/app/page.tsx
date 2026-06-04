import Link from "next/link";
import Image from "next/image";
import PublicHeader from "@/components/PublicHeader";
import PublicFooter from "@/components/PublicFooter";
import NewsletterCard from "@/components/home/NewsletterCard";
import AddressBlock from "@/components/home/AddressBlock";
import { listPublicProducts } from "@/lib/storefront-api";
import { mediaUrl } from "@/lib/media";

// ISR — la home revalide en même temps que /produits.
export const revalidate = 300;

// Reel Instagram officiel du lancement (publication Solidarité Textiles).
const LAUNCH_VIDEO_URL =
  "https://www.instagram.com/reel/DZIWPkZM45u/";

// Galerie « Ils étaient là le 3 juin ». Toutes les photos portent le
// photocall « Affirmez votre style » distribué à l'entrée.
const OPENING_GALLERY: { src: string; alt: string }[] = [
  { src: "/opening/opening-portrait-stripes.jpg", alt: "Cliente Vintiz devant la boutique, jour d'ouverture" },
  { src: "/opening/opening-trio-cadre.jpg", alt: "Trois clientes Vintiz avec le photocall #DestinationVintiz" },
  { src: "/opening/opening-blonde-blanc.jpg", alt: "Cliente Vintiz avec son cadre Instagram" },
  { src: "/opening/opening-veste-jean.jpg", alt: "Cliente Vintiz, veste en jean" },
  { src: "/opening/opening-duo-younger.jpg", alt: "Deux clientes Vintiz devant le photocall" },
  { src: "/opening/opening-duo-veste.jpg", alt: "Deux clientes Vintiz, ambiance ouverture" },
  { src: "/opening/opening-cardigan-creme.jpg", alt: "Cliente Vintiz, cardigan crème" },
  { src: "/opening/opening-veste-sauge.jpg", alt: "Cliente Vintiz, veste vert sauge" },
  { src: "/opening/opening-couple.jpg", alt: "Couple à l'ouverture de Vintiz Vernon" },
  { src: "/opening/opening-famille.jpg", alt: "Trois jeunes clientes Vintiz, photo souvenir d'ouverture" },
];

export default async function Home() {
  // Coups de cœur = les 4 dernières pièces disponibles avec une photo
  // (ordre déjà défini par l'API : displayed_at desc, fallback created_at).
  const apiProducts = await listPublicProducts();
  const featured = apiProducts
    .filter((p) => p.available && p.photo_url)
    .slice(0, 4);

  return (
    <>
      <PublicHeader />
      <main className="bg-vz-bg">
        {/* HERO — boutique ouverte */}
        <section className="max-w-7xl mx-auto px-6 pt-10 pb-16 lg:pt-16 lg:pb-24">
          <div className="grid lg:grid-cols-2 gap-10 lg:gap-16 items-center">
            <div>
              <span className="inline-flex items-center gap-2 rounded-full bg-vz-accent-soft px-4 py-1.5 text-xs font-semibold tracking-[0.18em] uppercase text-vz-accent">
                <span aria-hidden className="h-2 w-2 rounded-full bg-vz-accent animate-pulse" />
                La boutique est ouverte
              </span>
              <h1 className="mt-5 font-mockSerif text-5xl md:text-6xl lg:text-7xl text-vz-teal leading-[1.05]">
                Vintiz Vernon,
                <br />
                <span className="italic">on vous attend.</span>
              </h1>
              <p className="mt-6 text-base md:text-lg text-black/80 leading-relaxed max-w-xl">
                Notre boutique de seconde main premium a ouvert ses portes
                <strong> mercredi 3 juin 2026</strong> au cœur de Vernon.
                Vêtements, chaussures et accessoires soigneusement sélectionnés
                pour leur qualité et leur style. Du mardi au samedi, 10h30–19h.
              </p>
              <div className="mt-8 flex flex-col sm:flex-row gap-3">
                <Link
                  href="/produits"
                  className="inline-flex items-center justify-center rounded-full bg-vz-teal px-8 py-3.5 text-sm font-medium text-white hover:bg-vz-teal-deep transition-colors"
                >
                  Découvrir la sélection
                </Link>
                <a
                  href="https://www.google.com/maps/place/6+Rue+St+Jacques,+27200+Vernon"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center justify-center rounded-full border border-vz-teal/40 px-8 py-3.5 text-sm font-medium text-vz-teal hover:bg-vz-teal hover:text-white transition-colors"
                >
                  Venir nous voir
                </a>
              </div>
              <p className="mt-5 text-sm text-black/55">
                6 rue Saint-Jacques · 27200 Vernon · 02 58 65 66 46
              </p>
            </div>
            <div className="relative aspect-[4/5] sm:aspect-[3/4] lg:aspect-[4/5] rounded-xl overflow-hidden bg-stone-200">
              <Image
                src="/opening/opening-portrait-stripes.jpg"
                alt="Une cliente Vintiz le jour de l'ouverture, photocall « Affirmez votre style »"
                fill
                sizes="(max-width: 1024px) 100vw, 50vw"
                className="object-cover"
                priority
              />
              <div className="absolute bottom-0 inset-x-0 bg-gradient-to-t from-black/55 via-black/15 to-transparent p-5">
                <p className="text-white text-sm md:text-base font-medium drop-shadow">
                  #DestinationVintiz · 3 juin 2026
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* VIDEO LANCEMENT */}
        <section className="bg-vz-teal py-14 md:py-16">
          <div className="max-w-5xl mx-auto px-6 grid md:grid-cols-2 gap-10 items-center text-white">
            <div>
              <p className="text-[11px] tracking-[0.22em] uppercase font-medium opacity-90">
                Reportage vidéo
              </p>
              <h2 className="mt-2 font-mockSerif text-4xl md:text-5xl leading-tight">
                Revivez le jour d&apos;ouverture
              </h2>
              <p className="mt-4 text-base md:text-lg opacity-90 max-w-md leading-relaxed">
                Une boutique pleine, des sourires, le ruban inaugural coupé :
                la vidéo officielle du lancement, signée Solidarité Textiles.
              </p>
              <a
                href={LAUNCH_VIDEO_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-6 inline-flex items-center gap-3 rounded-full bg-white text-vz-teal-deep px-7 py-3.5 text-sm font-semibold hover:bg-vz-bg transition-colors"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                  <rect x="2" y="2" width="20" height="20" rx="5" />
                  <circle cx="12" cy="12" r="4" />
                  <circle cx="18" cy="6" r="1" fill="currentColor" />
                </svg>
                Voir le reel sur Instagram
              </a>
              <p className="mt-3 text-xs opacity-75">
                Reel publié par @solidaritetextiles · ouverture dans un nouvel onglet.
              </p>
            </div>
            <div className="relative aspect-video rounded-xl overflow-hidden bg-black/30 shadow-vz-soft">
              <Image
                src="/opening/opening-couple.jpg"
                alt="Vignette de la vidéo de lancement Vintiz Vernon"
                fill
                sizes="(max-width: 768px) 100vw, 50vw"
                className="object-cover opacity-90"
              />
              <a
                href={LAUNCH_VIDEO_URL}
                target="_blank"
                rel="noopener noreferrer"
                aria-label="Lecture vidéo lancement Vintiz"
                className="absolute inset-0 flex items-center justify-center group"
              >
                <span className="flex h-20 w-20 items-center justify-center rounded-full bg-white/95 text-vz-teal-deep shadow-vz-soft group-hover:scale-105 transition-transform">
                  <svg width="32" height="32" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
                    <path d="M8 5v14l11-7z" />
                  </svg>
                </span>
              </a>
            </div>
          </div>
        </section>

        {/* GALERIE — ils étaient là le 3 juin */}
        <section className="max-w-7xl mx-auto px-6 py-16 lg:py-20">
          <div className="mb-8 text-center">
            <p className="text-[11px] tracking-[0.22em] uppercase text-vz-teal font-medium">
              #DestinationVintiz
            </p>
            <h2 className="mt-2 font-mockSerif text-3xl md:text-4xl text-vz-teal">
              Ils étaient là pour l&apos;ouverture
            </h2>
            <p className="mt-3 max-w-xl mx-auto text-sm md:text-base text-black/70">
              Merci aux premières clientes et clients qui ont franchi nos portes
              le 3 juin avec le sourire devant notre cadre « Affirmez votre style ».
            </p>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-2 md:gap-3">
            {OPENING_GALLERY.map((m) => (
              <div
                key={m.src}
                className="relative aspect-[3/4] overflow-hidden rounded-md bg-stone-200"
              >
                <Image
                  src={m.src}
                  alt={m.alt}
                  fill
                  sizes="(max-width: 768px) 50vw, (max-width: 1024px) 33vw, 20vw"
                  className="object-cover hover:scale-[1.03] transition-transform duration-500"
                />
              </div>
            ))}
          </div>
        </section>

        {/* COUPS DE COEUR */}
        <section className="max-w-7xl mx-auto px-6 pb-16 lg:pb-20">
          <div className="mb-6">
            <h2 className="font-mockSerif text-3xl md:text-4xl text-vz-teal flex items-center gap-3">
              <span aria-hidden>❤️</span> Nos coups de cœur en boutique
            </h2>
            <p className="text-sm text-black/60 mt-2">
              À découvrir en rayon dès aujourd&apos;hui. La sélection bouge chaque jour.
            </p>
          </div>
          {featured.length > 0 ? (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 md:gap-6">
              {featured.map((p) => (
                <Link key={p.slug} href={`/produits/${p.slug}`} className="group block">
                  <div className="relative aspect-square rounded-md overflow-hidden bg-stone-100">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={mediaUrl(p.photo_url || "")}
                      alt={`${p.brand ?? ""} — ${p.name}`}
                      className="w-full h-full object-cover group-hover:scale-[1.02] transition-transform duration-500"
                      loading="lazy"
                    />
                  </div>
                  <div className="mt-3">
                    <p className="text-[11px] uppercase tracking-[0.12em] text-black/60">{p.brand}</p>
                    <p className="text-sm text-black line-clamp-2">{p.name}</p>
                    <p className="text-sm text-vz-teal font-semibold">{p.price_eur} €</p>
                  </div>
                </Link>
              ))}
            </div>
          ) : (
            <p className="text-sm text-black/60 italic">
              Les pièces du jour s&apos;affichent ici dès qu&apos;elles sont en rayon.
              En attendant,{" "}
              <Link href="/produits" className="underline underline-offset-2 hover:text-vz-teal">
                parcourez la sélection
              </Link>
              .
            </p>
          )}
          <div className="mt-8 text-center">
            <Link
              href="/produits"
              className="text-sm font-medium text-vz-teal underline underline-offset-4 hover:text-vz-teal-deep"
            >
              Voir toute la boutique →
            </Link>
          </div>
        </section>

        {/* CITATION */}
        <section className="bg-vz-bg-alt py-14">
          <p className="max-w-4xl mx-auto px-6 text-center font-mockSerif text-3xl md:text-4xl lg:text-5xl text-vz-teal leading-snug">
            Affirmez votre style,<br />
            révélez vos valeurs.
          </p>
        </section>

        {/* NOTRE CONCEPT */}
        <section className="max-w-7xl mx-auto px-6 py-16 lg:py-24">
          <div className="grid lg:grid-cols-2 gap-10 lg:gap-16 items-start">
            <div>
              <h2 className="font-mockSerif text-4xl md:text-5xl text-vz-teal mb-6">
                Notre concept
              </h2>
              <div className="relative aspect-[4/3] rounded-md overflow-hidden bg-stone-200">
                <Image
                  src="/opening/opening-veste-sauge.jpg"
                  alt="Intérieur boutique Vintiz Vernon"
                  fill
                  sizes="(max-width: 1024px) 100vw, 50vw"
                  className="object-cover"
                />
              </div>
            </div>
            <div className="pt-6 lg:pt-20 text-center lg:text-left">
              <p className="text-base md:text-lg text-black/80 leading-relaxed">
                La mission de Vintiz est claire : proposer une expérience shopping
                personnalisée, grâce à des articles de qualité, en excellent état,
                avec une sélection de marques renouvelée régulièrement. Des vêtements,
                chaussures et accessoires à petits prix pour se faire plaisir tout en
                respectant la planète.
              </p>
              <p className="mt-6 text-base md:text-lg text-black/80 leading-relaxed">
                Nous sélectionnons soigneusement les pièces de seconde main auprès
                de notre partenaire exclusif Solidarité Textiles.
              </p>
              <Link
                href="/a-propos"
                className="mt-8 inline-flex items-center justify-center rounded-full bg-vz-teal px-8 py-3.5 text-sm font-medium text-white hover:bg-vz-teal-deep transition-colors"
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
        <section className="bg-vz-bg-alt border-t border-black/5">
          <div className="max-w-7xl mx-auto px-6 py-14 grid md:grid-cols-3 gap-10 items-center">
            <div>
              <p className="font-mockSerif text-4xl text-vz-teal tracking-[0.35em]">V I N T I Z</p>
              <div className="mt-6">
                <AddressBlock />
              </div>
            </div>
            <div className="relative aspect-[3/4] rounded-md overflow-hidden bg-stone-200">
              <Image
                src="/opening/opening-blonde-blanc.jpg"
                alt="Cliente Vintiz, ambiance boutique"
                fill
                sizes="(max-width: 768px) 100vw, 33vw"
                className="object-cover"
              />
            </div>
            <div className="relative aspect-[3/4] rounded-md overflow-hidden bg-stone-200">
              <Image
                src="/opening/opening-cardigan-creme.jpg"
                alt="Cliente Vintiz, jour d'ouverture"
                fill
                sizes="(max-width: 768px) 100vw, 33vw"
                className="object-cover"
              />
            </div>
          </div>
        </section>
      </main>
      <PublicFooter />
    </>
  );
}
