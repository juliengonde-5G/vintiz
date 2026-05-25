'use client'

import { useEffect, useState } from 'react'
import { api } from '@/lib/api'

const MONTH_NAMES = [
  '', 'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
  'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre',
]

interface MonthStats {
  year: number
  month: number
  count: number
  net_ttc: number
  total_sales_ttc: number
  total_refunds_ttc: number
  total_tva: number
  cash_total: number
  card_total: number
  cheque_total: number
  transaction_count: number
  refund_count: number
}

function fmt(n: number) {
  return n.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

export default function MonthlyClosePage() {
  const [months, setMonths] = useState<MonthStats[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [downloading, setDownloading] = useState<string | null>(null)

  useEffect(() => {
    api.get('/api/accounting/monthly-close')
      .then(r => r.json())
      .then((data: MonthStats[]) => setMonths(data))
      .catch(() => setError('Impossible de charger les clôtures mensuelles'))
      .finally(() => setLoading(false))
  }, [])

  async function downloadFec(year: number, month: number) {
    const key = `${year}-${month}`
    setDownloading(key)
    try {
      const res = await api.get(`/api/accounting/monthly-close/${year}/${month}`)
      if (!res.ok) throw new Error('Erreur serveur')
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `FEC_Vintiz_${year}${String(month).padStart(2, '0')}.txt`
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      alert('Erreur lors du téléchargement du FEC')
    } finally {
      setDownloading(null)
    }
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-display font-semibold text-vz-ink">Clôtures mensuelles</h1>
        <p className="text-sm text-vz-ink-mute mt-1">FEC mensuel agrégé + statistiques par mois</p>
      </div>

      {loading && (
        <div className="text-vz-ink-mute text-sm">Chargement…</div>
      )}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 text-sm">{error}</div>
      )}

      {!loading && !error && months.length === 0 && (
        <div className="text-center py-16 text-vz-ink-mute">
          <p className="text-lg font-medium">Aucune clôture disponible</p>
          <p className="text-sm mt-1">Les clôtures apparaissent après chaque fermeture de caisse</p>
        </div>
      )}

      {months.length > 0 && (
        <div className="space-y-4">
          {months.map(m => {
            const key = `${m.year}-${m.month}`
            const isDownloading = downloading === key
            return (
              <div key={key} className="bg-vz-surface border border-vz-line rounded-xl p-5">
                <div className="flex items-start justify-between gap-4 flex-wrap">
                  <div>
                    <h2 className="text-lg font-semibold text-vz-ink">
                      {MONTH_NAMES[m.month]} {m.year}
                    </h2>
                    <p className="text-sm text-vz-ink-mute mt-0.5">
                      {m.count} clôture{m.count > 1 ? 's' : ''} · {m.transaction_count} vente{m.transaction_count > 1 ? 's' : ''}
                      {m.refund_count > 0 ? ` · ${m.refund_count} remboursement${m.refund_count > 1 ? 's' : ''}` : ''}
                    </p>
                  </div>
                  <button
                    onClick={() => downloadFec(m.year, m.month)}
                    disabled={isDownloading}
                    className="flex items-center gap-2 px-4 py-2 bg-vz-teal text-white rounded-lg text-sm font-medium hover:bg-vz-teal-deep disabled:opacity-50 transition-colors"
                  >
                    {isDownloading ? (
                      <>
                        <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                        </svg>
                        Génération…
                      </>
                    ) : (
                      <>
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                          <polyline points="7 10 12 15 17 10" />
                          <line x1="12" y1="15" x2="12" y2="3" />
                        </svg>
                        Télécharger FEC
                      </>
                    )}
                  </button>
                </div>

                <div className="mt-4 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
                  <Kpi label="CA net TTC" value={`${fmt(m.net_ttc)} €`} accent />
                  <Kpi label="Ventes TTC" value={`${fmt(m.total_sales_ttc)} €`} />
                  <Kpi label="Remboursements" value={`${fmt(m.total_refunds_ttc)} €`} />
                  <Kpi label="TVA collectée" value={`${fmt(m.total_tva)} €`} />
                  <Kpi label="Espèces" value={`${fmt(m.cash_total)} €`} />
                  <Kpi label="CB" value={`${fmt(m.card_total)} €`} />
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

function Kpi({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="bg-vz-bg rounded-lg p-3">
      <p className="text-xs text-vz-ink-mute">{label}</p>
      <p className={`text-sm font-semibold mt-0.5 ${accent ? 'text-vz-teal' : 'text-vz-ink'}`}>{value}</p>
    </div>
  )
}
