"use client";

import { useEffect, useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Step = "email" | "code";
type Channel = "email" | "sms";
type Mode = "login" | "register";

export default function AccountLoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("login");
  const [step, setStep] = useState<Step>("email");
  const [channel, setChannel] = useState<Channel>("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [firstName, setFirstName] = useState("");
  const [optinNewsletter, setOptinNewsletter] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  // Passwordless login via the email link: ?token=… → verify directly, no code.
  const [linkBusy, setLinkBusy] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const token = new URLSearchParams(window.location.search).get("token");
    if (!token) return;
    setLinkBusy(true);
    (async () => {
      try {
        const res = await fetch(`${API_URL}/api/auth/magic-link/verify-token`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ token }),
        });
        if (res.ok) {
          const data = await res.json();
          try {
            window.localStorage.setItem("vintiz_account_token", data.access_token);
            if (data.email) {
              window.localStorage.setItem("vintiz_account_email", data.email);
            }
          } catch {
            /* private mode */
          }
          router.push("/account");
          return;
        }
        setError("Ce lien de connexion est invalide ou expiré. Demandez-en un nouveau.");
      } catch {
        setError("Erreur réseau. Réessayez.");
      }
      setLinkBusy(false);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const registerAccount = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setInfo("");
    setBusy(true);
    try {
      // Always 202 — same response whether the email is new or known
      // (anti-enumeration). Creates the Client if needed + sends a magic link.
      await fetch(`${API_URL}/api/crm/account/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: email.trim().toLowerCase(),
          first_name: firstName.trim() || null,
          optin_newsletter: optinNewsletter,
        }),
      });
      setStep("code");
      setInfo(
        "Votre espace est prêt ! Un email vient de partir : cliquez sur le " +
          "lien de connexion (ou saisissez le code ci-dessous) pour y accéder.",
      );
    } catch {
      setError("Erreur réseau. Réessayez.");
    }
    setBusy(false);
  };

  const requestCode = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setInfo("");
    setBusy(true);
    try {
      // Backend accepts an email OR phone in the same `email` field.
      const identifier = channel === "email"
        ? email.trim().toLowerCase()
        : email.trim().replace(/[\s.\-]/g, "");
      // The endpoint always returns 204; we don't disclose whether the account exists.
      await fetch(`${API_URL}/api/auth/magic-link/request`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: identifier }),
      });
      setStep("code");
      setInfo(
        channel === "sms"
          ? "Si un compte existe avec ce numéro, un code à 6 chiffres vient d'être envoyé par SMS."
          : "Si un compte existe avec cet email, un code à 6 chiffres vient d'être envoyé. Pensez à vérifier vos spams.",
      );
    } catch {
      setError("Erreur réseau. Réessayez.");
    }
    setBusy(false);
  };

  const verifyCode = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const identifier = channel === "email"
        ? email.trim().toLowerCase()
        : email.trim().replace(/[\s.\-]/g, "");
      const res = await fetch(`${API_URL}/api/auth/magic-link/verify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: identifier, code: code.trim() }),
      });
      if (res.ok) {
        const data = await res.json();
        // PR1: stash the JWT in localStorage so /account pages can call the API.
        // PR3 will move this to an HttpOnly cookie via a Next API route.
        try {
          window.localStorage.setItem("vintiz_account_token", data.access_token);
          window.localStorage.setItem("vintiz_account_email", email.trim().toLowerCase());
        } catch {
          /* private mode — the account pages still receive the token via redirect */
        }
        router.push("/account");
      } else if (res.status === 429) {
        setError("Trop de tentatives. Patientez avant de redemander un code.");
      } else {
        setError("Code invalide ou expiré. Demandez un nouveau code.");
      }
    } catch {
      setError("Erreur réseau. Réessayez.");
    }
    setBusy(false);
  };

  return (
    <main className="min-h-screen bg-vz-bg">
      <Navbar />
      <section className="max-w-md mx-auto px-4 pt-16 pb-24">
        <h1 className="text-3xl font-display font-bold text-black mb-2">Mon espace Vintiz</h1>
        <p className="text-gray-600 mb-6">
          Recevez un email&nbsp;: cliquez sur le lien de connexion, ou saisissez
          le code à 6 chiffres — aucun mot de passe à retenir.
        </p>

        {step === "email" && (
          <div className="mb-6 inline-flex border border-vz-line rounded-full p-0.5 text-sm font-medium">
            <button
              type="button"
              onClick={() => { setMode("login"); setError(""); setInfo(""); }}
              className={`px-5 py-2 rounded-full transition-colors ${
                mode === "login" ? "bg-vz-teal text-white" : "text-vz-ink-mute hover:text-vz-ink"
              }`}
            >
              Se connecter
            </button>
            <button
              type="button"
              onClick={() => { setMode("register"); setChannel("email"); setError(""); setInfo(""); }}
              className={`px-5 py-2 rounded-full transition-colors ${
                mode === "register" ? "bg-vz-teal text-white" : "text-vz-ink-mute hover:text-vz-ink"
              }`}
            >
              Créer mon espace
            </button>
          </div>
        )}

        {linkBusy && (
          <div className="mb-6 p-3 bg-vz-teal/10 text-vz-teal rounded-lg text-sm">
            Connexion en cours…
          </div>
        )}

        {step === "email" && (
          <form onSubmit={mode === "register" ? registerAccount : requestCode} className="space-y-4">
            {mode === "login" && (
            <div className="inline-flex border border-vz-line rounded-full p-0.5 text-xs font-medium">
              <button
                type="button"
                onClick={() => { setChannel("email"); setEmail(""); }}
                className={`px-4 py-1.5 rounded-full transition-colors ${
                  channel === "email" ? "bg-vz-teal text-white" : "text-vz-ink-mute hover:text-vz-ink"
                }`}
              >
                Par email
              </button>
              <button
                type="button"
                onClick={() => { setChannel("sms"); setEmail(""); }}
                className={`px-4 py-1.5 rounded-full transition-colors ${
                  channel === "sms" ? "bg-vz-teal text-white" : "text-vz-ink-mute hover:text-vz-ink"
                }`}
              >
                Par SMS
              </button>
            </div>
            )}
            {mode === "register" && (
              <div>
                <label className="block text-sm text-gray-700 mb-1" htmlFor="firstname-input">
                  Prénom <span className="text-vz-ink-mute">(facultatif)</span>
                </label>
                <input
                  id="firstname-input"
                  type="text"
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                  placeholder="Léa"
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-vz-teal focus:border-vz-teal"
                />
              </div>
            )}
            <div>
              <label className="block text-sm text-gray-700 mb-1" htmlFor="email-input">
                {mode === "register" || channel === "email" ? "Email" : "Téléphone"}
              </label>
              <input
                id="email-input"
                type={mode === "register" || channel === "email" ? "email" : "tel"}
                inputMode={mode === "register" || channel === "email" ? "email" : "tel"}
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder={mode === "register" || channel === "email" ? "vous@email.fr" : "+33 6 12 34 56 78"}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-vz-teal focus:border-vz-teal"
              />
              <p className="text-xs text-vz-ink-mute mt-1">
                {mode === "register"
                  ? "Nous vous envoyons un lien de connexion pour activer votre espace."
                  : channel === "email"
                  ? "Le code arrive en 30 s. Vérifiez vos spams si besoin."
                  : "Le SMS arrive en quelques secondes. Tarif opérateur standard."}
              </p>
            </div>
            {mode === "register" && (
              <label className="flex items-start gap-2 text-xs text-gray-600">
                <input
                  type="checkbox"
                  checked={optinNewsletter}
                  onChange={(e) => setOptinNewsletter(e.target.checked)}
                  className="mt-0.5"
                />
                <span>
                  Je souhaite recevoir les nouveautés et offres Vintiz par email.
                  Vous pourrez vous désinscrire à tout moment.
                </span>
              </label>
            )}
            <button
              type="submit"
              disabled={busy || !email}
              className="w-full bg-vz-teal text-white py-3 rounded-lg font-medium hover:bg-vz-teal/90 disabled:opacity-50"
            >
              {busy
                ? "Envoi…"
                : mode === "register"
                ? "Créer mon espace"
                : channel === "email"
                ? "Recevoir mon code par email"
                : "Recevoir mon code par SMS"}
            </button>
          </form>
        )}

        {step === "code" && (
          <form onSubmit={verifyCode} className="space-y-4">
            {info && (
              <div className="p-3 bg-vz-teal/10 text-vz-teal rounded-lg text-sm">{info}</div>
            )}
            <div className="p-3 bg-vz-bg-alt border border-vz-line rounded-lg text-xs text-vz-ink-soft space-y-1">
              <p>
                <strong>Le code n&apos;arrive pas&nbsp;?</strong>
              </p>
              <ul className="list-disc list-inside space-y-0.5">
                <li>Vérifiez le dossier spam / courrier indésirable.</li>
                <li>Le délai d&apos;arrivée est généralement de 30 s à 2 min.</li>
                <li>Sur SMS, vérifiez que le numéro saisi commence par +33.</li>
                <li>Essayez l&apos;autre canal (email / SMS) en revenant en arrière.</li>
              </ul>
            </div>
            <div>
              <label className="block text-sm text-gray-700 mb-1" htmlFor="code-input">
                Code à 6 chiffres
              </label>
              <input
                id="code-input"
                type="text"
                inputMode="numeric"
                pattern="\d{6}"
                maxLength={6}
                required
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                placeholder="000000"
                className="w-full px-4 py-3 border border-gray-300 rounded-lg text-center text-2xl tracking-[0.5em] focus:ring-2 focus:ring-vz-teal focus:border-vz-teal"
                autoFocus
              />
            </div>
            <button
              type="submit"
              disabled={busy || code.length !== 6}
              className="w-full bg-vz-teal text-white py-3 rounded-lg font-medium hover:bg-vz-teal/90 disabled:opacity-50"
            >
              {busy ? "Vérification…" : "Me connecter"}
            </button>
            <button
              type="button"
              onClick={() => {
                setStep("email");
                setCode("");
                setError("");
                setInfo("");
              }}
              className="w-full text-sm text-gray-600 underline"
            >
              Modifier l&apos;email ou redemander un code
            </button>
          </form>
        )}

        {error && <div className="mt-4 p-3 bg-red-50 text-red-700 rounded-lg text-sm">{error}</div>}

        <p className="mt-8 text-xs text-gray-500">
          La carte de fidélité est gratuite — adhérez en boutique à Vernon.
          1 € dépensé = 1 point. 100 points = bon de 8 €. Validité 24 mois sans activité.
        </p>
      </section>
      <Footer />
    </main>
  );
}
