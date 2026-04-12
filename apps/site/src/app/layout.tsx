import type { Metadata } from "next";
import "./globals.css";
import CookieBanner from "@/components/CookieBanner";

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
    <html lang="fr">
      <head>
        <link rel="icon" href="/logo-rose.png" type="image/png" />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=Playfair+Display:ital,wght@0,400;0,500;0,600;0,700;1,400;1,500&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="font-sans antialiased">
        {children}
        <CookieBanner />
      </body>
    </html>
  );
}
