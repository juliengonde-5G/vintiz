import type { Metadata } from "next";
import Link from "next/link";
import PublicFooter from "@/components/PublicFooter";
import PublicHeader from "@/components/PublicHeader";
import ContactForm from "./ContactForm";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://vintiz.fr";

export const metadata: Metadata = {
  title: "Contact",
  description:
    "Vintiz — 6 rue Saint-Jacques, 27200 Vernon. Boutique seconde main premium en Normandie. Tél, e-mail, horaires et accès.",
  alternates: {
    canonical: `${SITE_URL}/contact`,
    languages: {
      "fr-FR": `${SITE_URL}/contact`,
      "en-US": `${SITE_URL}/en/contact`,
    },
  },
  openGraph: {
    title: "Contact | Vintiz Vernon",
    description:
      "Vintiz — 6 rue Saint-Jacques, 27200 Vernon. Tél, e-mail et accès.",
    url: `${SITE_URL}/contact`,
    type: "website",
    locale: "fr_FR",
  },
};

const contactJsonLd = {
  "@context": "https://schema.org",
  "@type": "ContactPage",
  name: "Contact Vintiz",
  url: `${SITE_URL}/contact`,
  mainEntity: {
    "@type": "ClothingStore",
    name: "Vintiz",
    url: SITE_URL,
    email: "contact@vintiz.fr",
    telephone: "+33 2 77 19 01 97",
    address: {
      "@type": "PostalAddress",
      streetAddress: "6 rue Saint-Jacques",
      addressLocality: "Vernon",
      postalCode: "27200",
      addressRegion: "Normandie",
      addressCountry: "FR",
    },
    geo: {
      "@type": "GeoCoordinates",
      latitude: 49.0926,
      longitude: 1.4773,
    },
    openingHoursSpecification: [
      {
        "@type": "OpeningHoursSpecification",
        dayOfWeek: [
          "Tuesday",
          "Wednesday",
          "Thursday",
          "Friday",
          "Saturday",
        ],
        opens: "10:30",
        closes: "19:00",
      },
    ],
    contactPoint: [
      {
        "@type": "ContactPoint",
        contactType: "customer service",
        telephone: "+33 2 77 19 01 97",
        email: "contact@vintiz.fr",
        areaServed: "FR",
        availableLanguage: ["French"],
      },
    ],
  },
};

