"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AccountShell from "@/components/account/AccountShell";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ConsentRow {
  purpose: string;
  label: string;
  granted: boolean;
  source: string | null;
  policy_version: string | null;
  recorded_at: string | null;
}

function formatDate(s: string | null): string {
  if (!s) return "—";
  return new Date(s).toLocaleDateString("fr-FR", {
    day: "2-digit",
    month: "long",
    year: "numeric",
  });
}

export default function AccountRgpdPage() {
  const [email, setEmail] = useState("");
  const [consents, setConsents] = useState<ConsentRow[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [actionMsg, setActionMsg] = useState("");
  const [error, setError] = useState("");
  const [deletionPending, setDeletionPending] = useState(false);

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem("vintiz_account_email");
      if (stored) {
        setEmail(stored);
        void loadConsents(stored);
        void loadDeletionStatus(stored);
      }
    } catch {
      /* noop */
    }
  }, []);

  const loadConsents = async (target: string) => {
    const res = await fetch(
      `${API_URL}/api/crm/account/consents?email=${encodeURIComponent(target)}`,
      { cache: "no-store" }
    );
    if (res.ok) {
      setConsents(await res.json());
    }
  };

  const loadDeletionStatus = async (target: string) => {
    const res = await fetch(
      `${API_URL}/api/crm/clients/lookup?email=${encodeURIComponent(target)}`,
      { cache: "no-store" }
    );
    if (res.ok) {
      const body = await res.json();
      setDeletionPending(Boolean(body.client?.deletion_pending));
    }
  };

  const toggle = async (purpose: string, granted: boolean) => {
    setBusy(purpose);
    setError("");
    try {
      const res = await fetch(
        `${API_URL}/api/crm/account/consents/${encodeURIComponent(purpose)}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, granted }),
        }
      );
      if (res.ok) {
        await loadConsents(email);
      } else {
        setError("Modification impossible.");
      }
    } catch {
      setError("Erreur réseau.");
    }
    setBusy(null);
  };

  const exportData = async () => {
    setBusy("export");
    setActionMsg("");
    try {
      const res = await fetch(
        `${API_URL}/api/crm/account/data-export?email=${encodeURIComponent(email)}`,
        { cache: "no-store" }
      );
      if (!res.ok) {
        setError("Échec de l'export.");
      } else {
        const json = await res.json();
        const blob = new Blob([JSON.stringify(json, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `vintiz-mes-donnees-${email}.json`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
        setActionMsg("Vos données ont été téléchargées au format JSON.");
      }
    } catch {
      setError("Erreur réseau.");
    }
    setBusy(null);
  };

  const requestDeletion = async () => {
    if (!confirm("Confirmer la demande de suppression ? Vous disposez de 30 jours pour annuler.")) return;
    setBusy("deletion");
    try {
      const res = await fetch(`${API_URL}/api/crm/account/deletion-request`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      const body = await res.json().catch(() => ({}));
      if (res.ok) {
        setDeletionPending(true);
        setActionMsg(
          `Demande enregistrée. Vos données seront supprimées le ${formatDate(body.purge_after)}.`
        );
      } else {
        setError(body?.detail || "Échec de la demande.");
      }
    } catch {
      setError("Erreur réseau.");
    }
    setBusy(null);
  };

  const cancelDeletion = async () => {
    setBusy("deletion");
    try {
      const res = await fetch(`${API_URL}/api/crm/account/deletion-cancel`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      if (res.ok) {
        setDeletionPending(false);
        setActionMsg("Demande de suppression annulée.");
      } else {
        setError("Échec de l'annulation.");
      }
    } catch {
      setError("Erreur réseau.");
    }
    setBusy(null);
  };

  if (!email) {
    return (
      <AccountShell title="Confidentialité & RGPD">
        <Link href="/account/login" className="text-teal underline">Se connecter</Link>
      </AccountShell>
    );
  }

  return (
    <AccountShell
      title="Confidentialité & RGPD"
      intro="Gérez vos consentements, exportez vos données ou demandez la suppression de votre compte."
    >
      <div className="space-y-8">
        {actionMsg && (
          <div className="p-3 bg-teal/10 text-teal rounded-lg text-sm">{actionMsg}</div>
        )}
        {error && <div className="p-3 bg-red-50 text-red-700 rounded-lg text-sm">{error}</div>}

        <section>
          <h2 className="text-xl font-display font-semibold text-black mb-3">Mes consentements</h2>
          <ul className="space-y-2">
            {consents.map((c) => (
              <li key={c.purpose} className="bg-white rounded-2xl shadow-sm p-4 flex items-start justify-between gap-3">
                <div>
                  <p className="font-medium text-black">{c.label}</p>
                  <p className="text-xs text-gray-500 mt-1">
                    {c.granted ? "Activé" : "Désactivé"}
                    {c.recorded_at && ` · dernière mise à jour ${formatDate(c.recorded_at)}`}
                    {c.source && ` · source ${c.source}`}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => toggle(c.purpose, !c.granted)}
                  disabled={busy === c.purpose}
                  className={
                    "shrink-0 px-3 py-2 rounded-lg text-sm font-medium " +
                    (c.granted
                      ? "bg-pink/40 text-black"
                      : "bg-teal text-white")
                  }
                >
                  {busy === c.purpose ? "…" : c.granted ? "Désactiver" : "Activer"}
                </button>
              </li>
            ))}
          </ul>
        </section>

        <section>
          <h2 className="text-xl font-display font-semibold text-black mb-3">Mes données</h2>
          <div className="bg-white rounded-2xl shadow-sm p-5 space-y-3">
            <p className="text-sm text-gray-700">
              Téléchargez l&apos;intégralité des données que Vintiz détient sur
              vous, conformément à l&apos;article 20 RGPD (droit à la
              portabilité). Format JSON portable.
            </p>
            <button
              type="button"
              onClick={exportData}
              disabled={busy === "export"}
              className="bg-teal text-white px-4 py-2 rounded-lg font-medium disabled:opacity-50"
            >
              {busy === "export" ? "Export en cours…" : "Télécharger mes données"}
            </button>
          </div>
        </section>

        <section>
          <h2 className="text-xl font-display font-semibold text-black mb-3">Suppression de mon compte</h2>
          <div className="bg-white rounded-2xl shadow-sm p-5 space-y-3">
            {!deletionPending ? (
              <>
                <p className="text-sm text-gray-700">
                  Vos données sont effacées sous 30 jours après la demande. Vous
                  pouvez annuler à tout moment pendant ce délai.
                </p>
                <button
                  type="button"
                  onClick={requestDeletion}
                  disabled={busy === "deletion"}
                  className="bg-red-600 text-white px-4 py-2 rounded-lg font-medium disabled:opacity-50"
                >
                  {busy === "deletion" ? "…" : "Demander la suppression"}
                </button>
              </>
            ) : (
              <>
                <p className="text-sm text-gray-700">
                  Une demande de suppression est en cours. Vos données seront
                  effacées sous 30 jours sauf annulation.
                </p>
                <button
                  type="button"
                  onClick={cancelDeletion}
                  disabled={busy === "deletion"}
                  className="bg-teal text-white px-4 py-2 rounded-lg font-medium disabled:opacity-50"
                >
                  {busy === "deletion" ? "…" : "Annuler la suppression"}
                </button>
              </>
            )}
          </div>
        </section>

        <section className="text-sm text-gray-600">
          <p>
            DPO : <a href="mailto:dpo@solidarite-textiles.fr" className="text-teal underline">dpo@solidarite-textiles.fr</a>
          </p>
          <p className="mt-1">
            Voir aussi :{" "}
            <Link href="/confidentialite" className="text-teal underline">Politique de confidentialité</Link>{" · "}
            <Link href="/cgv" className="text-teal underline">CGV</Link>{" · "}
            <Link href="/mentions-legales" className="text-teal underline">Mentions légales</Link>
          </p>
        </section>
      </div>
    </AccountShell>
  );
}
