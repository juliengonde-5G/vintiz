import type { Metadata, Viewport } from "next";
import { Lexend_Mega, Poppins } from "next/font/google";
import CompanionDrawer from "@/components/ai/CompanionDrawer";
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
  themeColor: "#0B7A6A",
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
  icons: {
    icon: "/logo-teal.png",
    apple: "/logo-teal.png",
    shortcut: "/logo-teal.png",
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
        {/* Web app manifest — drives Add-to-Home-Screen on both iOS and Android. */}
        <link rel="manifest" href="/manifest.json" />
        {/* Status bar color — Chrome Android tints it teal on PWA install. */}
        <meta name="theme-color" content="#0B7A6A" />
        {/* iOS home-screen icon + standalone hint (kept for backward compat with
            existing iPad installs ; no-op on Android). */}
        <link rel="apple-touch-icon" href="/icon-192.png" />
        <meta name="apple-mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-status-bar-style" content="default" />
        {/* Generic Android equivalent — Chrome reads this on PWA install. */}
        <meta name="mobile-web-app-capable" content="yes" />
      </head>
      <body className="font-sans antialiased bg-background text-foreground">
        {children}
        <CompanionDrawer />
      </body>
    </html>
  );
}
