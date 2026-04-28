/**
 * Vintiz loyalty wallet card (charte v2 — 2026-04).
 *
 * Standalone React component reproducing the visual identity of the
 * Apple Wallet / Google Wallet pass. Use as a preview in account
 * pages or marketing materials. Pure Tailwind, no Next.js
 * dependency — works in any React + Tailwind app that imports the
 * Vintiz preset.
 */

interface WalletCardProps {
  holderName: string;
  /** V###### unique card number. */
  membershipNumber: string;
  points: number;
  /** Optional QR payload (defaults to the same URL as the wallet pass). */
  qrPayload?: string;
}

export function WalletCard({
  holderName,
  membershipNumber,
  points,
  qrPayload,
}: WalletCardProps) {
  const url =
    qrPayload ?? `https://vintiz.fr/account/login?membership=${membershipNumber}`;

  return (
    <article
      className="relative overflow-hidden rounded-3xl shadow-xl w-full max-w-sm aspect-[1.586/1] p-6 text-white"
      style={{ backgroundColor: "#008678" }}
    >
      <header className="flex items-start justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] opacity-80">Vintiz</p>
          <p className="text-sm font-medium opacity-90 mt-0.5">Carte fidélité</p>
        </div>
        <span className="text-2xl font-display font-bold tracking-wider">
          VL
        </span>
      </header>

      <div className="absolute inset-x-6 bottom-6">
        <p className="text-xs uppercase tracking-[0.2em] opacity-80">Titulaire</p>
        <p className="text-base font-medium truncate">{holderName}</p>

        <div className="mt-3 flex items-end justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] opacity-80">N° carte</p>
            <p className="font-mono text-lg tracking-wide">{membershipNumber}</p>
          </div>
          <div className="text-right">
            <p className="text-xs uppercase tracking-[0.2em] opacity-80">Points</p>
            <p className="text-3xl font-display font-bold">{points}</p>
          </div>
        </div>
      </div>

      {/* QR payload — caller responsible for rendering the actual QR; we
          surface the encoded URL so a wrapper can drop a <QRCode>. */}
      <span className="sr-only">QR payload: {url}</span>
    </article>
  );
}
