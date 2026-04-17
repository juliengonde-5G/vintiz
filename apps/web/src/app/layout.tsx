import type { Metadata, Viewport } from "next";
import { Lexend_Mega, Poppins } from "next/font/google";
import "./globals.css";

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

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  themeColor: "#FFC5DF",
};

export const metadata: Metadata = {
  title: "Vintiz - Back Office",
  description: "Vintiz Boutique Back-Office",
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "Vintiz",
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
        <link rel="apple-touch-icon" href="/icon-192.png" />
        <meta name="apple-mobile-web-app-capable" content="yes" />
      </head>
      <body className="font-sans antialiased bg-background text-foreground">
        {children}
      </body>
    </html>
  );
}
