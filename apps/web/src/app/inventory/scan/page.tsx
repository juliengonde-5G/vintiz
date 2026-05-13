'use client';

/**
 * Camera-as-scanner — alternative to a USB/Bluetooth barcode reader.
 *
 * Promoted to P1 in the M2 sprint : caméra arrière Android avec autofocus
 * permet de lire un EAN-13 / Code-128 directement depuis le viewfinder,
 * sans avoir à appairer un scanner Bluetooth chaque matin et en libérant
 * l'USB du dock.
 *
 * Decoder: ``@zxing/browser`` — supports EAN-13, EAN-8, UPC-A, UPC-E,
 * Code-128, Code-39, Code-93, ITF, QR, DataMatrix, PDF417 et autres.
 *
 * Behavior:
 * - Asks for ``video.environment`` (rear camera). Falls back to default
 *   if the user-facing camera is the only one (some Android phones).
 * - Once a barcode is decoded, navigates to ``/inventory?q=<barcode>`` —
 *   the existing inventory search page handles the rest.
 * - Shows the last scanned code + a "scan another" button to chain
 *   multiple captures during a stock check.
 */

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import Sidebar from '@/components/layout/Sidebar';
import Button from '@/components/ui/Button';
import Card from '@/components/ui/Card';

type ScanState =
  | { phase: 'idle' }
  | { phase: 'starting' }
  | { phase: 'scanning' }
  | { phase: 'detected'; code: string }
  | { phase: 'error'; reason: string };

export default function InventoryScanPage() {
  const router = useRouter();
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const controlsRef = useRef<{ stop: () => void } | null>(null);
  const [state, setState] = useState<ScanState>({ phase: 'idle' });

  useEffect(() => {
    let cancelled = false;
    setState({ phase: 'starting' });

    (async () => {
      try {
        // Lazy-load zxing — keeps the main bundle small for users who
        // never hit /inventory/scan.
        const { BrowserMultiFormatReader } = await import('@zxing/browser');
        if (cancelled) return;
        const reader = new BrowserMultiFormatReader();

        const constraints: MediaStreamConstraints = {
          video: { facingMode: { ideal: 'environment' } },
          audio: false,
        };

        const controls = await reader.decodeFromConstraints(
          constraints,
          videoRef.current!,
          (result) => {
            if (cancelled) return;
            if (result) {
              const code = result.getText();
              if (code) {
                controls.stop();
                setState({ phase: 'detected', code });
              }
            }
            // Errors here are per-frame "no barcode found" — silent.
          },
        );
        controlsRef.current = controls;
        if (!cancelled) setState({ phase: 'scanning' });
      } catch (err) {
        if (cancelled) return;
        const reason =
          (err as Error)?.name === 'NotAllowedError'
            ? "Accès caméra refusé. Autorise dans les réglages du navigateur."
            : (err as Error)?.message || "Impossible de démarrer la caméra.";
        setState({ phase: 'error', reason });
      }
    })();

    return () => {
      cancelled = true;
      controlsRef.current?.stop();
      controlsRef.current = null;
    };
  }, []);

  const goToProduct = () => {
    if (state.phase !== 'detected') return;
    router.push(`/inventory?q=${encodeURIComponent(state.code)}`);
  };

  const scanAgain = () => {
    // Re-mount the page to restart the camera cleanly. Cheaper than
    // managing the BrowserMultiFormatReader lifecycle ourselves.
    router.refresh();
    setState({ phase: 'starting' });
  };

  return (
    <div className="flex min-h-screen bg-vz-bg">
      <Sidebar />
      <main className="flex-1 p-6">
        <div className="max-w-2xl mx-auto space-y-4">
          <div className="flex items-center justify-between">
            <h1 className="font-display text-2xl text-vz-ink">Scanner caméra</h1>
            <Link href="/inventory" className="text-sm text-vz-teal hover:underline">
              ← Retour inventaire
            </Link>
          </div>

          <Card title="Viseur">
            <div className="relative aspect-[4/3] bg-black rounded-lg overflow-hidden">
              <video
                ref={videoRef}
                className="w-full h-full object-cover"
                playsInline
                muted
              />
              {/* Overlay viewfinder rectangle + scan line — purely cosmetic. */}
              {state.phase === 'scanning' && (
                <div className="absolute inset-8 border-2 border-vz-teal-soft/80 rounded-lg pointer-events-none">
                  <div className="absolute left-0 right-0 h-0.5 bg-vz-teal animate-pulse" style={{ top: '50%' }} />
                </div>
              )}
            </div>

            <div className="mt-4 space-y-2 text-sm">
              {state.phase === 'starting' && (
                <p className="text-vz-ink-soft">Démarrage de la caméra…</p>
              )}
              {state.phase === 'scanning' && (
                <p className="text-vz-ink-soft">
                  Cadre le code-barres dans le viseur. La détection est automatique.
                </p>
              )}
              {state.phase === 'detected' && (
                <div className="rounded-lg border-2 border-vz-teal-soft bg-vz-teal-soft/30 p-4">
                  <p className="text-xs uppercase tracking-widest text-vz-ink-mute">Code détecté</p>
                  <p className="font-mono text-lg text-vz-ink mt-1 break-all">{state.code}</p>
                  <div className="mt-3 flex gap-2">
                    <Button onClick={goToProduct}>Voir le produit →</Button>
                    <Button variant="outline" onClick={scanAgain}>Scanner un autre</Button>
                  </div>
                </div>
              )}
              {state.phase === 'error' && (
                <div role="alert" className="rounded-lg border border-red-300 bg-red-50 p-3 text-red-700">
                  {state.reason}
                </div>
              )}
            </div>
          </Card>

          <p className="text-xs text-vz-ink-mute">
            Astuce&nbsp;: si la détection est lente, ajoute de la lumière sur le code-barres
            ou rapproche le produit (~15&nbsp;cm). Le scanner reconnaît les EAN-13,
            Code-128, Code-39, ITF, QR et DataMatrix.
          </p>
        </div>
      </main>
    </div>
  );
}
