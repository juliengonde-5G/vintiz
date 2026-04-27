'use client';

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import Sidebar from '@/components/layout/Sidebar';
import Button from '@/components/ui/Button';
import Card from '@/components/ui/Card';
import SectionHeader from '@/components/ui/SectionHeader';
import EmptyState from '@/components/ui/EmptyState';
import IsoCanvas from '@/components/zones/IsoCanvas';
import { ZONE_TAG_OPTIONS } from '@/components/zones/FurnitureSVG';
import { api } from '@/lib/api';

type Zone = {
  id: string;
  name: string;
  description: string | null;
  capacity: number;
  product_types: string[] | null;
  color_code: string | null;
  pos_x: number;
  pos_y: number;
  width: number;
  height: number;
  shape: 'rect' | 'rounded' | 'circle' | string;
  icon: string | null;
  photo_url: string | null;
  sales_target_monthly: number | null;
  display_order: number;
  product_count?: number;
};

type DragState =
  | { mode: 'move'; zoneId: string; startX: number; startY: number; origX: number; origY: number }
  | { mode: 'resize'; zoneId: string; startX: number; startY: number; origW: number; origH: number }
  | null;

function occupancyInfo(count: number, capacity: number) {
  if (!capacity) return { pct: 0, tone: 'bg-gray-200', text: 'text-gray-600' };
  const pct = Math.min(100, Math.round((count / capacity) * 100));
  if (pct >= 95) return { pct, tone: 'bg-pink-500', text: 'text-pink-700' };
  if (pct >= 70) return { pct, tone: 'bg-teal-400', text: 'text-teal' };
  if (pct >= 40) return { pct, tone: 'bg-teal-300', text: 'text-teal' };
  return { pct, tone: 'bg-yellow-300', text: 'text-yellow-700' };
}

function ZoneIcon({ name, className }: { name: string | null; className?: string }) {
  const size = 18;
  const props = {
    width: size,
    height: size,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 2,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
    className,
  };
  switch (name) {
    case 'sparkles':
      return (
        <svg {...props}>
          <path d="M12 3l2 5 5 2-5 2-2 5-2-5-5-2 5-2z" />
        </svg>
      );
    case 'star':
      return (
        <svg {...props}>
          <polygon points="12 2 15 9 22 9.5 17 14.5 18.5 22 12 18 5.5 22 7 14.5 2 9.5 9 9" />
        </svg>
      );
    case 'shirt':
      return (
        <svg {...props}>
          <path d="M4 6l4-3h8l4 3-3 3v12H7V9L4 6z" />
        </svg>
      );
    case 'cash':
      return (
        <svg {...props}>
          <rect x="2" y="6" width="20" height="12" rx="2" />
          <circle cx="12" cy="12" r="3" />
        </svg>
      );
    case 'grid':
      return (
        <svg {...props}>
          <rect x="3" y="3" width="7" height="7" rx="1" />
          <rect x="14" y="3" width="7" height="7" rx="1" />
          <rect x="3" y="14" width="7" height="7" rx="1" />
          <rect x="14" y="14" width="7" height="7" rx="1" />
        </svg>
      );
    case 'bag':
      return (
        <svg {...props}>
          <path d="M4 7h16l-1 13H5L4 7z" />
          <path d="M9 7V5a3 3 0 1 1 6 0v2" />
        </svg>
      );
    case 'door':
      return (
        <svg {...props}>
          <path d="M5 21V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16" />
          <circle cx="15" cy="13" r="0.8" fill="currentColor" />
        </svg>
      );
    default:
      return (
        <svg {...props}>
          <rect x="4" y="4" width="16" height="16" rx="3" />
        </svg>
      );
  }
}

