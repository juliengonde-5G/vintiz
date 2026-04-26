'use client';

import React from 'react';

export type RecoCardData = {
  product_id: string;
  product_name: string;
  product_thumb?: string | null;
  score?: number | null;
  days_on_shelf?: number | null;
  action: 'METTRE_EN_AVANT' | 'DEMARQUER' | 'RETIRER' | 'MAINTENIR';
  reasons: string[];
  similar_products?: { id: string; name: string; thumb?: string | null }[];
};

const ACTION_META = {
  METTRE_EN_AVANT: { label: 'Mettre en avant', color: 'bg-green-100 text-green-700', icon: '⭐' },
  DEMARQUER: { label: 'Démarquer', color: 'bg-orange-100 text-orange-700', icon: '🏷️' },
  RETIRER: { label: 'Retirer du rayon', color: 'bg-red-100 text-red-700', icon: '🚫' },
  MAINTENIR: { label: 'Maintenir', color: 'bg-blue-100 text-blue-700', icon: '✓' },
};

type Props = {
  reco: RecoCardData;
  onAccept?: (id: string) => void;
  onPostpone?: (id: string) => void;
  onReject?: (id: string) => void;
};

export default function RecoCard({ reco, onAccept, onPostpone, onReject }: Props) {
  const meta = ACTION_META[reco.action];
  return (
    <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden flex flex-col md:flex-row">
      {/* Photo */}
      <div className="md:w-1/3 aspect-square md:aspect-auto bg-gray-100 flex-shrink-0">
        {reco.product_thumb ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={reco.product_thumb} alt={reco.product_name} className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-5xl text-gray-300">👗</div>
        )}
      </div>

      {/* Body */}
      <div className="p-4 flex-1 flex flex-col">
        <div className="flex items-start justify-between gap-2 mb-2">
          <div>
            <h3 className="font-medium text-black text-base leading-tight">
              {reco.product_name}
            </h3>
            <div className="text-xs text-gray-500 mt-0.5">
              {typeof reco.score === 'number' && <>Score {reco.score.toFixed(0)}/100</>}
              {typeof reco.days_on_shelf === 'number' && (
                <> · En rayon depuis {reco.days_on_shelf}j</>
              )}
            </div>
          </div>
        </div>

        <div className={`inline-flex items-center gap-1 self-start px-2 py-1 rounded-full text-xs font-medium ${meta.color} mb-3`}>
          <span>{meta.icon}</span>
          <span>{meta.label}</span>
        </div>

        {reco.reasons.length > 0 && (
          <ul className="text-sm text-gray-700 space-y-1 mb-3">
            {reco.reasons.map((r, i) => (
              <li key={i} className="flex gap-1.5">
                <span className="text-teal">•</span>
                <span>{r}</span>
              </li>
            ))}
          </ul>
        )}

        {reco.similar_products && reco.similar_products.length > 0 && (
          <div className="mb-3">
            <div className="text-[10px] text-gray-400 uppercase tracking-wider mb-1">Pièces similaires</div>
            <div className="flex gap-1.5">
              {reco.similar_products.slice(0, 3).map((s) => (
                <div key={s.id} className="w-12 h-12 rounded bg-gray-100 overflow-hidden">
                  {s.thumb ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={s.thumb} alt={s.name} className="w-full h-full object-cover" />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-lg">👕</div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="flex gap-2 mt-auto pt-2 border-t border-gray-100">
          <button
            onClick={() => onAccept?.(reco.product_id)}
            disabled={!onAccept}
            className="flex-1 text-xs px-3 py-2 bg-teal text-white rounded-lg hover:bg-teal/90 min-h-0"
          >
            Accepter
          </button>
          <button
            onClick={() => onPostpone?.(reco.product_id)}
            disabled={!onPostpone}
            className="text-xs px-3 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 min-h-0"
          >
            Reporter 7j
          </button>
          <button
            onClick={() => onReject?.(reco.product_id)}
            disabled={!onReject}
            className="text-xs px-3 py-2 bg-red-50 text-red-600 rounded-lg hover:bg-red-100 min-h-0"
          >
            Pourquoi pas
          </button>
        </div>
      </div>
    </div>
  );
}
