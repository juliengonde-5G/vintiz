'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';

// --- Typage minimal de l'API Web Speech (non incluse dans les libs DOM TS) ---
interface SpeechAlternative {
  transcript: string;
}
interface SpeechResult {
  0: SpeechAlternative;
  isFinal: boolean;
  length: number;
}
interface SpeechResultList {
  length: number;
  [index: number]: SpeechResult;
}
interface SpeechEvent {
  resultIndex: number;
  results: SpeechResultList;
}
interface SpeechRecognitionLike {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((e: SpeechEvent) => void) | null;
  onerror: ((e: { error?: string }) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
}
type SpeechRecognitionCtor = new () => SpeechRecognitionLike;

function getRecognitionCtor(): SpeechRecognitionCtor | null {
  if (typeof window === 'undefined') return null;
  const w = window as unknown as {
    SpeechRecognition?: SpeechRecognitionCtor;
    webkitSpeechRecognition?: SpeechRecognitionCtor;
  };
  return w.SpeechRecognition || w.webkitSpeechRecognition || null;
}

/**
 * Bouton micro optionnel : dictée vocale (Web Speech API, fr-FR). Accumule le
 * transcript final et le renvoie via ``onTranscript`` à l'arrêt. Ne s'affiche
 * pas si le navigateur ne supporte pas la reconnaissance vocale (dégradation
 * silencieuse — la saisie manuelle / photo reste disponible).
 */
export default function VoiceDictationButton({
  onTranscript,
  disabled,
  busy,
}: {
  onTranscript: (transcript: string) => void;
  disabled?: boolean;
  busy?: boolean;
}) {
  const [supported, setSupported] = useState(false);
  const [listening, setListening] = useState(false);
  const [interim, setInterim] = useState('');
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const finalRef = useRef('');

  useEffect(() => {
    setSupported(getRecognitionCtor() !== null);
  }, []);

  const stop = useCallback(() => {
    recognitionRef.current?.stop();
  }, []);

  const start = useCallback(() => {
    const Ctor = getRecognitionCtor();
    if (!Ctor) return;
    const rec = new Ctor();
    rec.lang = 'fr-FR';
    rec.continuous = true;
    rec.interimResults = true;
    finalRef.current = '';
    setInterim('');

    rec.onresult = (e: SpeechEvent) => {
      let interimText = '';
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const r = e.results[i];
        const txt = r[0]?.transcript ?? '';
        if (r.isFinal) finalRef.current += txt + ' ';
        else interimText += txt;
      }
      setInterim(interimText);
    };
    rec.onerror = () => {
      setListening(false);
    };
    rec.onend = () => {
      setListening(false);
      setInterim('');
      const text = finalRef.current.trim();
      if (text) onTranscript(text);
    };

    recognitionRef.current = rec;
    setListening(true);
    rec.start();
  }, [onTranscript]);

  useEffect(() => () => recognitionRef.current?.stop(), []);

  if (!supported) return null;

  return (
    <div className="flex flex-col gap-1">
      <button
        type="button"
        onClick={listening ? stop : start}
        disabled={disabled || busy}
        className={`inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors disabled:opacity-50 ${
          listening
            ? 'bg-red-500 text-white animate-pulse'
            : 'bg-vz-teal-soft text-vz-teal hover:bg-vz-teal hover:text-white'
        }`}
        title="Dicter la fiche produit (optionnel)"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
          <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
          <line x1="12" y1="19" x2="12" y2="23" />
          <line x1="8" y1="23" x2="16" y2="23" />
        </svg>
        {busy ? 'Analyse…' : listening ? 'Stop' : 'Dicter la fiche'}
      </button>
      {listening && (
        <span className="text-xs text-vz-ink-mute italic min-h-[1rem]">
          {interim || 'Parlez… (ex. « chemise Brice taille L homme, très bon état, 8 euros »)'}
        </span>
      )}
    </div>
  );
}
