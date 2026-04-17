import type { Metadata } from "next";
import { Lexend_Mega, Poppins } from "next/font/google";
import "./globals.css";
import CookieBanner from "@/components/CookieBanner";

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

export const metadata: Metadata = {
  title: "Vintiz | Boutique seconde main premium - Vernon",
  description:
    "Vintiz, boutique de vetements de seconde main premium a Vernon. Marques selectionnees, pieces uniques, mode responsable. 6 rue Saint-Jacques, 27200 Vernon.",
  keywords: "seconde main, vintage, premium, vetements femme, Vernon, friperie haut de gamme, mode responsable, Sandro, Maje, Isabel Marant",
  openGraph: {
    title: "Vintiz | Boutique seconde main premium - Vernon",
    description:
      "Mode premium de seconde main. Pieces uniques selectionnees avec soin a Vernon.",
    type: "website",
    locale: "fr_FR",
    siteName: "Vintiz",
    url: "https://vintiz.fr",
  },
  twitter: {
    card: "summary_large_image",
    title: "Vintiz | Boutique seconde main premium",
    description: "Mode premium de seconde main a Vernon.",
  },
  alternates: {
    canonical: "https://vintiz.fr",
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="fr" className={`${lexendMega.variable} ${poppins.variable}`}>
      <head>
        <link rel="icon" href="/logo-teal.png" type="image/png" />
        <link rel="apple-touch-icon" href="/logo-teal.png" />
      </head>
      <body className="font-sans antialiased bg-cream text-black">
        {children}
        <CookieBanner />
      </body>
    </html>
  );
}
