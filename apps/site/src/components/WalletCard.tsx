"use client";

import { useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface WalletPayload {
  client_id: string;
  holder_name: string;
  membership_number: string;
  tier: string;
  points: number;
  benefit_text: string;
  primary_color: string;
  qr_payload: string;
  apple_signed_available?: boolean;
  google_save_available?: boolean;
}

const TIER_LABELS: Record<string, string> = {
  bronze: "Bronze",
  silver: "Argent",
  gold: "Or",
};

export default function WalletCard({ email }: { email: string }) {
  const [data, setData] = useState<WalletPayload | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    fetch(
      `${API_URL}/api/crm/account/wallet?email=${encodeURIComponent(email)}`,
      { cache: "no-store" },
    )
      .then(async (res) => {
        if (cancelled) return;
        if (res.ok) setData(await res.json());
        else setError("Wallet indisponible.");
      })
      .catch(() => {
        if (!cancelled) setError("Erreur réseau.");
      });
    return () => {
      cancelled = true;
    };
  }, [email]);

  if (error) {
    return (
      <p className="text-sm text-gray-400 text-center py-2">{error}</p>
    );
  }

  if (!data) {
    return (
      <p className="text-sm text-gray-400 text-center py-2">Chargement…</p>
    );
  }

  const qrSrc = `https://api.qrserver.com/v1/create-qr-code/?size=120x120&data=${encodeURIComponent(
    data.qr_payload,
  )}`;

  return (
    <div
      className="rounded-2xl p-5 text-white shadow-md"
      style={{ background: `linear-gradient(135deg, #0B7A6A 0%, ${data.primary_color} 100%)` }}
    >
      <div className="flex justify-between items-start gap-4">
        <div>
          <p className="text-xs uppercase tracking-widest opacity-80">
            Vintiz · Carte fidélité
          </p>
          <p className="font-display text-xl mt-1">{data.holder_name}</p>
          <p className="text-xs opacity-80 mt-1 font-mono">
            {data.membership_number}
          </p>
        </div>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={qrSrc}
          alt="QR membership"
          className="w-20 h-20 rounded-md bg-white p-1"
        />
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
        <div>
          <p className="text-xs uppercase opacity-80">Statut</p>
          <p className="font-semibold">
            {TIER_LABELS[data.tier] || data.tier}
          </p>
        </div>
        <div>
          <p className="text-xs uppercase opacity-80">Points</p>
          <p className="font-semibold">{data.points}</p>
        </div>
      </div>

      <p className="mt-4 text-xs opacity-90">{data.benefit_text}</p>

      <div className="mt-4 flex flex-wrap gap-2">
        {data.apple_signed_available && (
          <a
            href={`${API_URL}/api/crm/account/wallet/apple?email=${encodeURIComponent(email)}`}
            download
            className="text-[11px] bg-black/30 hover:bg-black/50 rounded-full px-3 py-1.5 font-medium transition-colors"
            title="Télécharger un .pkpass signé pour Apple Wallet"
          >
            Ajouter à Apple Wallet
          </a>
        )}
        {data.google_save_available && (
          <a
            href={`${API_URL}/api/crm/account/wallet/google?email=${encodeURIComponent(email)}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[11px] bg-black/30 hover:bg-black/50 rounded-full px-3 py-1.5 font-medium transition-colors"
            title="Ajouter à Google Wallet"
          >
            Ajouter à Google Wallet
          </a>
        )}
        <a
          href={`${API_URL}/api/crm/account/wallet/qr.png?email=${encodeURIComponent(email)}`}
          download={`vintiz-${data.membership_number}-qr.png`}
          className="text-[11px] bg-white/15 hover:bg-white/25 rounded-full px-3 py-1.5 font-medium transition-colors"
          title="Télécharger le QR code de votre carte"
        >
          Télécharger le QR
        </a>
      </div>
    </div>
  );
}
