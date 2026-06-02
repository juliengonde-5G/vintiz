import Link from "next/link";
import Image from "next/image";
import PublicHeader from "@/components/PublicHeader";
import PublicFooter from "@/components/PublicFooter";
import NewsletterCard from "@/components/home/NewsletterCard";
import AddressBlock from "@/components/home/AddressBlock";
import { mediaUrl } from "@/lib/media";
import { formatPriceCents } from "@/lib/format";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Highlight {
  id: string;
  name: string;
  brand: string | null;
  size: string | null;
  color: string | null;
  sale_price: number;
  price_cents: number;
  photo_url: string | null;
  reason: string | null;
}

interface HighlightsPayload {
  items: Highlight[];
  curator_note: string;
}

/** Fetch the manager-curated "coups de cœur" — padded by top trend if the
 *  curation is incomplete. Returns ``items=[]`` when nothing real is on the
 *  floor (the section is then hidden — no demo fallback). Revalidated every
 *  60 s to keep the landing snappy without spamming the API. */
async function fetchHighlights(): Promise<HighlightsPayload> {
  try {
    const res = await fetch(`${API_URL}/api/crm/storefront/highlights?limit=4`, {
      next: { revalidate: 60 },
    });
    if (!res.ok) return { items: [], curator_note: "" };
    return (await res.json()) as HighlightsPayload;
  } catch {
    return { items: [], curator_note: "" };
  }
}

const MOSAIC = [
  { src: "/dev/shop-pink-racks.jpg", alt: "Portants de la boutique Vintiz" },
  { src: "/dev/shop-mirrors.jpg", alt: "Cabines d'essayage Vintiz" },
  { src: "/dev/shop-counter.jpg", alt: "Comptoir caisse Vintiz" },
  { src: "/dev/shop-showroom.jpg", alt: "Showroom intérieur Vintiz" },
];

