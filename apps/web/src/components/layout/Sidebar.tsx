'use client';

import React, { Suspense, useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';

type NavItem = {
  label: string;
  href: string;
  icon: React.ReactNode;
  // For items sharing the same pathname but distinguished by a query
  // parameter (e.g. /dashboard/workflows?category=metier|endpoint|...).
  matchQuery?: { key: string; value: string };
  indent?: boolean;
};

type NavGroup = {
  label: string;
  items: NavItem[];
};

const iconProps = {
  width: 22,
  height: 22,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
};

const navGroups: NavGroup[] = [
  {
    label: 'Pilotage',
    items: [
      {
        label: 'Dashboard',
        href: '/dashboard',
        icon: (
          <svg {...iconProps}>
            <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
            <polyline points="9 22 9 12 15 12 15 22" />
          </svg>
        ),
      },
      {
        label: 'Cahier du jour',
        href: '/dashboard/cahier-du-jour',
        icon: (
          <svg {...iconProps}>
            <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
            <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
          </svg>
        ),
      },
      {
        label: 'Rapports',
        href: '/reports',
        icon: (
          <svg {...iconProps}>
            <line x1="18" y1="20" x2="18" y2="10" />
            <line x1="12" y1="20" x2="12" y2="4" />
            <line x1="6" y1="20" x2="6" y2="14" />
          </svg>
        ),
      },
    ],
  },
  {
    label: 'Commerce',
    items: [
      {
        label: 'Caisse',
        href: '/pos',
        icon: (
          <svg {...iconProps}>
            <circle cx="9" cy="21" r="1" />
            <circle cx="20" cy="21" r="1" />
            <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6" />
          </svg>
        ),
      },
      {
        label: 'Inventaire',
        href: '/inventory',
        icon: (
          <svg {...iconProps}>
            <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
            <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
            <line x1="12" y1="22.08" x2="12" y2="12" />
          </svg>
        ),
      },
      {
        label: 'Mouvements',
        href: '/inventory/movements',
        icon: (
          <svg {...iconProps}>
            <polyline points="17 11 21 7 17 3" />
            <line x1="21" y1="7" x2="9" y2="7" />
            <polyline points="7 21 3 17 7 13" />
            <line x1="3" y1="17" x2="15" y2="17" />
          </svg>
        ),
      },
      {
        label: 'Espaces',
        href: '/zones',
        icon: (
          <svg {...iconProps}>
            <rect x="3" y="3" width="7" height="7" rx="1" />
            <rect x="14" y="3" width="7" height="5" rx="1" />
            <rect x="14" y="12" width="7" height="9" rx="1" />
            <rect x="3" y="14" width="7" height="7" rx="1" />
          </svg>
        ),
      },
      {
        label: 'Clients',
        href: '/clients',
        icon: (
          <svg {...iconProps}>
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
            <circle cx="9" cy="7" r="4" />
            <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
            <path d="M16 3.13a4 4 0 0 1 0 7.75" />
          </svg>
        ),
      },
      {
        label: 'Newsletter',
        href: '/newsletter',
        icon: (
          <svg {...iconProps}>
            <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
            <polyline points="22,6 12,13 2,6" />
          </svg>
        ),
      },
      {
        label: 'Opérations',
        href: '/admin/operations',
        icon: (
          <svg {...iconProps}>
            <path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z" />
            <line x1="7" y1="7" x2="7.01" y2="7" />
          </svg>
        ),
      },
    ],
  },
  {
    label: 'Intelligence',
    items: [
      {
        label: 'Vintiz IA',
        href: '/ia',
        icon: (
          <svg {...iconProps}>
            <path d="M12 2a4 4 0 0 1 4 4v1h1a3 3 0 0 1 3 3v1a3 3 0 0 1-3 3h-1v4a2 2 0 0 1-2 2h-4a2 2 0 0 1-2-2v-4H7a3 3 0 0 1-3-3v-1a3 3 0 0 1 3-3h1V6a4 4 0 0 1 4-4z" />
            <circle cx="9" cy="13" r="1" />
            <circle cx="15" cy="13" r="1" />
          </svg>
        ),
      },
    ],
  },
  {
    label: 'Comptabilité',
    items: [
      {
        label: 'Exports',
        href: '/accounting/exports',
        icon: (
          <svg {...iconProps}>
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="16" y1="13" x2="8" y2="13" />
            <line x1="16" y1="17" x2="8" y2="17" />
            <polyline points="10 9 9 9 8 9" />
          </svg>
        ),
      },
      {
        label: 'Journal',
        href: '/accounting/journal',
        icon: (
          <svg {...iconProps}>
            <line x1="8" y1="6" x2="21" y2="6" />
            <line x1="8" y1="12" x2="21" y2="12" />
            <line x1="8" y1="18" x2="21" y2="18" />
            <line x1="3" y1="6" x2="3.01" y2="6" />
            <line x1="3" y1="12" x2="3.01" y2="12" />
            <line x1="3" y1="18" x2="3.01" y2="18" />
          </svg>
        ),
      },
      {
        label: 'Réconciliation',
        href: '/accounting/reconciliation',
        icon: (
          <svg {...iconProps}>
            <polyline points="16 3 21 3 21 8" />
            <line x1="4" y1="20" x2="21" y2="3" />
            <polyline points="21 16 21 21 16 21" />
            <line x1="15" y1="15" x2="21" y2="21" />
          </svg>
        ),
      },
      {
        label: 'Paramétrage',
        href: '/settings/comptabilite',
        icon: (
          <svg {...iconProps}>
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
          </svg>
        ),
      },
    ],
  },
  {
    label: 'Configuration',
    items: [
      {
        label: 'Admin',
        href: '/admin',
        icon: (
          <svg {...iconProps}>
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            <polyline points="9 12 11 14 15 10" />
          </svg>
        ),
      },
      {
        label: 'Utilisateurs',
        href: '/admin/users',
        icon: (
          <svg {...iconProps}>
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
            <circle cx="9" cy="7" r="4" />
            <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
            <path d="M16 3.13a4 4 0 0 1 0 7.75" />
          </svg>
        ),
      },
      {
        label: 'Transactions',
        href: '/admin/transactions',
        icon: (
          <svg {...iconProps}>
            <line x1="12" y1="1" x2="12" y2="23" />
            <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
          </svg>
        ),
      },
      {
        label: 'Rapports Z',
        href: '/admin/z-reports',
        icon: (
          <svg {...iconProps}>
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <path d="M9 13l2 2 4-4" />
          </svg>
        ),
      },
      {
        label: 'Base de données',
        href: '/admin/database',
        icon: (
          <svg {...iconProps}>
            <ellipse cx="12" cy="5" rx="9" ry="3" />
            <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
            <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
          </svg>
        ),
      },
      {
        label: 'Parametres',
        href: '/settings',
        icon: (
          <svg {...iconProps}>
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
          </svg>
        ),
      },
    ],
  },
];

// Hidden for role=collaborateur (Lot 7).
const COLLAB_HIDDEN_GROUPS = new Set(['Configuration']);
const COLLAB_HIDDEN_PATHS = new Set(['/seo', '/admin/operations']);

// Minimal placeholder rendered while Suspense hydrates the inner sidebar.
// Matches the desktop dimensions of the real aside so the layout doesn't
// shift on first paint.
function SidebarFallback() {
  return (
    <aside
      aria-hidden
      className="hidden md:flex fixed top-0 left-0 h-full w-64 bg-white border-r border-gray-100 z-40"
    />
  );
}

export default function Sidebar() {
  return (
    <Suspense fallback={<SidebarFallback />}>
      <SidebarInner />
    </Suspense>
  );
}

function SidebarInner() {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [collapsed, setCollapsed] = useState(false);
  const [desktopCollapsed, setDesktopCollapsed] = useState(false);
  const [userName, setUserName] = useState<string>('Admin');
  const [role, setRole] = useState<'manager' | 'collaborateur' | null>(null);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const token = localStorage.getItem('token');
    if (!token) router.replace('/login');
    const stored = localStorage.getItem('username');
    if (stored) setUserName(stored);
    const storedRole = localStorage.getItem('role') as 'manager' | 'collaborateur' | null;
    if (storedRole) setRole(storedRole);
    // Lot 7 — restrict /admin/*, /settings, /seo to managers
    if (storedRole === 'collaborateur') {
      const blocked = ['/admin', '/settings', '/seo'];
      if (blocked.some((p) => pathname === p || pathname.startsWith(`${p}/`))) {
        router.replace('/dashboard');
      }
    }
    const sidebarPref = localStorage.getItem('vintiz_sidebar_state');
    if (sidebarPref === 'collapsed') setDesktopCollapsed(true);
  }, [router, pathname]);

  useEffect(() => {
    if (typeof document === 'undefined') return;
    document.body.dataset.sidebar = desktopCollapsed ? 'collapsed' : 'expanded';
    if (typeof window !== 'undefined') {
      localStorage.setItem('vintiz_sidebar_state', desktopCollapsed ? 'collapsed' : 'expanded');
    }
  }, [desktopCollapsed]);

  const isItemActive = (item: NavItem) => {
    // Strip the optional query string for pathname comparison.
    const itemPath = item.href.split('?')[0];
    if (itemPath === '/dashboard') {
      if (pathname !== itemPath) return false;
    } else if (pathname === itemPath) {
      // exact match always wins
    } else if (pathname.startsWith(`${itemPath}/`)) {
      // Prefix match — but defer to a more specific sibling nav item so a
      // dedicated sub-module (e.g. /inventory/movements) doesn't also light
      // up its parent (/inventory). Detail routes with no dedicated nav item
      // (e.g. /inventory/<id>) still highlight the parent.
      const hasMoreSpecific = navGroups.some((g) =>
        g.items.some((other) => {
          const otherPath = other.href.split('?')[0];
          return (
            otherPath !== itemPath &&
            otherPath.startsWith(`${itemPath}/`) &&
            (pathname === otherPath || pathname.startsWith(`${otherPath}/`))
          );
        }),
      );
      if (hasMoreSpecific) return false;
    } else {
      return false;
    }
    // If the item discriminates on a query param, only match when the
    // current URL carries the same value (default to first registered
    // value when the param is absent).
    if (item.matchQuery) {
      const current = searchParams?.get(item.matchQuery.key);
      if (current) return current === item.matchQuery.value;
      // No param in URL: only the item that represents the default value
      // (the workflow page falls back to "metier") is considered active.
      return item.matchQuery.value === 'metier';
    }
    return true;
  };

  return (
    <>
      {/* Mobile hamburger */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="fixed top-4 left-4 z-50 md:hidden min-h-[48px] min-w-[48px] flex items-center justify-center rounded-lg bg-white shadow-md"
        aria-label="Menu"
      >
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#1A1A1A" strokeWidth="2" strokeLinecap="round">
          <line x1="3" y1="6" x2="21" y2="6" />
          <line x1="3" y1="12" x2="21" y2="12" />
          <line x1="3" y1="18" x2="21" y2="18" />
        </svg>
      </button>

      {collapsed && (
        <div
          className="fixed inset-0 bg-black/30 z-40 md:hidden"
          onClick={() => setCollapsed(false)}
        />
      )}

      <aside
        className={`fixed top-0 left-0 h-full bg-white border-r border-gray-100 z-40 transition-all duration-200 flex flex-col ${
          collapsed ? 'translate-x-0' : '-translate-x-full'
        } md:translate-x-0 ${desktopCollapsed ? 'md:w-16' : 'w-64'} ${!desktopCollapsed ? 'w-64' : ''}`}
      >
        {/* Desktop expand/collapse toggle */}
        <button
          onClick={() => setDesktopCollapsed(!desktopCollapsed)}
          className="hidden md:flex absolute -right-3 top-20 z-50 h-6 w-6 min-h-0 min-w-0 items-center justify-center rounded-full bg-white border border-gray-200 shadow-sm hover:bg-gray-50 text-gray-500"
          aria-label={desktopCollapsed ? 'Étendre la barre latérale' : 'Réduire la barre latérale'}
          title={desktopCollapsed ? 'Étendre' : 'Réduire'}
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            {desktopCollapsed ? (
              <polyline points="9 18 15 12 9 6" />
            ) : (
              <polyline points="15 18 9 12 15 6" />
            )}
          </svg>
        </button>

        {/* Brand */}
        <div className={`pt-6 pb-5 border-b border-gray-100 flex flex-col items-center ${desktopCollapsed ? 'md:px-2' : 'px-6'}`}>
          <img
            src="/logo-teal.png"
            alt="Vintiz"
            className={`w-auto mb-1 select-none transition-all ${desktopCollapsed ? 'md:h-8' : 'h-14'}`}
            draggable={false}
          />
          {!desktopCollapsed && (
            <p className="text-[10px] tracking-[0.25em] text-gray-400 uppercase">Back Office</p>
          )}
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-3 overflow-y-auto">
          {navGroups
            .filter((group) => role !== 'collaborateur' || !COLLAB_HIDDEN_GROUPS.has(group.label))
            .map((group) => {
              const items = group.items.filter(
                (item) => role !== 'collaborateur' || !COLLAB_HIDDEN_PATHS.has(item.href),
              );
              if (items.length === 0) return null;
              return (
            <div key={group.label} className="mb-4">
              {!desktopCollapsed && (
                <p className="md:px-6 px-6 mb-1 text-[10px] font-semibold tracking-[0.22em] uppercase text-gray-400">
                  {group.label}
                </p>
              )}
              <ul className={`space-y-0.5 ${desktopCollapsed ? 'md:px-2' : 'px-3'}`}>
                {items.map((item) => {
                  const isActive = isItemActive(item);
                  const indented = item.indent && !desktopCollapsed;
                  return (
                    <li key={item.href}>
                      <Link
                        href={item.href}
                        onClick={() => setCollapsed(false)}
                        title={desktopCollapsed ? item.label : undefined}
                        className={`relative flex items-center gap-3 ${desktopCollapsed ? 'md:justify-center md:px-2 px-4' : indented ? 'pl-10 pr-4' : 'px-4'} ${indented ? 'py-1.5 min-h-[36px]' : 'py-2.5 min-h-[48px]'} rounded-xl transition-all ${
                          isActive
                            ? 'bg-vz-bg text-vz-teal font-medium shadow-sm'
                            : 'text-gray-600 hover:bg-gray-50 hover:text-black'
                        }`}
                      >
                        {isActive && (
                          <span className="absolute left-0 top-2 bottom-2 w-1 rounded-r-full bg-vz-teal" />
                        )}
                        {!indented && (
                          <span className={isActive ? 'text-vz-teal' : 'text-gray-400'}>
                            {item.icon}
                          </span>
                        )}
                        <span className={`text-sm ${desktopCollapsed ? 'md:hidden' : ''} ${indented ? 'text-[13px]' : ''}`}>{item.label}</span>
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
              );
            })}
        </nav>

        {/* User + Logout */}
        <div className={`p-3 border-t border-gray-100 space-y-1 ${desktopCollapsed ? 'md:p-2' : ''}`}>
          {!desktopCollapsed ? (
            <div className="flex items-center gap-3 px-3 py-2 rounded-xl bg-vz-bg">
              <div className="h-9 w-9 rounded-full bg-vz-teal flex items-center justify-center text-white font-semibold font-display text-sm">
                {userName.slice(0, 1).toUpperCase()}
              </div>
              <div className="min-w-0">
                <p className="text-sm font-medium text-black truncate">{userName}</p>
                <p className="text-[11px] text-gray-500">Manager</p>
              </div>
            </div>
          ) : (
            <div className="hidden md:flex justify-center" title={userName}>
              <div className="h-9 w-9 rounded-full bg-vz-teal flex items-center justify-center text-white font-semibold font-display text-sm">
                {userName.slice(0, 1).toUpperCase()}
              </div>
            </div>
          )}
          <button
            onClick={() => {
              if (typeof window !== 'undefined') {
                localStorage.removeItem('token');
                window.location.href = '/login';
              }
            }}
            title={desktopCollapsed ? 'Deconnexion' : undefined}
            className={`flex items-center gap-3 ${desktopCollapsed ? 'md:justify-center md:px-2 px-4' : 'px-4'} py-2.5 rounded-xl min-h-[48px] w-full text-gray-500 hover:bg-red-50 hover:text-red-600 transition-colors`}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
              <polyline points="16 17 21 12 16 7" />
              <line x1="21" y1="12" x2="9" y2="12" />
            </svg>
            <span className={`text-sm ${desktopCollapsed ? 'md:hidden' : ''}`}>Deconnexion</span>
          </button>
        </div>
      </aside>
    </>
  );
}
