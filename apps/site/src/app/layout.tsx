import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Vintiz - Ouverture Prochaine | Vernon",
  description:
    "Vintiz, votre nouvelle boutique de vêtements de seconde main premium à Vernon. Ouverture prochaine au 6 rue Saint-Jacques, 27200 Vernon.",
  openGraph: {
    title: "Vintiz - Ouverture Prochaine | Vernon",
    description:
      "Votre nouvelle boutique de vêtements de seconde main premium à Vernon.",
    type: "website",
    locale: "fr_FR",
    siteName: "Vintiz",
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
      </body>
    </html>
  );
}