export default async function Home() {
  const highlights = await fetchHighlights();
  return (
    <>
      <PublicHeader />
      <main className="bg-vz-bg">
        {/* HERO */}
        <section className="max-w-7xl mx-auto px-6 pt-10 pb-16 lg:pt-16 lg:pb-24">
          <div className="grid lg:grid-cols-2 gap-10 lg:gap-16 items-center">
            <div>
              <h1 className="font-mockSerif text-5xl md:text-6xl lg:text-7xl text-vz-teal leading-[1.05]">
                Vintiz,
                <br />
                <span className="italic">une mode qui fait sens.</span>
              </h1>
              <p className="mt-6 text-base md:text-lg text-black/80 leading-relaxed max-w-xl">
                Votre destination slow fashion à Vernon.
                <br />
                Bienvenue dans la boutique de seconde main premium pour celles et ceux
                qui aiment la mode chic et tendance. Retrouvez des vêtements, chaussures
                et accessoires soigneusement sélectionnés pour leur qualité et leur style.
              </p>
              <div className="mt-8 flex flex-col sm:flex-row gap-3">
                <Link
                  href="/produits"
                  className="inline-flex items-center justify-center rounded-full bg-vz-teal px-8 py-3.5 text-sm font-medium text-white hover:bg-vz-teal-deep transition-colors"
                >
                  Découvrir la boutique
                </Link>
                <Link
                  href="/personal-shopper"
                  className="inline-flex items-center justify-center rounded-full border border-vz-teal/40 px-8 py-3.5 text-sm font-medium text-vz-teal hover:bg-vz-teal hover:text-white transition-colors"
                >
                  Mon Personal Shopper
                </Link>
              </div>
            </div>
            <div className="relative aspect-[4/3] rounded-xl overflow-hidden bg-slate-900">
              <Image
                src="/dev/storefront-vintiz.jpg"
                alt="Devanture Vintiz — 6 rue Saint-Jacques, Vernon"
                fill
                sizes="(max-width: 1024px) 100vw, 50vw"
                className="object-cover"
                priority
              />
            </div>
          </div>
        </section>

        {/* MOSAIQUE BOUTIQUE */}
        <section className="w-full">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 md:gap-3 px-2 md:px-3">
            {MOSAIC.map((m) => (
              <div key={m.src} className="relative aspect-[3/4] overflow-hidden bg-stone-200">
                <Image src={m.src} alt={m.alt} fill sizes="(max-width: 768px) 50vw, 25vw" className="object-cover" />
              </div>
            ))}
          </div>
        </section>

        {/* COUPS DE COEUR — sélection vivante : curation manager + meilleurs
            produits du rayon (trend_score). Masquée si rien de vendable —
            aucun fallback démo. */}
        {highlights.items.length > 0 && (
          <section className="max-w-7xl mx-auto px-6 py-16 lg:py-20">
            <div className="mb-6">
              <h2 className="font-mockSerif text-3xl md:text-4xl text-vz-teal flex items-center gap-3">
                <span aria-hidden>❤️</span> Nos coups de cœur en boutique
              </h2>
              {highlights.curator_note && (
                <p className="mt-2 text-sm text-black/70 italic">
                  {highlights.curator_note}
                </p>
              )}
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 md:gap-6">
              {highlights.items.map((p) => {
                const photo = mediaUrl(p.photo_url);
                return (
                  <article key={p.id} className="group">
                    <div className="relative aspect-square rounded-md overflow-hidden bg-stone-100">
                      {photo ? (
                        <Image
                          src={photo}
                          alt={p.name}
                          fill
                          sizes="(max-width: 768px) 50vw, 25vw"
                          className="object-cover"
                        />
                      ) : (
                        <div className="absolute inset-0 flex items-center justify-center text-vz-teal/60 text-sm font-mockSerif">
                          {p.name}
                        </div>
                      )}
                    </div>
                    <div className="mt-3">
                      <p className="text-sm text-black line-clamp-1">{p.name}</p>
                      {(p.brand || p.size) && (
                        <p className="text-xs text-black/50">
                          {[p.brand, p.size].filter(Boolean).join(" · ")}
                        </p>
                      )}
                      <p className="text-sm text-black/70 mt-0.5">
                        {formatPriceCents(p.price_cents)}
                      </p>
                      {p.reason && (
                        <p className="mt-1 text-xs text-vz-teal italic line-clamp-2">
                          {p.reason}
                        </p>
                      )}
                    </div>
                  </article>
                );
              })}
            </div>
            <div className="mt-8 text-center">
              <Link href="/produits" className="text-sm font-medium text-vz-teal underline underline-offset-4 hover:text-vz-teal-deep">
                Voir toute la boutique →
              </Link>
            </div>
          </section>
        )}

        {/* CITATION */}
        <section className="bg-vz-bg py-14">
          <p className="max-w-4xl mx-auto px-6 text-center font-mockSerif text-3xl md:text-4xl lg:text-5xl text-vz-teal leading-snug">
            Vintiz : affirmez votre style,<br />
            faites briller vos valeurs.
          </p>
        </section>

        {/* NOTRE CONCEPT */}
        <section className="max-w-7xl mx-auto px-6 py-16 lg:py-24">
          <div className="grid lg:grid-cols-2 gap-10 lg:gap-16 items-start">
            <div>
              <h2 className="font-mockSerif text-4xl md:text-5xl text-vz-teal mb-6">Notre concept</h2>
              <div className="relative aspect-[4/3] rounded-md overflow-hidden bg-stone-200">
                <Image src="/dev/shop-local.jpg" alt="Intérieur boutique Vintiz" fill sizes="(max-width: 1024px) 100vw, 50vw" className="object-cover" />
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
        <section className="bg-vz-bg border-t border-black/5">
          <div className="max-w-7xl mx-auto px-6 py-14 grid md:grid-cols-3 gap-10 items-center">
            <div>
              <p className="font-mockSerif text-4xl text-vz-teal tracking-[0.35em]">V I N T I Z</p>
              <div className="mt-6">
                <AddressBlock />
              </div>
            </div>
            <div className="relative aspect-[3/4] rounded-md overflow-hidden bg-stone-200">
              <Image src="/dev/look-femme.jpg" alt="Look femme Vintiz" fill sizes="(max-width: 768px) 100vw, 33vw" className="object-cover" />
            </div>
            <div className="relative aspect-[3/4] rounded-md overflow-hidden bg-stone-200">
              <Image src="/dev/look-homme.jpg" alt="Look homme Vintiz" fill sizes="(max-width: 768px) 100vw, 33vw" className="object-cover" />
            </div>
          </div>
        </section>
      </main>
      <PublicFooter />
    </>
  );
}
