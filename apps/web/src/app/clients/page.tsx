'use client';

import Sidebar from '@/components/layout/Sidebar';

export default function ClientsPage() {
  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar />
      <main className="flex-1 md:ml-64 p-6">
        <h1 className="text-2xl font-bold mb-6">Clients</h1>
        <div className="bg-white rounded-xl shadow-sm p-8 text-center text-gray-400">
          <svg className="mx-auto mb-4" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
            <circle cx="9" cy="7" r="4" />
            <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
            <path d="M16 3.13a4 4 0 0 1 0 7.75" />
          </svg>
          <p className="text-lg">Module CRM - Phase 2</p>
          <p className="text-sm mt-2">Gestion clients, fidelite et historique achats.</p>
        </div>
      </main>
    </div>
  );
}
