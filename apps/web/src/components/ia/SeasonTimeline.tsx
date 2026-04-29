'use client';

import React from 'react';

const MONTHS = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Juin', 'Juil', 'Août', 'Sep', 'Oct', 'Nov', 'Déc'];

type CategoryCalendar = Record<string, number[]>;

type Props = {
  /** Map of category → months[] (1-12) where the category is in season. */
  categoryCalendar: CategoryCalendar;
  /** Optional in-stock count by category for "alert" indicator. */
  stockByCategory?: Record<string, number>;
  /** Highlighted month (1-12). Defaults to current month. */
  currentMonth?: number;
};

export default function SeasonTimeline({
  categoryCalendar,
  stockByCategory = {},
  currentMonth,
}: Props) {
  const cur = currentMonth ?? new Date().getMonth() + 1;
  const categories = Object.keys(categoryCalendar);
  if (categories.length === 0) {
    return <p className="text-sm text-gray-400">Aucune catégorie configurée. Voir Settings → Scoring IA.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-gray-200">
            <th className="text-left py-2 pr-3 text-gray-500 font-medium">Catégorie</th>
            {MONTHS.map((m, i) => (
              <th
                key={m}
                className={`py-2 px-1.5 text-center text-gray-500 font-medium ${
                  i + 1 === cur ? 'bg-vz-teal-soft text-vz-teal' : ''
                }`}
              >
                {m}
              </th>
            ))}
            <th className="py-2 pl-3 text-right text-gray-500 font-medium">Stock</th>
          </tr>
        </thead>
        <tbody>
          {categories.map((cat) => {
            const months = categoryCalendar[cat] || [];
            const inSeason = months.includes(cur);
            // Alert : end-of-season warning if season ends in ≤ 4 weeks.
            const seasonEnd = months.length > 0 ? Math.max(...months) : null;
            const monthsUntilEnd = seasonEnd ? (seasonEnd - cur + 12) % 12 : null;
            const stock = stockByCategory[cat] || 0;
            const alert = inSeason && monthsUntilEnd !== null && monthsUntilEnd <= 1 && stock > 5;

            return (
              <tr key={cat} className="border-b border-gray-100">
                <td className="py-2 pr-3 font-medium text-black">{cat}</td>
                {MONTHS.map((_, i) => {
                  const month = i + 1;
                  const active = months.includes(month);
                  const isCur = month === cur;
                  return (
                    <td key={i} className="py-2 px-1 text-center">
                      <div
                        className={`mx-auto h-3 w-3 rounded-full ${
                          active
                            ? isCur
                              ? 'bg-vz-teal ring-2 ring-vz-teal/30'
                              : 'bg-vz-teal/60'
                            : 'bg-gray-100'
                        }`}
                      />
                    </td>
                  );
                })}
                <td className={`py-2 pl-3 text-right tabular-nums ${alert ? 'text-red-600 font-bold' : 'text-gray-600'}`}>
                  {stock}
                  {alert && <span className="ml-1">⚠</span>}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="text-[10px] text-gray-400 mt-2">
        ⚠ = catégorie en stock à 4 semaines de la fin de saison — pensez à démarquer ou retourner.
      </p>
    </div>
  );
}
