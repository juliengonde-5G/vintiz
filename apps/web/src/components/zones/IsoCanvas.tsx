'use client';

import React, { useEffect, useRef, useState } from 'react';
import FurnitureSVG, { FURNITURE_TYPES, ZONE_TAG_OPTIONS } from './FurnitureSVG';
import { api } from '@/lib/api';

type Zone = {
  id: string;
  name: string;
  pos_x: number;
  pos_y: number;
  width: number;
  height: number;
  shape?: string;
  color_code?: string | null;
  product_count?: number;
  capacity?: number;
  tags?: string[];
};

type FurnitureItem = {
  id: string;
  zone_id: string | null;
  type: string;
  variant: string | null;
  pos_x: number;
  pos_y: number;
  rotation: number;
  scale: number;
  label: string | null;
};

type Props = {
  zones: Zone[];
  editMode: boolean;
  filterTag?: string | null;
};

/**
 * Iso 2.5D canvas (CSS skew + rotate). Renders :
 * - The base canvas with zones (% coords, like the legacy view)
 * - An isometric overlay : skew(-30deg) + rotate(30deg)
 * - Furniture items positioned in % coords with same iso transform
 *
 * Drag/drop of furniture is handled in % coords for consistency with
 * the existing zone canvas model.
 */
export default function IsoCanvas({ zones, editMode, filterTag }: Props) {
  const [furniture, setFurniture] = useState<FurnitureItem[]>([]);
  const [selectedFurnId, setSelectedFurnId] = useState<string | null>(null);
  const [showPalette, setShowPalette] = useState(false);
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const canvasRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const r = await api.get('/api/admin/furniture');
        if (r.ok) setFurniture(await r.json());
      } catch { /* silent */ }
    })();
  }, []);

  const addFurniture = async (type: string, variant?: string) => {
    try {
      const r = await api.post('/api/admin/furniture', {
        type, variant, pos_x: 50, pos_y: 50, rotation: 0, scale: 1.0,
      });
      if (r.ok) {
        const { id } = await r.json();
        setFurniture((prev) => [...prev, {
          id, zone_id: null, type, variant: variant || null,
          pos_x: 50, pos_y: 50, rotation: 0, scale: 1.0, label: null,
        }]);
      }
    } catch { /* silent */ }
  };

  const moveFurniture = (id: string, dx: number, dy: number) => {
    setFurniture((prev) => prev.map((f) =>
      f.id === id
        ? { ...f, pos_x: Math.max(0, Math.min(100, f.pos_x + dx)), pos_y: Math.max(0, Math.min(100, f.pos_y + dy)) }
        : f
    ));
  };

  const persistFurniture = async (id: string) => {
    const f = furniture.find((x) => x.id === id);
    if (!f) return;
    try {
      await api.put(`/api/admin/furniture/${id}`, {
        zone_id: f.zone_id, type: f.type, variant: f.variant,
        pos_x: f.pos_x, pos_y: f.pos_y,
        rotation: f.rotation, scale: f.scale, label: f.label,
      });
    } catch { /* silent */ }
  };

  const deleteFurniture = async (id: string) => {
    try {
      await api.delete(`/api/admin/furniture/${id}`);
      setFurniture((prev) => prev.filter((f) => f.id !== id));
      if (selectedFurnId === id) setSelectedFurnId(null);
    } catch { /* silent */ }
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!draggingId || !canvasRef.current) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const dx = (e.movementX / rect.width) * 100;
    const dy = (e.movementY / rect.height) * 100;
    moveFurniture(draggingId, dx, dy);
  };

  // Filter zones by tag if active
  const visibleZoneIds = filterTag
    ? new Set(zones.filter((z) => z.tags?.includes(filterTag)).map((z) => z.id))
    : new Set(zones.map((z) => z.id));

  return (
    <div className="space-y-3">
      {/* Toolbar */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex gap-2 flex-wrap">
          {ZONE_TAG_OPTIONS.slice(0, 6).map((opt) => (
            <span
              key={opt.tag}
              className="text-[10px] px-2 py-0.5 rounded-full border"
              style={{ borderColor: opt.color, color: opt.color }}
            >
              {opt.label}
            </span>
          ))}
        </div>
        {editMode && (
          <button
            onClick={() => setShowPalette((s) => !s)}
            className="text-sm px-3 py-1.5 bg-vz-teal text-white rounded-lg min-h-0 min-w-0"
          >
            {showPalette ? 'Fermer la palette' : '+ Ajouter du mobilier'}
          </button>
        )}
      </div>

      {/* Furniture palette */}
      {showPalette && (
        <div className="bg-white border border-gray-200 rounded-lg p-3">
          <div className="text-xs text-gray-500 mb-2">Cliquez pour ajouter au canvas</div>
          <div className="grid grid-cols-5 md:grid-cols-10 gap-2">
            {FURNITURE_TYPES.map((ft) => (
              <button
                key={ft.type}
                onClick={() => addFurniture(ft.type, ft.variants?.[0])}
                title={ft.label}
                className="bg-gray-50 hover:bg-vz-teal-soft rounded-lg p-2 text-center min-h-0 min-w-0 border border-gray-100"
              >
                <FurnitureSVG type={ft.type} variant={ft.variants?.[0]} size={40} />
                <div className="text-[9px] text-gray-600 mt-1 truncate">{ft.label}</div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Iso canvas */}
      <div className="relative bg-gradient-to-br from-vz-bg to-yellow-50 rounded-2xl overflow-hidden p-6 shadow-vz-soft">
        <div
          ref={canvasRef}
          className="relative aspect-[16/10] mx-auto"
          style={{ maxWidth: '900px' }}
          onMouseMove={handleMouseMove}
          onMouseUp={() => {
            if (draggingId) {
              persistFurniture(draggingId);
              setDraggingId(null);
            }
          }}
        >
          {/* Iso transform wrapper — skew + rotate gives the cavalier 30° view. */}
          <div
            className="absolute inset-0 origin-center"
            style={{ transform: 'rotate(30deg) skew(-15deg, 0deg)', transformStyle: 'preserve-3d' }}
          >
            {/* Floor grid */}
            <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="absolute inset-0 w-full h-full opacity-20">
              {Array.from({ length: 11 }).map((_, i) => (
                <g key={i}>
                  <line x1={i * 10} y1="0" x2={i * 10} y2="100" stroke="#999" strokeWidth="0.2" />
                  <line x1="0" y1={i * 10} x2="100" y2={i * 10} stroke="#999" strokeWidth="0.2" />
                </g>
              ))}
            </svg>

            {/* Zones (transparent fills) */}
            {zones.map((z) => {
              const isVisible = visibleZoneIds.has(z.id);
              return (
                <div
                  key={z.id}
                  className={`absolute rounded-lg transition-opacity ${
                    isVisible ? 'opacity-90' : 'opacity-20'
                  }`}
                  style={{
                    left: `${z.pos_x}%`,
                    top: `${z.pos_y}%`,
                    width: `${z.width}%`,
                    height: `${z.height}%`,
                    backgroundColor: z.color_code || '#1A7A6A',
                    border: '2px solid rgba(0,0,0,0.3)',
                  }}
                  title={z.name}
                >
                  <div
                    className="absolute -top-5 left-2 text-[10px] font-medium text-black bg-white/80 px-1 rounded"
                    style={{ transform: 'skew(15deg, 0deg) rotate(-30deg)' }}
                  >
                    {z.name} ({z.product_count || 0}/{z.capacity || 0})
                  </div>
                </div>
              );
            })}

            {/* Furniture items */}
            {furniture.map((f) => (
              <div
                key={f.id}
                className={`absolute cursor-move transition-transform ${
                  selectedFurnId === f.id ? 'ring-2 ring-vz-teal rounded' : ''
                }`}
                style={{
                  left: `${f.pos_x}%`,
                  top: `${f.pos_y}%`,
                  transform: `translate(-50%, -50%) scale(${f.scale}) rotate(${f.rotation}deg)`,
                }}
                onMouseDown={(e) => {
                  e.preventDefault();
                  if (editMode) setDraggingId(f.id);
                  setSelectedFurnId(f.id);
                }}
              >
                <FurnitureSVG type={f.type} variant={f.variant} size={50} />
              </div>
            ))}
          </div>
        </div>

        {/* Selected furniture controls */}
        {editMode && selectedFurnId && (
          <div className="mt-2 p-2 bg-white rounded-lg border border-gray-200 flex items-center gap-2 flex-wrap">
            <span className="text-xs text-gray-500">Sélectionné</span>
            {(() => {
              const f = furniture.find((x) => x.id === selectedFurnId);
              if (!f) return null;
              return (
                <>
                  <span className="text-xs font-medium">{f.type} {f.variant ?? ''}</span>
                  <button
                    onClick={() => {
                      setFurniture((prev) => prev.map((x) =>
                        x.id === f.id ? { ...x, rotation: (x.rotation + 45) % 360 } : x
                      ));
                    }}
                    className="text-xs px-2 py-1 bg-gray-100 rounded min-h-0 min-w-0"
                  >
                    Pivoter +45°
                  </button>
                  <button
                    onClick={() => deleteFurniture(f.id)}
                    className="text-xs px-2 py-1 bg-red-50 text-red-600 rounded min-h-0 min-w-0"
                  >
                    Supprimer
                  </button>
                </>
              );
            })()}
          </div>
        )}
      </div>
    </div>
  );
}
