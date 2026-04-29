'use client';

import React, { useEffect, useRef, useState } from 'react';
import { usePathname } from 'next/navigation';
import { api } from '@/lib/api';

type Msg = { role: 'user' | 'assistant'; content: string };

const STORAGE_KEY = 'vintiz.companion.chat';

export default function CompanionDrawer() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Msg[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) setMessages(JSON.parse(raw));
    } catch {}
  }, []);

  useEffect(() => {
    if (!mounted) return;
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(messages.slice(-30)));
    } catch {}
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, mounted]);

  // Hide on auth pages
  if (!mounted || pathname === '/login' || pathname === '/') return null;

  const send = async () => {
    const trimmed = input.trim();
    if (!trimmed || loading) return;
    const next: Msg[] = [...messages, { role: 'user' as const, content: trimmed }];
    setMessages(next);
    setInput('');
    setLoading(true);
    setError(null);
    try {
      const res = await api.post('/api/ai/chat', {
        messages: next,
        context: { page: pathname },
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Chat indisponible');
      }
      const data = await res.json();
      setMessages((prev) => [...prev, { role: 'assistant' as const, content: data.reply }]);
    } catch (e: any) {
      setError(e.message || 'Chat indisponible');
    } finally {
      setLoading(false);
    }
  };

  const handleKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  return (
    <>
      {/* Floating trigger */}
      {!open && (
        <button
          onClick={() => setOpen(true)}
          className="fixed bottom-5 right-5 z-40 h-14 w-14 rounded-full bg-vz-teal text-white shadow-vz-soft flex items-center justify-center hover:scale-105 active:scale-95 transition-transform ring-4 ring-white"
          aria-label="Ouvrir le compagnon IA"
        >
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            <circle cx="9" cy="10" r="1" fill="white" />
            <circle cx="15" cy="10" r="1" fill="white" />
          </svg>
        </button>
      )}

      {/* Drawer */}
      {open && (
        <>
          <div
            className="fixed inset-0 bg-black/25 z-40 animate-slide-up"
            onClick={() => setOpen(false)}
          />
          <aside className="fixed bottom-0 right-0 top-0 z-50 w-full sm:w-[420px] bg-white shadow-vz-soft flex flex-col animate-slide-in-right">
            {/* Header */}
            <header className="px-5 py-4 border-b border-gray-100 flex items-center justify-between bg-vz-teal text-white">
              <div className="flex items-center gap-3">
                <div className="h-9 w-9 rounded-xl bg-white/15 flex items-center justify-center">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 2a4 4 0 0 1 4 4v1h1a3 3 0 0 1 3 3v1a3 3 0 0 1-3 3h-1v4a2 2 0 0 1-2 2h-4a2 2 0 0 1-2-2v-4H7a3 3 0 0 1-3-3v-1a3 3 0 0 1 3-3h1V6a4 4 0 0 1 4-4z" />
                    <circle cx="9" cy="13" r="1" fill="white" />
                    <circle cx="15" cy="13" r="1" fill="white" />
                  </svg>
                </div>
                <div>
                  <p className="font-display font-semibold">Compagnon IA</p>
                  <p className="text-[11px] opacity-80">Demande-moi n&apos;importe quoi sur la boutique</p>
                </div>
              </div>
              <button
                onClick={() => setOpen(false)}
                className="h-9 w-9 rounded-lg hover:bg-white/15 flex items-center justify-center"
                aria-label="Fermer"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </header>

            {/* Messages */}
            <div ref={scrollRef} className="flex-1 overflow-y-auto px-5 py-4 space-y-4 bg-vz-bg">
              {messages.length === 0 && (
                <div className="rounded-2xl bg-white p-4 text-sm text-gray-600 shadow-vz-soft">
                  <p className="font-medium text-black mb-1">Coucou 👋</p>
                  Je peux t&apos;aider a repondre aux questions sur ta boutique : CA du jour,
                  produits a mettre en avant, idees de vitrine, analyse d&apos;une zone, etc.
                  <br /><br />
                  Essaie : <em>&quot;Quelles sont mes 5 pieces qui tournent le mieux en ce moment ?&quot;</em>
                </div>
              )}
              {messages.map((m, i) => (
                <div
                  key={i}
                  className={`rounded-2xl px-4 py-3 max-w-[85%] text-sm ${
                    m.role === 'user'
                      ? 'ml-auto bg-vz-teal text-white shadow-vz-soft'
                      : 'bg-white text-black shadow-vz-soft'
                  }`}
                >
                  {m.content.split('\n').map((line, j) => (
                    <p key={j} className={j > 0 ? 'mt-1' : ''}>{line}</p>
                  ))}
                </div>
              ))}
              {loading && (
                <div className="rounded-2xl bg-white px-4 py-3 shadow-vz-soft inline-flex items-center gap-2 text-sm text-gray-500">
                  <span className="h-2 w-2 bg-vz-teal rounded-full animate-pulse" />
                  <span className="h-2 w-2 bg-vz-teal rounded-full animate-pulse" style={{ animationDelay: '150ms' }} />
                  <span className="h-2 w-2 bg-vz-teal rounded-full animate-pulse" style={{ animationDelay: '300ms' }} />
                </div>
              )}
              {error && (
                <div className="rounded-2xl bg-vz-accent-soft text-vz-accent text-sm px-4 py-3 border border-vz-accent-soft">
                  {error}
                </div>
              )}
            </div>

            {/* Input */}
            <div className="border-t border-gray-100 p-4 bg-white">
              <div className="flex items-end gap-2">
                <textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKey}
                  placeholder="Ecris ton message…"
                  rows={1}
                  className="flex-1 resize-none rounded-xl border border-gray-200 px-3 py-2 text-sm focus:ring-2 focus:ring-vz-teal focus:border-vz-teal max-h-32"
                />
                <button
                  onClick={send}
                  disabled={loading || !input.trim()}
                  className="h-11 w-11 rounded-xl bg-vz-teal text-white flex items-center justify-center hover:bg-vz-teal-deep disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                  aria-label="Envoyer"
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="22" y1="2" x2="11" y2="13" />
                    <polygon points="22 2 15 22 11 13 2 9 22 2" />
                  </svg>
                </button>
              </div>
              {messages.length > 0 && (
                <button
                  onClick={() => { setMessages([]); localStorage.removeItem(STORAGE_KEY); }}
                  className="mt-2 text-[11px] text-gray-400 hover:text-gray-600"
                >
                  Effacer la conversation
                </button>
              )}
            </div>
          </aside>
        </>
      )}
    </>
  );
}
