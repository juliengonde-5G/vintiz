const MATOMO_URL = process.env.NEXT_PUBLIC_MATOMO_URL || "";

/**
 * Iframe d'opposition (opt-out) fournie par Matomo. Même si la mesure
 * cookieless est exemptée de consentement, la CNIL recommande d'offrir un
 * moyen simple de s'y opposer. L'iframe pose/retire un cookie d'opt-out géré
 * par Matomo lui-même. Masqué tant que l'instance Matomo n'est pas configurée.
 */
export default function MatomoOptOut() {
  if (!MATOMO_URL) return null;
  const base = MATOMO_URL.endsWith("/") ? MATOMO_URL : `${MATOMO_URL}/`;
  const src = `${base}index.php?module=CoreAdminHome&action=optOut&language=fr`;
  return (
    <div className="mt-4 rounded-lg border border-vz-line/60 bg-white p-4">
      <iframe
        title="Opposition à la mesure d'audience Matomo"
        src={src}
        style={{ border: 0, width: "100%", height: 150 }}
        loading="lazy"
      />
    </div>
  );
}
