'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import Sidebar from '@/components/layout/Sidebar';
import workflowsData from './workflows.json';

type PackageCategory =
  | 'client'
  | 'hardware'
  | 'frontend'
  | 'backend'
  | 'scheduler'
  | 'data'
  | 'external';

interface WorkflowPackage {
  id: string;
  name: string;
  subtitle?: string;
  category: PackageCategory;
  description?: string;
  x: number;
  y: number;
}

interface WorkflowStep {
  from: string;
  to: string;
  label: string;
  detail: string;
  protocol?: string;
}

type WorkflowCategory = 'metier' | 'endpoint' | 'cron' | 'hardware';

interface Workflow {
  id: string;
  category: WorkflowCategory;
  group?: string;
  title: string;
  description: string;
  trigger?: string;
  steps: WorkflowStep[];
}

const data = workflowsData as unknown as {
  packages: WorkflowPackage[];
  workflows: Workflow[];
};

const BOX_WIDTH = 180;
const BOX_HEIGHT = 64;
const VIEW_W = 1240;
const VIEW_H = 820;

const CATEGORY_LABELS: Record<WorkflowCategory, string> = {
  metier: 'Parcours métier',
  endpoint: 'Endpoints API',
  cron: 'Crons & jobs',
  hardware: 'Hardware & Ops',
};

const PACKAGE_COLORS: Record<PackageCategory, { fill: string; stroke: string; label: string }> = {
  client: { fill: '#FFF7ED', stroke: '#F59E0B', label: 'Client' },
  hardware: { fill: '#FEF2F2', stroke: '#E84E8B', label: 'Hardware' },
  frontend: { fill: '#ECFEFF', stroke: '#0E7490', label: 'Frontend' },
  backend: { fill: '#CDE5DF', stroke: '#0B7A6A', label: 'Backend' },
  scheduler: { fill: '#F0FDF4', stroke: '#15803D', label: 'Scheduler' },
  data: { fill: '#EFF6FF', stroke: '#1D4ED8', label: 'Data' },
  external: { fill: '#F5F3FF', stroke: '#7C3AED', label: 'Externe' },
};

function pkgCenter(pkg: WorkflowPackage) {
  return { cx: pkg.x + BOX_WIDTH / 2, cy: pkg.y + BOX_HEIGHT / 2 };
}

function buildArrowPath(
  from: WorkflowPackage,
  to: WorkflowPackage,
  offsetIdx: number,
): { d: string; midX: number; midY: number; angle: number } {
  // Anchor at side closest to target
  const sameNode = from.id === to.id;
  if (sameNode) {
    // Loop: small arc above the node
    const { cx, cy } = pkgCenter(from);
    const r = 36 + offsetIdx * 6;
    const d = `M ${cx + 10} ${cy - BOX_HEIGHT / 2} C ${cx + 10 + r} ${cy - BOX_HEIGHT / 2 - r}, ${cx - 10 - r} ${cy - BOX_HEIGHT / 2 - r}, ${cx - 10} ${cy - BOX_HEIGHT / 2}`;
    return { d, midX: cx, midY: cy - BOX_HEIGHT / 2 - r, angle: 0 };
  }

  const fromC = pkgCenter(from);
  const toC = pkgCenter(to);
  const goingRight = toC.cx > fromC.cx;
  const fromX = goingRight ? from.x + BOX_WIDTH : from.x;
  const toX = goingRight ? to.x : to.x + BOX_WIDTH;
  const fromY = fromC.cy;
  const toY = toC.cy;

  // Slight bezier curve so parallel arrows fan out
  const dx = toX - fromX;
  const curve = Math.max(40, Math.abs(dx) * 0.35) + offsetIdx * 12;
  const c1x = fromX + (goingRight ? curve : -curve);
  const c1y = fromY + offsetIdx * 6;
  const c2x = toX + (goingRight ? -curve : curve);
  const c2y = toY - offsetIdx * 6;

  const d = `M ${fromX} ${fromY} C ${c1x} ${c1y}, ${c2x} ${c2y}, ${toX} ${toY}`;

  // Midpoint approximation for label placement
  const midX = (fromX + toX) / 2;
  const midY = (fromY + toY) / 2 - 8 - offsetIdx * 10;
  const angle = Math.atan2(toY - fromY, toX - fromX) * (180 / Math.PI);

  return { d, midX, midY, angle };
}

