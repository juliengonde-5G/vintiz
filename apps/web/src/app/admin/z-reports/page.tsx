'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

/**
 * Fusion : les rapports Z (suivi de caisse) sont désormais dans l'onglet
 * « Caisse » de la page unifiée « Transactions & Caisse ». On y redirige.
 */
export default function ZReportsRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace('/admin/transactions?view=caisse');
  }, [router]);
  return (
    <div className="min-h-screen flex items-center justify-center text-sm text-vz-ink-mute">
      Redirection vers Transactions &amp; Caisse…
    </div>
  );
}
