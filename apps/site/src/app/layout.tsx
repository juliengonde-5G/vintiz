import type { Metadata, Viewport } from "next";
import { Lexend_Mega, Poppins } from "next/font/google";
import Script from "next/script";
import "./globals.css";
import CookieBanner from "@/components/CookieBanner";
import Analytics from "@/components/Analytics";

// Charte graphique Vintiz v2 : Lexend Mega (titres) + Poppins (texte).
const lexendMega = Lexend_Mega({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-display",
  display: "swap",
});

const poppins = Poppins({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
  variable: "--font-body",
  display: "swap",
});

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://vintiz.fr";
const GA_ID = process.env.NEXT_PUBLIC_GA_ID || "";

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#F6F5F1",
};

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "Vintiz | Boutique seconde main premium à Vernon (27)",
    template: "%s | Vintiz",
  },
  description:
    "Vintiz, boutique de vêtements de seconde main premium à Vernon en Normandie. Marques sélectionnées (Sandro, Maje, Isabel Marant…), pièces uniques, mode responsable. 6 rue Saint-Jacques, 27200 Vernon.",
  keywords: [
    "seconde main",
    "friperie Vernon",
    "vintage premium",
    "vêtements femme Vernon",
    "mode responsable Normandie",
    "dépôt-vente Vernon",
    "Sandro occasion",
    "Maje occasion",
    "Isabel Marant occasion",
    "boutique vintage Eure",
  ],
  authors: [{ name: "Vintiz" }],
  creator: "Vintiz",
  publisher: "Vintiz",
  openGraph: {
    title: "Vintiz | Boutique seconde main premium à Vernon",
    description:
      "Votre nouvelle destination Slow Fashion premium à Vernon, Normandie. Pièces uniques sélectionnées avec soin — 6 rue Saint-Jacques.",
    type: "website",
    locale: "fr_FR",
    siteName: "Vintiz",
    url: SITE_URL,
    images: [
      {
        url: "/logo-teal.png",
        width: 512,
        height: 512,
        alt: "Vintiz — boutique seconde main premium Vernon",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Vintiz | Boutique seconde main premium",
    description: "Votre nouvelle destination Slow Fashion premium à Vernon, Normandie.",
    images: ["/logo-teal.png"],
  },
  alternates: {
    canonical: SITE_URL,
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
  category: "shopping",
  verification: {
    google: process.env.NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION,
  },
  manifest: "/manifest.webmanifest",
  applicationName: "Vintiz",
  appleWebApp: {
    capable: true,
    title: "Vintiz",
    statusBarStyle: "default",
  },
  icons: {
    icon: [
      { url: "/logo-teal.png", type: "image/png", sizes: "192x192" },
      { url: "/logo-teal.png", type: "image/png", sizes: "512x512" },
    ],
    apple: [
      { url: "/logo-teal.png", sizes: "180x180", type: "image/png" },
    ],
    shortcut: "/logo-teal.png",
  },
};

const jsonLd = {
  "@context": "https://schema.org",
  "@type": "ClothingStore",
  name: "Vintiz",
  description:
    "Boutique de vêtements de seconde main premium à Vernon, Normandie.",
  url: SITE_URL,
  logo: `${SITE_URL}/logo-teal.png`,
  image: `${SITE_URL}/logo-teal.png`,
  priceRange: "€€",
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
      dayOfWeek: ["Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
      opens: "10:00",
      closes: "19:00",
    },
  ],
  sameAs: [
    "https://www.instagram.com/vintiz.fr/",
    "https://www.facebook.com/vintiz.fr",
    "https://www.tiktok.com/@vintiz.fr",
  ],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="fr" className={`${lexendMega.variable} ${poppins.variable}`}>
      <head>
        {/* icon, apple-touch-icon, manifest et canonical sont émis par
            Next.js depuis `metadata` ci-dessus — pas de balises manuelles
            ici pour éviter les doublons (W-06 audit SEO). */}
        <meta name="geo.region" content="FR-27" />
        <meta name="geo.placename" content="Vernon" />
        <meta name="geo.position" content="49.0926;1.4773" />
        <meta name="ICBM" content="49.0926, 1.4773" />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
        {GA_ID && (
          <Script
            id="ga-consent-defaults"
            strategy="beforeInteractive"
            dangerouslySetInnerHTML={{
              __html: `
                window.dataLayer = window.dataLayer || [];
                function gtag(){dataLayer.push(arguments);}
                window.gtag = gtag;
                gtag('consent', 'default', {
                  'ad_storage': 'denied',
                  'ad_user_data': 'denied',
                  'ad_personalization': 'denied',
                  'analytics_storage': 'denied',
                  'wait_for_update': 500,
                });
              `,
            }}
          />
        )}
      </head>
      <body className="font-sans antialiased bg-vz-bg text-black">
        {children}
        <CookieBanner />
        <Analytics gaId={GA_ID} />
      </body>
    </html>
  );
}