const VALID_CATEGORIES: WorkflowCategory[] = ['metier', 'endpoint', 'cron', 'hardware'];

export default function WorkflowsPage() {
  const searchParams = useSearchParams();
  const urlCategory = searchParams.get('category') as WorkflowCategory | null;
  const category: WorkflowCategory =
    urlCategory && VALID_CATEGORIES.includes(urlCategory) ? urlCategory : 'metier';
  const [search, setSearch] = useState('');
  const [selectedId, setSelectedId] = useState<string>(
    data.workflows.find((w) => w.category === 'metier')?.id ?? data.workflows[0].id,
  );
  const [hoveredStepIdx, setHoveredStepIdx] = useState<number | null>(null);
  const [zoomed, setZoomed] = useState(false);

  useEffect(() => {
    if (!zoomed) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setZoomed(false);
    };
    document.body.style.overflow = 'hidden';
    document.addEventListener('keydown', onKey);
    return () => {
      document.body.style.overflow = '';
      document.removeEventListener('keydown', onKey);
    };
  }, [zoomed]);

  const packagesById = useMemo(
    () => Object.fromEntries(data.packages.map((p) => [p.id, p])) as Record<string, WorkflowPackage>,
    [],
  );

  const visibleWorkflows = useMemo(() => {
    const q = search.trim().toLowerCase();
    return data.workflows
      .filter((w) => w.category === category)
      .filter(
        (w) =>
          !q ||
          w.title.toLowerCase().includes(q) ||
          w.description.toLowerCase().includes(q) ||
          (w.group?.toLowerCase().includes(q) ?? false),
      );
  }, [category, search]);

  // Auto-select first workflow if filter changes & current selection drops out
  React.useEffect(() => {
    if (!visibleWorkflows.find((w) => w.id === selectedId) && visibleWorkflows.length > 0) {
      setSelectedId(visibleWorkflows[0].id);
    }
  }, [visibleWorkflows, selectedId]);

  const selected = useMemo(
    () => data.workflows.find((w) => w.id === selectedId) ?? null,
    [selectedId],
  );

  // Packages touched by selected workflow + arrow paths
  const activePackageIds = useMemo(() => {
    if (!selected) return new Set<string>();
    const s = new Set<string>();
    selected.steps.forEach((st) => {
      s.add(st.from);
      s.add(st.to);
    });
    return s;
  }, [selected]);

  const arrows = useMemo(() => {
    if (!selected) return [];
    // Count duplicates on same (from, to) pair to offset them
    const seen: Record<string, number> = {};
    return selected.steps.map((step, idx) => {
      const fromPkg = packagesById[step.from];
      const toPkg = packagesById[step.to];
      if (!fromPkg || !toPkg) return null;
      const key = `${step.from}__${step.to}`;
      const offset = (seen[key] = (seen[key] ?? -1) + 1);
      const path = buildArrowPath(fromPkg, toPkg, offset);
      return { idx, step, path };
    }).filter(Boolean) as Array<{
      idx: number;
      step: WorkflowStep;
      path: { d: string; midX: number; midY: number; angle: number };
    }>;
  }, [selected, packagesById]);

  // Group workflows by `group` for the picker
  const groupedWorkflows = useMemo(() => {
    const out: Record<string, Workflow[]> = {};
    visibleWorkflows.forEach((w) => {
      const g = w.group ?? '—';
      if (!out[g]) out[g] = [];
      out[g].push(w);
    });
    return out;
  }, [visibleWorkflows]);

  const totalByCategory = useMemo(() => {
    return data.workflows.reduce<Record<WorkflowCategory, number>>(
      (acc, w) => {
        acc[w.category] = (acc[w.category] ?? 0) + 1;
        return acc;
      },
      { metier: 0, endpoint: 0, cron: 0, hardware: 0 },
    );
  }, []);

  const svgContent = (
    <>
      <defs>
        <marker
          id="arrow-teal"
          markerWidth="10"
          markerHeight="10"
          refX="8"
          refY="3"
          orient="auto"
          markerUnits="strokeWidth"
        >
          <path d="M0,0 L0,6 L9,3 z" fill="#0B7A6A" />
        </marker>
        <marker
          id="arrow-pink"
          markerWidth="10"
          markerHeight="10"
          refX="8"
          refY="3"
          orient="auto"
          markerUnits="strokeWidth"
        >
          <path d="M0,0 L0,6 L9,3 z" fill="#E84E8B" />
        </marker>
      </defs>

      {/* Column labels */}
      <g fontSize="11" fill="#8B8B86" fontWeight="600" letterSpacing="0.1em" textAnchor="middle">
        <text x={60 + BOX_WIDTH / 2} y={30}>CLIENT / HARDWARE</text>
        <text x={290 + BOX_WIDTH / 2} y={30}>FRONTEND</text>
        <text x={530 + BOX_WIDTH / 2} y={30}>BACKEND</text>
        <text x={760 + BOX_WIDTH / 2} y={30}>DATA</text>
        <text x={990 + BOX_WIDTH / 2} y={30}>EXTERNE</text>
      </g>

      {/* Packages */}
      {data.packages.map((pkg) => {
        const active = activePackageIds.has(pkg.id);
        const conf = PACKAGE_COLORS[pkg.category];
        return (
          <g key={pkg.id} transform={`translate(${pkg.x},${pkg.y})`}>
            <rect
              width={BOX_WIDTH}
              height={BOX_HEIGHT}
              rx={10}
              ry={10}
              fill={active ? conf.fill : '#FFFFFF'}
              stroke={active ? conf.stroke : '#D5D3CC'}
              strokeWidth={active ? 2 : 1}
              opacity={selected && !active ? 0.4 : 1}
            >
              <title>{pkg.description ?? pkg.name}</title>
            </rect>
            <text
              x={BOX_WIDTH / 2}
              y={26}
              textAnchor="middle"
              fontSize="13"
              fontWeight="600"
              fill={active ? conf.stroke : '#0E0E0C'}
              opacity={selected && !active ? 0.5 : 1}
            >
              {pkg.name}
            </text>
            {pkg.subtitle && (
              <text
                x={BOX_WIDTH / 2}
                y={44}
                textAnchor="middle"
                fontSize="10"
                fill="#8B8B86"
                opacity={selected && !active ? 0.5 : 1}
              >
                {pkg.subtitle}
              </text>
            )}
          </g>
        );
      })}

      {/* Arrows */}
      {arrows.map(({ idx, step, path }) => {
        const isHovered = hoveredStepIdx === idx;
        const color = isHovered ? '#E84E8B' : '#0B7A6A';
        return (
          <g key={idx}>
            <path
              d={path.d}
              fill="none"
              stroke={color}
              strokeWidth={isHovered ? 3 : 2}
              markerEnd={isHovered ? 'url(#arrow-pink)' : 'url(#arrow-teal)'}
              opacity={hoveredStepIdx !== null && !isHovered ? 0.25 : 0.9}
            >
              <title>{`${idx + 1}. ${step.label}`}</title>
            </path>
            {/* Step number badge */}
            <g transform={`translate(${path.midX},${path.midY})`}>
              <circle
                r="12"
                fill={color}
                stroke="#FFFFFF"
                strokeWidth="2"
                opacity={hoveredStepIdx !== null && !isHovered ? 0.3 : 1}
              />
              <text
                textAnchor="middle"
                dy="4"
                fontSize="11"
                fontWeight="700"
                fill="#FFFFFF"
                opacity={hoveredStepIdx !== null && !isHovered ? 0.3 : 1}
              >
                {idx + 1}
              </text>
            </g>
          </g>
        );
      })}
    </>
  );

  return (
    <div className="min-h-screen bg-vz-bg flex">
      <Sidebar />

      <main className="flex-1 md:ml-64 transition-all">
        <div className="px-4 md:px-6 py-6 max-w-[1800px] mx-auto">
          {/* Header */}
          <div className="mb-5 flex items-baseline justify-between gap-4 flex-wrap">
            <div>
              <h1 className="font-display text-2xl md:text-3xl text-vz-ink">
                Workflows Vintiz — {CATEGORY_LABELS[category]}
              </h1>
              <p className="text-sm text-vz-ink-soft mt-1">
                Documentation pilotée par <code className="text-xs bg-white px-1.5 py-0.5 rounded border border-vz-line">workflows.json</code> —
                cliquez un flux pour visualiser la propagation entre paquets et annoter chaque étape.
              </p>
            </div>
            <span className="text-xs text-vz-ink-mute">
              {totalByCategory[category]} flux dans cette catégorie
            </span>
          </div>

          {/* Main 3-column layout */}
          <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr_360px] gap-4">
            {/* LEFT — workflow picker */}
            <section className="bg-white border border-vz-line rounded-2xl p-3 max-h-[calc(100vh-180px)] overflow-y-auto">
              <input
                type="search"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Rechercher un flux…"
                className="w-full px-3 py-2 text-sm rounded-xl border border-vz-line focus:outline-none focus:ring-2 focus:ring-vz-teal mb-3"
              />
              {Object.keys(groupedWorkflows).length === 0 && (
                <p className="text-sm text-vz-ink-mute px-2 py-4">Aucun flux ne correspond.</p>
              )}
              {Object.entries(groupedWorkflows).map(([group, items]) => (
                <div key={group} className="mb-3">
                  <p className="px-2 mb-1 text-[10px] font-semibold tracking-[0.18em] uppercase text-vz-ink-mute">
                    {group}
                  </p>
                  <ul className="space-y-0.5">
                    {items.map((w) => {
                      const active = w.id === selectedId;
                      return (
                        <li key={w.id}>
                          <button
                            onClick={() => setSelectedId(w.id)}
                            className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${
                              active
                                ? 'bg-vz-teal-soft text-vz-teal-deep font-medium'
                                : 'hover:bg-vz-bg-alt text-vz-ink-soft'
                            }`}
                          >
                            <span className="block">{w.title}</span>
                            {w.steps.length > 0 && (
                              <span className="text-[11px] text-vz-ink-mute">
                                {w.steps.length} étape{w.steps.length > 1 ? 's' : ''}
                              </span>
                            )}
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              ))}
            </section>

            {/* CENTER — SVG graph */}
            <section className="bg-white border border-vz-line rounded-2xl p-3">
              <div className="flex items-center justify-between mb-2 px-2 gap-3">
                <h2 className="font-display text-lg text-vz-ink truncate">
                  {selected?.title ?? 'Sélectionnez un flux'}
                </h2>
                <div className="flex items-center gap-2 shrink-0">
                  <div className="hidden lg:flex flex-wrap gap-1.5 text-[10px]">
                    {(Object.entries(PACKAGE_COLORS) as Array<[PackageCategory, typeof PACKAGE_COLORS[PackageCategory]]>).map(
                      ([key, conf]) => (
                        <span
                          key={key}
                          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full border"
                          style={{ borderColor: conf.stroke, color: conf.stroke, background: conf.fill }}
                        >
                          <span
                            className="inline-block w-2 h-2 rounded-full"
                            style={{ background: conf.stroke }}
                          />
                          {conf.label}
                        </span>
                      ),
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => setZoomed(true)}
                    title="Agrandir (plein écran)"
                    className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-vz-line text-xs text-vz-ink-soft hover:bg-vz-bg-alt"
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="15 3 21 3 21 9" />
                      <polyline points="9 21 3 21 3 15" />
                      <line x1="21" y1="3" x2="14" y2="10" />
                      <line x1="3" y1="21" x2="10" y2="14" />
                    </svg>
                    Agrandir
                  </button>
                </div>
              </div>

              <svg
                viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
                className="w-full h-auto cursor-zoom-in"
                style={{ minHeight: 480 }}
                onClick={() => setZoomed(true)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') setZoomed(true); }}
                aria-label="Agrandir le diagramme du workflow"
              >
                {svgContent}
              </svg>
            </section>

            {/* RIGHT — workflow detail */}
            <section className="bg-white border border-vz-line rounded-2xl p-4 max-h-[calc(100vh-180px)] overflow-y-auto">
              {selected ? (
                <>
                  <div className="mb-3">
                    <span className="inline-block text-[10px] font-semibold tracking-[0.18em] uppercase text-vz-teal mb-1">
                      {selected.group ?? CATEGORY_LABELS[selected.category]}
                    </span>
                    <h3 className="font-display text-lg text-vz-ink leading-tight">
                      {selected.title}
                    </h3>
                    <p className="text-sm text-vz-ink-soft mt-2">{selected.description}</p>
                    {selected.trigger && (
                      <div className="mt-3 px-3 py-2 rounded-lg bg-vz-bg-alt text-xs text-vz-ink-soft">
                        <span className="font-semibold text-vz-ink-mute mr-2">DÉCLENCHEUR</span>
                        <code className="text-xs">{selected.trigger}</code>
                      </div>
                    )}
                  </div>

                  <ol className="space-y-2.5 mt-4">
                    {selected.steps.map((step, idx) => {
                      const fromPkg = packagesById[step.from];
                      const toPkg = packagesById[step.to];
                      return (
                        <li
                          key={idx}
                          onMouseEnter={() => setHoveredStepIdx(idx)}
                          onMouseLeave={() => setHoveredStepIdx(null)}
                          className={`p-2.5 rounded-lg border transition-colors cursor-default ${
                            hoveredStepIdx === idx
                              ? 'border-vz-accent bg-vz-accent-soft/40'
                              : 'border-vz-line hover:bg-vz-bg-alt'
                          }`}
                        >
                          <div className="flex items-start gap-2.5">
                            <span
                              className={`shrink-0 inline-flex items-center justify-center w-6 h-6 rounded-full text-[11px] font-bold text-white ${
                                hoveredStepIdx === idx ? 'bg-vz-accent' : 'bg-vz-teal'
                              }`}
                            >
                              {idx + 1}
                            </span>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center flex-wrap gap-1 text-[11px] text-vz-ink-mute mb-1">
                                <span className="font-medium text-vz-ink-soft">
                                  {fromPkg?.name ?? step.from}
                                </span>
                                <span>→</span>
                                <span className="font-medium text-vz-ink-soft">
                                  {toPkg?.name ?? step.to}
                                </span>
                                {step.protocol && (
                                  <span className="ml-1 px-1.5 py-0.5 bg-vz-bg-alt rounded text-[9px] font-semibold text-vz-ink-mute">
                                    {step.protocol}
                                  </span>
                                )}
                              </div>
                              <p className="text-sm text-vz-ink font-mono break-words">
                                {step.label}
                              </p>
                              <p className="text-xs text-vz-ink-soft mt-1 leading-relaxed">
                                {step.detail}
                              </p>
                            </div>
                          </div>
                        </li>
                      );
                    })}
                  </ol>
                </>
              ) : (
                <p className="text-sm text-vz-ink-mute">
                  Sélectionnez un flux dans la liste pour voir son détail.
                </p>
              )}
            </section>
          </div>

          <p className="text-[11px] text-vz-ink-mute mt-4 text-center">
            {data.workflows.length} flux · {data.packages.length} paquets ·
            <a
              href="https://github.com/juliengonde-5g/vintiz/blob/main/apps/web/src/app/dashboard/workflows/workflows.json"
              target="_blank"
              rel="noopener"
              className="ml-1 underline hover:text-vz-teal"
            >
              éditer workflows.json
            </a>
          </p>
        </div>
      </main>

      {zoomed && (
        <div
          className="fixed inset-0 z-50 bg-black/70 flex flex-col p-4"
          role="dialog"
          aria-modal="true"
          aria-label="Diagramme du workflow en plein écran"
        >
          <div className="flex items-center justify-between text-white mb-3 px-2">
            <div className="min-w-0">
              <p className="text-[10px] tracking-[0.22em] uppercase opacity-70">
                {selected?.group ?? CATEGORY_LABELS[category]}
              </p>
              <h2 className="font-display text-xl md:text-2xl truncate">
                {selected?.title ?? 'Workflow'}
              </h2>
            </div>
            <button
              type="button"
              onClick={() => setZoomed(false)}
              title="Fermer (Échap)"
              className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-white/10 hover:bg-white/20 text-sm"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
              Fermer
            </button>
          </div>
          <div
            className="flex-1 bg-white rounded-2xl overflow-auto p-4 cursor-zoom-out"
            onClick={() => setZoomed(false)}
          >
            <svg
              viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
              className="w-full h-full"
              preserveAspectRatio="xMidYMid meet"
              onClick={(e) => e.stopPropagation()}
            >
              {svgContent}
            </svg>
          </div>
        </div>
      )}
    </div>
  );
}
