'use client';

/**
 * État affiché à la place d'un écran de gestion des zones quand la
 * fonctionnalité « zonage » est désactivée (boutique sans zones).
 */

import React from 'react';
import Link from 'next/link';
import Sidebar from '@/components/layout/Sidebar';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';

export default function ZoningDisabled({ title = 'Gestion des zones' }: { title?: string }) {
  return (
    <div className="min-h-screen bg-vz-bg">
      <Sidebar />
      <main className="md:ml-64 px-4 pt-16 pb-10 md:p-8">
        <div className="max-w-2xl mx-auto">
          <Card title={title}>
            <div className="py-6 text-center">
              <div className="text-4xl mb-3" aria-hidden>🗺️</div>
              <p className="text-sm text-vz-ink font-medium">Gestion des zones désactivée</p>
              <p className="text-sm text-vz-ink-mute mt-1 max-w-prose mx-auto">
                Cette boutique fonctionne sans zonage. Le placement par zone, le plan 2D,
                l&apos;optimisation IA et les KPI par zone sont masqués.
              </p>
              <div className="mt-4">
                <Link href="/setup"><Button variant="outline">Réactiver dans l&apos;installation</Button></Link>
              </div>
            </div>
          </Card>
        </div>
      </main>
    </div>
  );
}
