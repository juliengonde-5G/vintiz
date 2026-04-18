'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';

type NavItem = {
  label: string;
  href: string;
  icon: React.ReactNode;
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
    ],
  },
  {
    label: 'Intelligence',
    items: [
      {
        label: 'Compagnon IA',
        href: '/ia',
        icon: (
          <svg {...iconProps}>
            <path d="M12 2a4 4 0 0 1 4 4v1h1a3 3 0 0 1 3 3v1a3 3 0 0 1-3 3h-1v4a2 2 0 0 1-2 2h-4a2 2 0 0 1-2-2v-4H7a3 3 0 0 1-3-3v-1a3 3 0 0 1 3-3h1V6a4 4 0 0 1 4-4z" />
            <circle cx="9" cy="13" r="1" />
            <circle cx="15" cy="13" r="1" />
          </svg>
        ),
      },
      {
        label: 'SEO',
        href: '/seo',
        icon: (
          <svg {...iconProps}>
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
            <line x1="8" y1="11" x2="14" y2="11" />
            <line x1="11" y1="8" x2="11" y2="14" />
          </svg>
        ),
      },
    ],
  },
  {
    label: 'Configuration',
    items: [
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

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const [collapsed, setCollapsed] = useState(false);
  const [userName, setUserName] = useState<string>('Admin');

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const token = localStorage.getItem('token');
    if (!token) router.replace('/login');
    const stored = localStorage.getItem('username');
    if (stored) setUserName(stored);
  }, [router]);

  const isItemActive = (href: string) => {
    if (href === '/dashboard') return pathname === href;
    return pathname === href || pathname.startsWith(`${href}/`);
  };

  return (
    <>
      {/* Mobile hamburger */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="fixed top-4 left-4 z-50 md:hidden min-h-[44px] min-w-[44px] flex items-center justify-center rounded-lg bg-white shadow-md"
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
        className={`fixed top-0 left-0 h-full bg-white border-r border-gray-100 z-40 transition-transform duration-200 w-64 flex flex-col ${
          collapsed ? 'translate-x-0' : '-translate-x-full'
        } md:translate-x-0`}
      >
        {/* Brand */}
        <div className="px-6 pt-6 pb-5 border-b border-gray-100 flex flex-col items-center">
          <img
            src="/logo-teal.png"
            alt="Vintiz"
            className="h-14 w-auto mb-1 select-none"
            draggable={false}
          />
          <p className="text-[10px] tracking-[0.25em] text-gray-400 uppercase">Back Office</p>
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-3 overflow-y-auto">
          {navGroups.map((group) => (
            <div key={group.label} className="mb-4">
              <p className="px-6 mb-1 text-[10px] font-semibold tracking-[0.22em] uppercase text-gray-400">
                {group.label}
              </p>
              <ul className="space-y-0.5 px-3">
                {group.items.map((item) => {
                  const isActive = isItemActive(item.href);
                  return (
                    <li key={item.href}>
                      <Link
                        href={item.href}
                        onClick={() => setCollapsed(false)}
                        className={`relative flex items-center gap-3 px-4 py-2.5 rounded-xl min-h-[44px] transition-all ${
                          isActive
                            ? 'bg-gradient-warm text-teal font-medium shadow-sm'
                            : 'text-gray-600 hover:bg-gray-50 hover:text-black'
                        }`}
                      >
                        {isActive && (
                          <span className="absolute left-0 top-2 bottom-2 w-1 rounded-r-full bg-teal" />
                        )}
                        <span className={isActive ? 'text-teal' : 'text-gray-400'}>
                          {item.icon}
                        </span>
                        <span className="text-sm">{item.label}</span>
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>

        {/* User + Logout */}
        <div className="p-3 border-t border-gray-100 space-y-1">
          <div className="flex items-center gap-3 px-3 py-2 rounded-xl bg-cream">
            <div className="h-9 w-9 rounded-full bg-gradient-signature flex items-center justify-center text-white font-semibold font-display text-sm">
              {userName.slice(0, 1).toUpperCase()}
            </div>
            <div className="min-w-0">
              <p className="text-sm font-medium text-black truncate">{userName}</p>
              <p className="text-[11px] text-gray-500">Manager</p>
            </div>
          </div>
          <button
            onClick={() => {
              if (typeof window !== 'undefined') {
                localStorage.removeItem('token');
                window.location.href = '/login';
              }
            }}
            className="flex items-center gap-3 px-4 py-2.5 rounded-xl min-h-[44px] w-full text-gray-500 hover:bg-red-50 hover:text-red-600 transition-colors"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
              <polyline points="16 17 21 12 16 7" />
              <line x1="21" y1="12" x2="9" y2="12" />
            </svg>
            <span className="text-sm">Deconnexion</span>
          </button>
        </div>
      </aside>
    </>
  );
}
