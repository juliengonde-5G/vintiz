'use client';

import React, { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import Button from '@/components/ui/Button';
import { api } from '@/lib/api';

type Priority = {
  title: string;
  body: string;
  action_url: string;
  type: string;
  priority: number;
};

type Briefing = {
  greeting: string;
  date: string;
  today: { revenue: number; transactions: number };
  yesterday: { revenue: number; transactions: number };
  stock: { active: number; stale_45d: number };
  zone_alerts: { zone_id: string; zone_name: string; occupancy_pct: number; status: string }[];
  priorities: Priority[];
};

type Task = {
  id: string;
  type: string;
  title: string;
  body: string | null;
  priority: number;
  status: string;
  action_url: string | null;
  due_date: string | null;
  created_at: string;
};

function formatCurrency(v: number) {
  return v.toFixed(0).replace(/\B(?=(\d{3})+(?!\d))/g, ' ') + ' €';
}

function priorityBadge(p: number) {
  if (p >= 4) return { bg: 'bg-pink-500 text-white', label: 'URGENT' };
  if (p >= 3) return { bg: 'bg-teal text-white', label: 'PRIORITAIRE' };
  return { bg: 'bg-gray-200 text-gray-700', label: 'IDEE' };
}

export default function CompanionHero() {
  const [briefing, setBriefing] = useState<Briefing | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [bRes, tRes] = await Promise.all([
        api.get('/api/ai/briefing'),
        api.get('/api/ai/tasks?status=open'),
      ]);
      if (bRes.ok) setBriefing(await bRes.json());
      if (tRes.ok) setTasks(await tRes.json());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const runAction = async (taskId: string, action: 'accept' | 'snooze' | 'dismiss', days = 1) => {
    setBusy(taskId);
    try {
      const url = `/api/ai/tasks/${taskId}/${action}`;
      const res = action === 'snooze'
        ? await api.post(url, { days })
        : await api.post(url, {});
      if (res.ok) setTasks((prev) => prev.filter((t) => t.id !== taskId));
    } finally {
      setBusy(null);
    }
  };

  const deltaRevenue = briefing
    ? briefing.yesterday.revenue > 0
      ? ((briefing.today.revenue - briefing.yesterday.revenue) / briefing.yesterday.revenue) * 100
      : null
    : null;

  return (
    <div className="mb-8 space-y-6">
      {/* Hero card */}
      <div className="relative rounded-3xl bg-gradient-teal text-white p-6 md:p-8 shadow-depth overflow-hidden">
        <div className="absolute -right-10 -top-10 h-48 w-48 rounded-full bg-white/10 blur-2xl" />
        <div className="absolute right-20 bottom-0 h-32 w-32 rounded-full bg-pink/30 blur-3xl" />
        <div className="relative z-10 flex items-start justify-between gap-6 flex-wrap">
          <div className="flex items-start gap-4 min-w-0 flex-1">
            {/* AI avatar */}
            <div className="flex-shrink-0 h-14 w-14 rounded-2xl bg-white/15 backdrop-blur-sm flex items-center justify-center shadow-lg ring-2 ring-white/20">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 2a4 4 0 0 1 4 4v1h1a3 3 0 0 1 3 3v1a3 3 0 0 1-3 3h-1v4a2 2 0 0 1-2 2h-4a2 2 0 0 1-2-2v-4H7a3 3 0 0 1-3-3v-1a3 3 0 0 1 3-3h1V6a4 4 0 0 1 4-4z" />
                <circle cx="9" cy="13" r="1" fill="white" />
                <circle cx="15" cy="13" r="1" fill="white" />
              </svg>
            </div>
            <div className="min-w-0">
              <p className="text-[11px] tracking-[0.22em] uppercase font-medium opacity-80">
                Compagnon IA · {briefing?.date || '—'}
              </p>
              <h1 className="font-display font-semibold text-2xl md:text-3xl leading-tight mt-1">
                {loading ? 'Chargement…' : briefing?.greeting || 'Bienvenue.'}
              </h1>
            </div>
          </div>
          {/* KPIs */}
          {briefing && (
            <div className="grid grid-cols-3 gap-3 text-center">
              <div className="rounded-2xl bg-white/15 backdrop-blur-sm px-3 py-2 min-w-[96px]">
                <p className="text-[10px] uppercase tracking-wider opacity-80">Aujourd&apos;hui</p>
                <p className="font-display font-semibold text-xl mt-0.5">
                  {formatCurrency(briefing.today.revenue)}
                </p>
                {deltaRevenue !== null && (
                  <p className="text-[11px] opacity-90 mt-0.5">
                    {deltaRevenue >= 0 ? '▲' : '▼'} {Math.abs(deltaRevenue).toFixed(0)}%
                  </p>
                )}
              </div>
              <div className="rounded-2xl bg-white/15 backdrop-blur-sm px-3 py-2 min-w-[96px]">
                <p className="text-[10px] uppercase tracking-wider opacity-80">Tickets</p>
                <p className="font-display font-semibold text-xl mt-0.5">{briefing.today.transactions}</p>
                <p className="text-[11px] opacity-90 mt-0.5">hier {briefing.yesterday.transactions}</p>
              </div>
              <div className="rounded-2xl bg-white/15 backdrop-blur-sm px-3 py-2 min-w-[96px]">
                <p className="text-[10px] uppercase tracking-wider opacity-80">Stock</p>
                <p className="font-display font-semibold text-xl mt-0.5">{briefing.stock.active}</p>
                {briefing.stock.stale_45d > 0 && (
                  <p className="text-[11px] opacity-90 mt-0.5">{briefing.stock.stale_45d} anciens</p>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Priorities */}
      {briefing && briefing.priorities.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <div>
              <p className="text-[11px] tracking-[0.22em] uppercase text-teal font-medium">
                Briefing du jour
              </p>
              <h2 className="font-display font-semibold text-lg text-black mt-0.5">
                Tes 3 priorites
              </h2>
            </div>
            <button onClick={load} className="text-xs text-teal hover:text-teal-700">
              Rafraichir
            </button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {briefing.priorities.map((p, i) => {
              const badge = priorityBadge(p.priority);
              return (
                <Link
                  key={i}
                  href={p.action_url}
                  className="group rounded-2xl bg-white p-5 shadow-card hover:shadow-soft transition-all animate-slide-up block"
                  style={{ animationDelay: `${i * 60}ms` }}
                >
                  <span className={`inline-block text-[10px] font-semibold tracking-wider px-2 py-0.5 rounded-full ${badge.bg} mb-3`}>
                    {badge.label}
                  </span>
                  <h3 className="font-display font-semibold text-black leading-snug">{p.title}</h3>
                  <p className="text-sm text-gray-600 mt-1">{p.body}</p>
                  <span className="inline-flex items-center gap-1 mt-3 text-sm text-teal font-medium group-hover:gap-2 transition-all">
                    Agir
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <polyline points="9 6 15 12 9 18" />
                    </svg>
                  </span>
                </Link>
              );
            })}
          </div>
        </div>
      )}

      {/* AI Tasks feed */}
      {tasks.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <div>
              <p className="text-[11px] tracking-[0.22em] uppercase text-teal font-medium">
                Cartes-taches IA
              </p>
              <h2 className="font-display font-semibold text-lg text-black mt-0.5">
                {tasks.length} suggestion{tasks.length > 1 ? 's' : ''} en attente
              </h2>
            </div>
          </div>
          <div className="space-y-3">
            {tasks.map((t) => {
              const badge = priorityBadge(t.priority);
              return (
                <div key={t.id} className="rounded-2xl bg-white p-4 shadow-card animate-slide-up flex items-start gap-3">
                  <span className={`flex-shrink-0 text-[10px] font-semibold tracking-wider px-2 py-0.5 rounded-full ${badge.bg} mt-0.5`}>
                    {badge.label}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-black">{t.title}</p>
                    {t.body && <p className="text-sm text-gray-600 mt-0.5">{t.body}</p>}
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    {t.action_url && (
                      <Link href={t.action_url}>
                        <Button size="sm" variant="outline">Ouvrir</Button>
                      </Link>
                    )}
                    <Button
                      size="sm"
                      onClick={() => runAction(t.id, 'accept')}
                      disabled={busy === t.id}
                    >
                      Accepter
                    </Button>
                    <button
                      onClick={() => runAction(t.id, 'snooze', 1)}
                      disabled={busy === t.id}
                      className="text-xs text-gray-500 hover:text-gray-700 px-2"
                    >
                      Reporter
                    </button>
                    <button
                      onClick={() => runAction(t.id, 'dismiss')}
                      disabled={busy === t.id}
                      className="text-xs text-gray-400 hover:text-pink-700 px-2"
                      aria-label="Refuser"
                    >
                      ✕
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
