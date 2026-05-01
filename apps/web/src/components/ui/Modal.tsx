'use client';

import React, { useEffect, useId, useRef } from 'react';

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  actions?: React.ReactNode;
  /**
   * Set to ``false`` to opt out of the click-outside-to-close behaviour
   * for modals that wrap critical flows (e.g. payment in progress).
   */
  closeOnBackdrop?: boolean;
}

const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(', ');

/**
 * Accessible modal dialog.
 *
 * Adds vs. the previous version:
 * - ``role="dialog"`` + ``aria-modal="true"`` + ``aria-labelledby``
 * - ESC closes
 * - Focus is trapped inside the dialog while open (Tab / Shift+Tab cycle)
 * - Focus is moved to the close button on open and restored to the
 *   previous activeElement on close (so screen readers and keyboard
 *   users don't get dropped at the top of the page).
 */
export default function Modal({
  open,
  onClose,
  title,
  children,
  actions,
  closeOnBackdrop = true,
}: ModalProps) {
  const titleId = useId();
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const closeBtnRef = useRef<HTMLButtonElement | null>(null);
  const previouslyFocused = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;
    document.body.style.overflow = 'hidden';
    previouslyFocused.current = document.activeElement as HTMLElement | null;
    // Move focus into the dialog on open.
    queueMicrotask(() => {
      const focusables = dialogRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR);
      const first = focusables?.[0] ?? closeBtnRef.current;
      first?.focus();
    });
    return () => {
      document.body.style.overflow = '';
      // Restore focus only if the previously focused element is still in the DOM.
      const prev = previouslyFocused.current;
      if (prev && document.body.contains(prev)) {
        prev.focus();
      }
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        onClose();
        return;
      }
      if (e.key !== 'Tab') return;
      // Focus trap.
      const focusables = dialogRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR);
      if (!focusables || focusables.length === 0) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      const active = document.activeElement as HTMLElement | null;
      if (e.shiftKey && active === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && active === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
    >
      <div
        className="absolute inset-0 bg-black/50"
        aria-hidden="true"
        onClick={closeOnBackdrop ? onClose : undefined}
      />
      <div
        ref={dialogRef}
        className="relative bg-white rounded-xl shadow-xl w-full max-w-lg mx-4 max-h-[90vh] flex flex-col"
      >
        <div className="flex items-center justify-between p-5 border-b border-gray-200">
          <h2 id={titleId} className="text-lg font-semibold text-black">{title}</h2>
          <button
            ref={closeBtnRef}
            onClick={onClose}
            className="min-h-[44px] min-w-[44px] flex items-center justify-center rounded-lg hover:bg-gray-100 transition-colors"
            aria-label="Fermer"
          >
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <line x1="4" y1="4" x2="16" y2="16" />
              <line x1="16" y1="4" x2="4" y2="16" />
            </svg>
          </button>
        </div>
        <div className="p-5 overflow-y-auto flex-1">{children}</div>
        {actions && (
          <div className="p-5 border-t border-gray-200 flex justify-end gap-3">
            {actions}
          </div>
        )}
      </div>
    </div>
  );
}
