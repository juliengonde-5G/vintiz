'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

/**
 * Fusion : le backlog des transactions + le suivi de caisse vivent désormais
 * sur la page unifiée « Transactions & Caisse ». On y redirige.
 */
export default function AdminRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace('/admin/transactions');
  }, [router]);
  return (
    <div className="min-h-screen flex items-center justify-center text-sm text-vz-ink-mute">
      Redirection vers Transactions &amp; Caisse…
    </div>
  );
}
