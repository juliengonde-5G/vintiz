import type { MetadataRoute } from "next";

/**
 * Web App Manifest pour vintiz.fr — déployé en `/manifest.webmanifest`
 * par Next.js. Permet l'installation "Add to home screen" iOS/Android
 * et l'expérience PWA standalone.
 *
 * Couleurs alignées sur la charte « Sauge Néo » v3 :
 *   - background_color = vz-bg (#F6F5F1)
 *   - theme_color      = vz-teal (#0B7A6A)
 */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Vintiz — Boutique seconde main premium Vernon",
    short_name: "Vintiz",
    description:
      "Boutique de vêtements de seconde main premium à Vernon, Normandie. Personal Shopper IA, fidélité, sélection curée.",
    start_url: "/",
    scope: "/",
    display: "standalone",
    orientation: "portrait",
    background_color: "#F6F5F1",
    theme_color: "#0B7A6A",
    lang: "fr-FR",
    dir: "ltr",
    categories: ["shopping", "lifestyle"],
    icons: [
      {
        src: "/logo-teal.png",
        sizes: "192x192",
        type: "image/png",
        purpose: "any",
      },
      {
        src: "/logo-teal.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "any",
      },
      {
        src: "/logo-teal.png",
        sizes: "192x192",
        type: "image/png",
        purpose: "maskable",
      },
      {
        src: "/logo-teal.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable",
      },
    ],
  };
}
