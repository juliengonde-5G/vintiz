"use client";

import { useEffect, useMemo, useState } from "react";
import QRCode from "qrcode";
import { isAndroid, isIOS } from "@/lib/platform";

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

export default function WalletCard({
  email,
  showBigQr = false,
}: {
  email: string;
  showBigQr?: boolean;
}) {
  const [data, setData] = useState<WalletPayload | null>(null);
  const [error, setError] = useState("");
  const [qrDataUrl, setQrDataUrl] = useState("");

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

  // Pick the platform-native wallet as the primary CTA. Android Chrome
  // can't install a .pkpass file, iOS Safari can't really save to Google
  // Wallet ; surfacing the wrong one first leads to broken downloads.
  // Must be called before any early return — Rules of Hooks.
  const primaryWallet: 'apple' | 'google' | null = useMemo(() => {
    if (!data) return null;
    if (isIOS() && data.apple_signed_available) return 'apple';
    if (isAndroid() && data.google_save_available) return 'google';
    if (data.apple_signed_available) return 'apple';
    if (data.google_save_available) return 'google';
    return null;
  }, [data]);

  // QR généré localement (plus aucun appel à un service tiers type qrserver) :
  // le numéro de carte ne quitte plus le navigateur. Voir audit juridique §6.
  useEffect(() => {
    const payload = data?.qr_payload;
    if (!payload) return;
    let cancelled = false;
    QRCode.toDataURL(payload, {
      width: 512,
      margin: 4,
      errorCorrectionLevel: "M",
    })
      .then((url) => {
        if (!cancelled) setQrDataUrl(url);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [data?.qr_payload]);

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

  const PRIMARY_CLASS =
    'text-xs bg-white text-vz-teal-deep hover:bg-white/90 rounded-full px-3 py-1.5 font-semibold transition-colors';
  const SECONDARY_CLASS =
    'text-[11px] bg-black/30 hover:bg-black/50 rounded-full px-3 py-1.5 font-medium transition-colors';

  return (
    <>
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
        {qrDataUrl ? (
          /* eslint-disable-next-line @next/next/no-img-element */
          <img
            src={qrDataUrl}
            alt="QR membership"
            className="w-24 h-24 rounded-md bg-white p-1"
          />
        ) : (
          <div className="w-24 h-24 rounded-md bg-white/40 animate-pulse" />
        )}
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
        {/* Render the platform-native wallet first with the prominent
            "primary" style so the user installs the right one in 1 tap. */}
        {primaryWallet === 'google' && data.google_save_available && (
          <a
            href={`${API_URL}/api/crm/account/wallet/google?email=${encodeURIComponent(email)}`}
            target="_blank"
            rel="noopener noreferrer"
            className={PRIMARY_CLASS}
            title="Ajouter à Google Wallet"
          >
            Ajouter à Google Wallet
          </a>
        )}
        {primaryWallet === 'apple' && data.apple_signed_available && (
          <a
            href={`${API_URL}/api/crm/account/wallet/apple?email=${encodeURIComponent(email)}`}
            download
            className={PRIMARY_CLASS}
            title="Télécharger un .pkpass signé pour Apple Wallet"
          >
            Ajouter à Apple Wallet
          </a>
        )}
        {/* Secondary wallet (the other platform). Hidden when both are
            unavailable to avoid empty/duplicate buttons. */}
        {primaryWallet !== 'apple' && data.apple_signed_available && (
          <a
            href={`${API_URL}/api/crm/account/wallet/apple?email=${encodeURIComponent(email)}`}
            download
            className={SECONDARY_CLASS}
            title="Télécharger un .pkpass signé pour Apple Wallet"
          >
            Ajouter à Apple Wallet
          </a>
        )}
        {primaryWallet !== 'google' && data.google_save_available && (
          <a
            href={`${API_URL}/api/crm/account/wallet/google?email=${encodeURIComponent(email)}`}
            target="_blank"
            rel="noopener noreferrer"
            className={SECONDARY_CLASS}
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

    {showBigQr && (
      <div className="mt-6 bg-white rounded-2xl shadow-sm p-6 flex flex-col items-center">
        {qrDataUrl ? (
          /* eslint-disable-next-line @next/next/no-img-element */
          <img
            src={qrDataUrl}
            alt="QR code de votre carte de fidélité"
            className="w-64 h-64 sm:w-72 sm:h-72"
          />
        ) : (
          <div className="w-64 h-64 sm:w-72 sm:h-72 bg-vz-bg-alt animate-pulse rounded-md" />
        )}
        <p className="mt-3 font-mono text-sm text-vz-ink">
          {data.membership_number}
        </p>
        <p className="mt-1 text-xs text-vz-ink-mute text-center">
          Présentez ce code à la caisse pour cumuler vos points.
        </p>
      </div>
    )}
    </>
  );
}
