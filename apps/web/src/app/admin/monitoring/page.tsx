'use client'

import { useEffect, useState, useCallback } from 'react'
import { api } from '@/lib/api'

interface ServiceStatus {
  name: string
  healthy: boolean
  latency_ms: number | null
  detail: string
  checked_at: string
}

interface MonitoringReport {
  all_healthy: boolean
  checked_at: string
  services: ServiceStatus[]
}

const SERVICE_LABELS: Record<string, string> = {
  db: 'PostgreSQL',
  pennylane: 'Pennylane',
  sumup: 'SumUp',
  brevo: 'Brevo',
  api: 'API Vintiz',
}

function StatusBadge({ healthy }: { healthy: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${
        healthy ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
      }`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${healthy ? 'bg-green-500' : 'bg-red-500'}`} />
      {healthy ? 'OK' : 'KO'}
    </span>
  )
}

export default function MonitoringPage() {
  const [report, setReport] = useState<MonitoringReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [refreshing, setRefreshing] = useState(false)

  const fetchStatus = useCallback(async (showSpinner = false) => {
    if (showSpinner) setRefreshing(true)
    try {
      const data: MonitoringReport = await api.get('/api/admin/monitoring').then(r => r.json())
      setReport(data)
      setError('')
    } catch {
      setError('Impossible de récupérer le statut des services')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    fetchStatus()
    const interval = setInterval(() => fetchStatus(), 60_000)
    return () => clearInterval(interval)
  }, [fetchStatus])

  const allHealthy = report?.all_healthy ?? true

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="flex items-start justify-between mb-6 gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-display font-semibold text-vz-ink">Monitoring</h1>
          <p className="text-sm text-vz-ink-mute mt-1">
            Santé des services externes · rafraîchissement auto toutes les 60 s
          </p>
        </div>
        <button
          onClick={() => fetchStatus(true)}
          disabled={refreshing || loading}
          className="flex items-center gap-2 px-4 py-2 border border-vz-line rounded-lg text-sm font-medium text-vz-ink-soft hover:bg-vz-bg disabled:opacity-50 transition-colors"
        >
          <svg
            className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`}
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            viewBox="0 0 24 24"
          >
            <polyline points="23 4 23 10 17 10" />
            <polyline points="1 20 1 14 7 14" />
            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
          </svg>
          Actualiser
        </button>
      </div>

      {loading && <div className="text-vz-ink-mute text-sm">Chargement…</div>}

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 text-sm">{error}</div>
      )}

      {report && (
        <>
          {/* Bandeau statut global */}
          <div
            className={`rounded-xl p-4 mb-6 flex items-center gap-3 ${
              allHealthy ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'
            }`}
          >
            <div
              className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 ${
                allHealthy ? 'bg-green-100' : 'bg-red-100'
              }`}
            >
              {allHealthy ? (
                <svg className="w-5 h-5 text-green-600" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              ) : (
                <svg className="w-5 h-5 text-red-600" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              )}
            </div>
            <div>
              <p className={`font-semibold ${allHealthy ? 'text-green-800' : 'text-red-800'}`}>
                {allHealthy ? 'Tous les services sont opérationnels' : 'Un ou plusieurs services sont en erreur'}
              </p>
              <p className={`text-xs mt-0.5 ${allHealthy ? 'text-green-600' : 'text-red-600'}`}>
                Dernière vérification : {new Date(report.checked_at).toLocaleString('fr-FR')}
              </p>
            </div>
          </div>

          {/* Cartes services */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {report.services.map(svc => (
              <div
                key={svc.name}
                className={`bg-vz-surface border rounded-xl p-5 ${
                  svc.healthy ? 'border-vz-line' : 'border-red-200'
                }`}
              >
                <div className="flex items-center justify-between mb-3">
                  <h3 className="font-semibold text-vz-ink">{SERVICE_LABELS[svc.name] ?? svc.name}</h3>
                  <StatusBadge healthy={svc.healthy} />
                </div>
                <div className="space-y-1">
                  <p className="text-sm text-vz-ink-soft">{svc.detail || '—'}</p>
                  {svc.latency_ms !== null && svc.latency_ms > 0 && (
                    <p className="text-xs text-vz-ink-mute">Latence : {svc.latency_ms} ms</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