export default function ZonesPage() {
  const [zones, setZones] = useState<Zone[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editMode, setEditMode] = useState(false);
  const [saving, setSaving] = useState(false);
  const [drag, setDrag] = useState<DragState>(null);
  const [hoverId, setHoverId] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'flat' | 'iso'>('flat');
  const [filterTag, setFilterTag] = useState<string | null>(null);
  const canvasRef = useRef<HTMLDivElement | null>(null);

  const loadZones = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get('/api/admin/zones');
      if (!res.ok) throw new Error('load failed');
      const data = await res.json();
      setZones(data);
      setError(null);
    } catch (e) {
      setError("Impossible de charger les zones");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadZones();
  }, [loadZones]);

  const totalCapacity = useMemo(
    () => zones.reduce((acc, z) => acc + (z.capacity || 0), 0),
    [zones]
  );
  const totalProducts = useMemo(
    () => zones.reduce((acc, z) => acc + (z.product_count || 0), 0),
    [zones]
  );

  const percentFromEvent = (e: React.PointerEvent | PointerEvent) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return { x: 0, y: 0 };
    return {
      x: ((e.clientX - rect.left) / rect.width) * 100,
      y: ((e.clientY - rect.top) / rect.height) * 100,
    };
  };

  const onMoveStart = (e: React.PointerEvent, zone: Zone) => {
    if (!editMode) return;
    e.preventDefault();
    (e.target as Element).setPointerCapture?.(e.pointerId);
    const p = percentFromEvent(e);
    setDrag({
      mode: 'move',
      zoneId: zone.id,
      startX: p.x,
      startY: p.y,
      origX: zone.pos_x,
      origY: zone.pos_y,
    });
  };

  const onResizeStart = (e: React.PointerEvent, zone: Zone) => {
    if (!editMode) return;
    e.preventDefault();
    e.stopPropagation();
    (e.target as Element).setPointerCapture?.(e.pointerId);
    const p = percentFromEvent(e);
    setDrag({
      mode: 'resize',
      zoneId: zone.id,
      startX: p.x,
      startY: p.y,
      origW: zone.width,
      origH: zone.height,
    });
  };

  const onPointerMove = (e: React.PointerEvent) => {
    if (!drag) return;
    const p = percentFromEvent(e);
    const dx = p.x - drag.startX;
    const dy = p.y - drag.startY;
    setZones((prev) =>
      prev.map((z) => {
        if (z.id !== drag.zoneId) return z;
        if (drag.mode === 'move') {
          const nx = Math.max(0, Math.min(100 - z.width, drag.origX + dx));
          const ny = Math.max(0, Math.min(100 - z.height, drag.origY + dy));
          return { ...z, pos_x: Math.round(nx), pos_y: Math.round(ny) };
        }
        const nw = Math.max(6, Math.min(100 - z.pos_x, drag.origW + dx));
        const nh = Math.max(6, Math.min(100 - z.pos_y, drag.origH + dy));
        return { ...z, width: Math.round(nw), height: Math.round(nh) };
      })
    );
  };

  const onPointerEnd = () => {
    setDrag(null);
  };

  const saveLayout = async () => {
    setSaving(true);
    try {
      const items = zones.map((z) => ({
        id: z.id,
        pos_x: z.pos_x,
        pos_y: z.pos_y,
        width: z.width,
        height: z.height,
      }));
      const res = await api.post('/api/admin/zones/layout', { items });
      if (!res.ok) throw new Error('save failed');
      setEditMode(false);
    } catch {
      setError("La sauvegarde du plan a echoue");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="min-h-screen bg-cream">
      <Sidebar />
      <main className="md:ml-64 p-4 md:p-8 max-w-7xl">
        <div className="mb-6 flex items-start justify-between gap-4 flex-wrap">
          <div>
            <p className="text-[11px] tracking-[0.22em] uppercase text-teal font-medium">
              Espaces de vente
            </p>
            <h1 className="text-3xl font-display font-semibold text-black mt-1">
              Plan de la boutique
            </h1>
            <p className="text-sm text-gray-600 mt-1">
              {zones.length} zones · {totalProducts} articles en rayon · capacite cumulee {totalCapacity}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {editMode ? (
              <>
                <Button variant="outline" size="sm" onClick={() => { setEditMode(false); loadZones(); }}>
                  Annuler
                </Button>
                <Button size="sm" onClick={saveLayout} disabled={saving}>
                  {saving ? 'Sauvegarde…' : 'Enregistrer le plan'}
                </Button>
              </>
            ) : (
              <Button variant="outline" size="sm" onClick={() => setEditMode(true)}>
                Editer le plan
              </Button>
            )}
          </div>
        </div>

        {error && (
          <div className="mb-4 rounded-xl border border-pink-300 bg-pink-50 text-pink-700 px-4 py-3 text-sm">
            {error}
          </div>
        )}

        {/* Canvas */}
        <Card variant="elevated" className="mb-6">
          <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
            <div>
              <h2 className="font-display font-semibold text-lg text-black">
                {editMode ? 'Mode edition — glisse, redimensionne, enregistre' : 'Vue terrain'}
              </h2>
              <p className="text-xs text-gray-500">
                {viewMode === 'iso'
                  ? 'Vue isométrique 2.5D — mobilier paramétrable + tags zones'
                  : (editMode
                    ? 'Deplace une zone en la tirant. Redimensionne avec la poignee en bas a droite.'
                    : 'Survole une zone pour en voir le detail, clique pour ouvrir son tableau de bord.')}
              </p>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              {/* L2.2 — Toggle Vue plate / Vue iso 2.5D */}
              <div className="flex bg-gray-100 rounded-lg p-0.5">
                <button
                  onClick={() => setViewMode('flat')}
                  className={`text-xs px-3 py-1 rounded-md min-h-0 min-w-0 ${
                    viewMode === 'flat' ? 'bg-white shadow-sm font-medium' : 'text-gray-500'
                  }`}
                >
                  Vue plate
                </button>
                <button
                  onClick={() => setViewMode('iso')}
                  className={`text-xs px-3 py-1 rounded-md min-h-0 min-w-0 ${
                    viewMode === 'iso' ? 'bg-white shadow-sm font-medium' : 'text-gray-500'
                  }`}
                >
                  Vue 2.5D
                </button>
              </div>
              {/* L2.2 — Filtre par tag (visible dans les 2 modes) */}
              <select
                value={filterTag || ''}
                onChange={(e) => setFilterTag(e.target.value || null)}
                className="text-xs px-2 py-1 border border-gray-200 rounded-lg bg-white min-h-0"
              >
                <option value="">Tous les tags</option>
                {ZONE_TAG_OPTIONS.map((opt) => (
                  <option key={opt.tag} value={opt.tag}>{opt.label}</option>
                ))}
              </select>
              {editMode && (
                <span className="text-xs px-3 py-1 rounded-full bg-teal-50 text-teal font-medium">
                  Edition active
                </span>
              )}
            </div>
          </div>

          {viewMode === 'iso' && (
            <IsoCanvas zones={zones as any} editMode={editMode} filterTag={filterTag} />
          )}

          {viewMode === 'flat' && (
          <>
          <div
            ref={canvasRef}
            onPointerMove={onPointerMove}
            onPointerUp={onPointerEnd}
            onPointerLeave={onPointerEnd}
            className={`relative w-full rounded-2xl overflow-hidden select-none ${
              editMode ? 'bg-[radial-gradient(#00867820_1px,transparent_1px)] bg-[length:18px_18px] ring-1 ring-teal-100' : 'bg-gradient-warm ring-1 ring-teal-50'
            }`}
            style={{ aspectRatio: '16 / 10' }}
          >
            {/* Entrance indicator (bottom center) */}
            <div className="absolute left-1/2 -translate-x-1/2 bottom-1 flex items-center gap-1 text-[10px] text-gray-500 tracking-widest uppercase">
              <span className="h-px w-5 bg-gray-400" />
              Entree
              <span className="h-px w-5 bg-gray-400" />
            </div>

            {loading ? (
              <div className="absolute inset-0 flex items-center justify-center text-sm text-gray-500">
                Chargement du plan…
              </div>
            ) : (
              zones.map((z) => {
                const occ = occupancyInfo(z.product_count || 0, z.capacity);
                const isDragging = drag?.zoneId === z.id;
                const isHovered = hoverId === z.id;
                const radius = z.shape === 'circle' ? '50%' : z.shape === 'rounded' ? '18px' : '6px';
                const bg = z.color_code || '#008678';
                return (
                  <div
                    key={z.id}
                    onPointerDown={(e) => onMoveStart(e, z)}
                    onPointerEnter={() => setHoverId(z.id)}
                    onPointerLeave={() => setHoverId((id) => (id === z.id ? null : id))}
                    onClick={() => {
                      if (!editMode && !isDragging) window.location.href = `/zones/${z.id}`;
                    }}
                    className={`absolute group transition-shadow ${
                      editMode ? 'cursor-move' : 'cursor-pointer'
                    } ${isDragging ? 'shadow-depth z-30' : isHovered ? 'shadow-depth z-20' : 'shadow-soft z-10'}`}
                    style={{
                      left: `${z.pos_x}%`,
                      top: `${z.pos_y}%`,
                      width: `${z.width}%`,
                      height: `${z.height}%`,
                      background: `linear-gradient(135deg, ${bg}, ${bg}CC)`,
                      borderRadius: radius,
                      border: isHovered || editMode ? '2px solid rgba(255,255,255,0.9)' : '2px solid rgba(255,255,255,0.4)',
                    }}
                    title={z.name}
                  >
                    <div className="absolute inset-0 p-2 flex flex-col justify-between text-white">
                      <div className="flex items-start justify-between gap-1">
                        <div className="flex items-center gap-1 rounded-full bg-black/15 px-2 py-0.5 backdrop-blur-sm">
                          <ZoneIcon name={z.icon} className="text-white/90" />
                          <span className="text-[11px] font-semibold font-display truncate max-w-[120px]">
                            {z.name}
                          </span>
                        </div>
                        <span className="text-[10px] font-medium rounded-full bg-black/15 px-1.5 py-0.5">
                          {occ.pct}%
                        </span>
                      </div>
                      <div className="flex items-end justify-between">
                        <span className="text-[10px] font-medium opacity-90">
                          {z.product_count ?? 0}/{z.capacity || '∞'}
                        </span>
                        <span className="text-[10px] opacity-90">{z.width}×{z.height}</span>
                      </div>
                    </div>
                    {editMode && (
                      <div
                        onPointerDown={(e) => onResizeStart(e, z)}
                        className="absolute bottom-0 right-0 h-4 w-4 bg-white rounded-tl-md rounded-br-md cursor-nwse-resize shadow-md flex items-center justify-center"
                        aria-label="Redimensionner"
                      >
                        <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="#008678" strokeWidth="1.5" strokeLinecap="round">
                          <line x1="2" y1="8" x2="8" y2="2" />
                          <line x1="5" y1="8" x2="8" y2="5" />
                        </svg>
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
          <div className="mt-3 flex items-center gap-3 text-xs text-gray-500 flex-wrap">
            <span className="inline-flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-teal" /> Normal
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-yellow-300" /> Sous-remplie
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-pink-500" /> Saturee
            </span>
          </div>
          </>
          )}
        </Card>

        {/* Cards */}
        <SectionHeader
          title="Vue detaillee par zone"
          subtitle="Chaque zone a son propre tableau de bord — clique pour plonger."
        />
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="h-48 rounded-2xl bg-white animate-pulse" />
            ))}
          </div>
        ) : zones.length === 0 ? (
          <EmptyState
            title="Aucune zone"
            description="Lance le seed pour initialiser les 11 espaces de la boutique."
          />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {zones.map((z) => {
              const occ = occupancyInfo(z.product_count || 0, z.capacity);
              return (
                <Link key={z.id} href={`/zones/${z.id}`} className="group">
                  <div className="rounded-2xl bg-white p-5 shadow-card hover:shadow-soft transition-all group-active:scale-[0.99] animate-slide-up">
                    <div className="flex items-center gap-3 mb-4">
                      <div
                        className="h-11 w-11 rounded-xl flex items-center justify-center text-white shadow-sm"
                        style={{ background: `linear-gradient(135deg, ${z.color_code || '#008678'}, ${z.color_code || '#008678'}CC)` }}
                      >
                        <ZoneIcon name={z.icon} />
                      </div>
                      <div className="min-w-0 flex-1">
                        <h3 className="font-display font-semibold text-black truncate">{z.name}</h3>
                        <p className="text-xs text-gray-500 truncate">{z.description || '—'}</p>
                      </div>
                      <span className={`text-xs font-semibold ${occ.text}`}>{occ.pct}%</span>
                    </div>
                    <div className="h-2 bg-gray-100 rounded-full overflow-hidden mb-3">
                      <div
                        className={`h-full ${occ.tone} transition-all`}
                        style={{ width: `${occ.pct}%` }}
                      />
                    </div>
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-gray-500">
                        {z.product_count ?? 0} / {z.capacity || '∞'} articles
                      </span>
                      {z.product_types && z.product_types.length > 0 && (
                        <span className="text-gray-700 truncate">
                          {z.product_types.slice(0, 2).join(' · ')}
                        </span>
                      )}
                    </div>
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