export default function ContactPage() {
  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(contactJsonLd) }}
      />
      <PublicHeader />
      <main className="bg-vz-bg">
        <section className="max-w-6xl mx-auto px-6 py-16 lg:py-20">
          <p className="text-xs uppercase tracking-[0.18em] text-vz-teal font-medium mb-3">
            Nous joindre
          </p>
          <h1 className="font-display font-[450] text-4xl sm:text-5xl text-vz-ink leading-tight tracking-[-0.015em]">
            Venez nous voir à Vernon.
          </h1>
          <p className="mt-6 text-lg text-vz-ink-soft max-w-2xl leading-relaxed">
            Vintiz vous accueille au cœur de Vernon, à 5 minutes à pied de la
            collégiale et 10 minutes en voiture de Giverny. Une question, une
            envie, ou simplement nous saluer — toutes les bonnes raisons sont
            les bonnes.
          </p>

          <div className="mt-12 grid lg:grid-cols-2 gap-12 lg:gap-16">
            {/* Coordonnées + horaires */}
            <div className="space-y-8">
              <section>
                <h2 className="font-display text-xl text-vz-ink mb-4">
                  Adresse
                </h2>
                <p className="text-vz-ink leading-relaxed">
                  6 rue Saint-Jacques
                  <br />
                  27200 Vernon — Normandie
                </p>
                <a
                  href="https://www.google.com/maps/place/6+Rue+St+Jacques,+27200+Vernon"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-3 inline-flex items-center gap-2 text-sm font-medium text-vz-teal hover:underline"
                >
                  Itinéraire Google Maps
                  <svg
                    width="14"
                    height="14"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M5 12h14M13 6l6 6-6 6" />
                  </svg>
                </a>
              </section>

              <section>
                <h2 className="font-display text-xl text-vz-ink mb-4">
                  Horaires
                </h2>
                <p className="text-vz-ink leading-relaxed">
                  Du mardi au samedi
                  <br />
                  De 10h30 à 19h
                </p>
                <p className="mt-2 text-sm text-vz-ink-mute">
                  Fermé dimanche et lundi.
                </p>
              </section>

              <section>
                <h2 className="font-display text-xl text-vz-ink mb-4">
                  Téléphone
                </h2>
                <p className="text-vz-ink">
                  <a
                    href="tel:+33277190197"
                    className="hover:text-vz-teal transition-colors"
                  >
                    02 77 19 01 97
                  </a>
                </p>
              </section>

              <section>
                <h2 className="font-display text-xl text-vz-ink mb-4">
                  Nous écrire
                </h2>
                <p className="text-vz-ink">
                  <a
                    href="mailto:contact@vintiz.fr"
                    className="hover:text-vz-teal transition-colors"
                  >
                    contact@vintiz.fr
                  </a>
                </p>
                <p className="mt-2 text-sm text-vz-ink-mute">
                  Réponse sous 48 h ouvrées.
                </p>
              </section>

              <section>
                <h2 className="font-display text-xl text-vz-ink mb-4">
                  Comment venir
                </h2>
                <ul className="space-y-2 text-vz-ink leading-relaxed">
                  <li>
                    <span className="text-vz-ink-mute">Depuis Évreux :</span> ~
                    30 min (D6155 / N13)
                  </li>
                  <li>
                    <span className="text-vz-ink-mute">
                      Depuis Mantes-la-Jolie :
                    </span>{" "}
                    ~ 25 min (A13)
                  </li>
                  <li>
                    <span className="text-vz-ink-mute">Depuis Giverny :</span>{" "}
                    ~ 10 min
                  </li>
                  <li>
                    <span className="text-vz-ink-mute">
                      Depuis Paris Saint-Lazare :
                    </span>{" "}
                    Gare Vernon-Giverny, ~ 50 min en train + 10 min à pied
                  </li>
                </ul>
              </section>

              <section>
                <h2 className="font-display text-xl text-vz-ink mb-4">
                  Suivez-nous
                </h2>
                <div className="flex gap-3">
                  <a
                    href="https://www.instagram.com/vintiz.fr/"
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label="Instagram Vintiz"
                    className="w-11 h-11 rounded-full border border-vz-teal/30 flex items-center justify-center text-vz-teal hover:bg-vz-teal hover:text-white transition-colors"
                  >
                    <svg
                      width="18"
                      height="18"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <rect x="2" y="2" width="20" height="20" rx="5" ry="5" />
                      <path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z" />
                      <line x1="17.5" y1="6.5" x2="17.51" y2="6.5" />
                    </svg>
                  </a>
                  <a
                    href="https://www.facebook.com/vintiz.fr"
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label="Facebook Vintiz"
                    className="w-11 h-11 rounded-full border border-vz-teal/30 flex items-center justify-center text-vz-teal hover:bg-vz-teal hover:text-white transition-colors"
                  >
                    <svg
                      width="18"
                      height="18"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <path d="M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3z" />
                    </svg>
                  </a>
                  <a
                    href="https://www.tiktok.com/@vintiz.fr"
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label="TikTok Vintiz"
                    className="w-11 h-11 rounded-full border border-vz-teal/30 flex items-center justify-center text-vz-teal hover:bg-vz-teal hover:text-white transition-colors"
                  >
                    <svg
                      width="18"
                      height="18"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <path d="M9 12a4 4 0 1 0 4 4V4a5 5 0 0 0 5 5" />
                    </svg>
                  </a>
                </div>
              </section>
            </div>

            {/* Formulaire */}
            <div>
              <ContactForm />

              <p className="mt-6 text-xs text-vz-ink-mute">
                En envoyant ce message, vous acceptez d&apos;être recontactée par
                e-mail ou téléphone par Vintiz. Vos données ne sont pas
                réutilisées à des fins marketing — voir notre{" "}
                <Link
                  href="/confidentialite"
                  className="underline underline-offset-2 hover:text-vz-teal"
                >
                  politique de confidentialité
                </Link>
                .
              </p>
            </div>
          </div>
        </section>

        {/* Carte */}
        <section className="bg-vz-bg-alt border-y border-black/5">
          <div className="max-w-6xl mx-auto px-6 py-12">
            <h2 className="font-display text-2xl text-vz-ink mb-6">
              La boutique sur la carte
            </h2>
            <div className="aspect-[16/9] sm:aspect-[21/9] rounded-2xl overflow-hidden border border-black/5 bg-vz-surface shadow-sm">
              <iframe
                title="Vintiz — 6 rue Saint-Jacques, 27200 Vernon"
                src="https://maps.google.com/maps?q=6+Rue+Saint-Jacques+27200+Vernon&output=embed&hl=fr"
                className="w-full h-full"
                loading="lazy"
                referrerPolicy="no-referrer-when-downgrade"
              />
            </div>
            <p className="mt-3 text-xs text-vz-ink-mute">
              <a
                href="https://www.google.com/maps/place/6+Rue+Saint-Jacques,+27200+Vernon,+France"
                target="_blank"
                rel="noopener noreferrer"
                className="underline underline-offset-2 hover:text-vz-teal"
              >
                Ouvrir dans Google Maps
              </a>
              .
            </p>
          </div>
        </section>
      </main>
      <PublicFooter />
    </>
  );
}
