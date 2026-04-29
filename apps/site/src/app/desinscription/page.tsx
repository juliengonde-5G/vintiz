import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Désinscription newsletter",
  description: "Désinscription de la newsletter Vintiz.",
  robots: { index: false, follow: false },
};

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Result =
  | { ok: true; message: string; email?: string }
  | { ok: false; message: string };

async function unsubscribe(token: string | undefined): Promise<Result> {
  if (!token) {
    return { ok: false, message: "Lien invalide : jeton manquant." };
  }
  try {
    const res = await fetch(
      `${API_URL}/api/newsletter/unsubscribe?token=${encodeURIComponent(token)}`,
      { cache: "no-store" }
    );
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      return {
        ok: false,
        message:
          typeof data?.detail === "string"
            ? data.detail
            : "Le lien de désinscription est invalide ou a expiré.",
      };
    }
    return { ok: true, message: data.message ?? "Désinscription effectuée.", email: data.email };
  } catch {
    return { ok: false, message: "Impossible de contacter le serveur. Réessayez plus tard." };
  }
}

export default async function UnsubscribePage({
  searchParams,
}: {
  searchParams: { token?: string };
}) {
  const result = await unsubscribe(searchParams.token);

  return (
    <>
      <Navbar />
      <section className="pt-28 pb-20 px-6 bg-vz-bg min-h-screen">
        <div className="max-w-xl mx-auto bg-white rounded-2xl shadow-sm border border-vz-accent-soft/30 px-6 py-8 text-center">
          <h1 className="font-display text-2xl text-black mb-4">
            Désinscription newsletter
          </h1>
          {result.ok ? (
            <>
              <div className="bg-vz-teal/10 border border-vz-teal/30 rounded-lg p-4 text-vz-teal mb-4">
                {result.message}
              </div>
              {result.email && (
                <p className="text-sm text-black/60 mb-4">
                  Adresse concernée : <span className="font-medium">{result.email}</span>
                </p>
              )}
              <p className="text-sm text-black/60">
                Vous pouvez vous réinscrire à tout moment depuis{" "}
                <Link href="/" className="underline text-vz-teal">
                  la page d&apos;accueil
                </Link>
                .
              </p>
            </>
          ) : (
            <>
              <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 mb-4">
                {result.message}
              </div>
              <p className="text-sm text-black/60">
                Si le problème persiste, contactez{" "}
                <a href="mailto:dpo@solidarite-textiles.fr" className="underline text-vz-teal">
                  dpo@solidarite-textiles.fr
                </a>
                .
              </p>
            </>
          )}
        </div>
      </section>
      <Footer />
    </>
  );
}
