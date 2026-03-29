'use client';

import Sidebar from '@/components/layout/Sidebar';

export default function ReportsPage() {
  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar />
      <main className="flex-1 md:ml-64 p-6">
        <h1 className="text-2xl font-bold mb-6">Rapports</h1>
        <div className="bg-white rounded-xl shadow-sm p-8 text-center text-gray-400">
          <svg className="mx-auto mb-4" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <line x1="18" y1="20" x2="18" y2="10" />
            <line x1="12" y1="20" x2="12" y2="4" />
            <line x1="6" y1="20" x2="6" y2="14" />
          </svg>
          <p className="text-lg">Rapports - Phase 2</p>
          <p className="text-sm mt-2">Rapports quotidiens, hebdomadaires et mensuels.</p>
        </div>
      </main>
    </div>
  );
}
