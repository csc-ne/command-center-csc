import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertTriangle, Bell, Calendar, Clock, Flag, ArrowRight } from 'lucide-react'
import toast from 'react-hot-toast'

import { api, errMsg } from '@/api/client'
import Button from '@/components/ui/Button'
import { cn, PRIORITY_LABEL, PRIORITY_STYLES, formatShortDate } from '@/lib/utils'

function formatDaysLeft(dueDateStr) {
  const due = new Date(dueDateStr)
  const now = new Date()
  const diffMs = due - now
  const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24))

  if (diffDays < 0) return `${Math.abs(diffDays)} dia${Math.abs(diffDays) !== 1 ? 's' : ''} atrasado`
  if (diffDays === 0) return 'Vence hoje'
  if (diffDays === 1) return 'Vence amanha'
  return `Vence em ${diffDays} dias`
}

export default function AlertsPage() {
  const navigate = useNavigate()
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(true)
  const [days, setDays] = useState(7)

  useEffect(() => {
    document.title = 'Alertas - Fleet Intelligence'
  }, [])

  useEffect(() => {
    fetchAlerts()
  }, [days])

  async function fetchAlerts() {
    setLoading(true)
    try {
      const { data } = await api.get(`/alerts/due-soon?days=${days}`)
      setAlerts(data)
    } catch (err) {
      toast.error(errMsg(err))
    } finally {
      setLoading(false)
    }
  }

  function goToCard(alert) {
    navigate(`/boards/${alert.board_id}?highlight=${alert.id}`)
  }

  // Group by board
  const grouped = {}
  for (const a of alerts) {
    if (!grouped[a.board_id]) {
      grouped[a.board_id] = { board_name: a.board_name, items: [] }
    }
    grouped[a.board_id].items.push(a)
  }

  const overdue = alerts.filter((a) => a.is_overdue)
  const upcoming = alerts.filter((a) => !a.is_overdue)

  if (loading) {
    return (
      <div className="flex h-[60vh] items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    )
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Bell className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight">Alertas</h1>
            <p className="text-sm text-muted-foreground">
              {alerts.length} card{alerts.length !== 1 ? 's' : ''} com data limite proxima
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Periodo:</span>
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="rounded-md border border-border bg-surface px-3 py-1.5 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring cursor-pointer"
          >
            <option value={3}>3 dias</option>
            <option value={7}>7 dias</option>
            <option value={14}>14 dias</option>
            <option value={30}>30 dias</option>
          </select>
        </div>
      </div>

      {alerts.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-green-100 text-green-600 mb-4 dark:bg-green-950 dark:text-green-400">
            <Bell className="h-8 w-8" />
          </div>
          <h3 className="text-lg font-semibold mb-1">Tudo em dia!</h3>
          <p className="text-sm text-muted-foreground">
            Nenhum card com vencimento nos proximos {days} dias.
          </p>
        </div>
      )}

      {/* Overdue section */}
      {overdue.length > 0 && (
        <div className="mb-6">
          <div className="mb-3 flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-destructive" />
            <h2 className="font-semibold text-destructive">{overdue.length} atrasado{overdue.length !== 1 ? 's' : ''}</h2>
          </div>
          <div className="space-y-2">
            {overdue.map((a) => (
              <AlertCard key={a.id} alert={a} onClick={() => goToCard(a)} />
            ))}
          </div>
        </div>
      )}

      {/* Upcoming section */}
      {upcoming.length > 0 && (
        <div>
          <div className="mb-3 flex items-center gap-2">
            <Clock className="h-4 w-4 text-amber-500" />
            <h2 className="font-semibold text-foreground">{upcoming.length} proximo{upcoming.length !== 1 ? 's' : ''} do vencimento</h2>
          </div>
          <div className="space-y-2">
            {upcoming.map((a) => (
              <AlertCard key={a.id} alert={a} onClick={() => goToCard(a)} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function AlertCard({ alert, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'w-full rounded-lg border bg-surface p-4 text-left transition-all hover:shadow-card-hover cursor-pointer',
        alert.is_overdue
          ? 'border-destructive/30 hover:border-destructive/50'
          : 'border-border hover:border-primary/30',
      )}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <h3 className="font-medium text-foreground truncate">{alert.title}</h3>
          {alert.description && (
            <p className="mt-0.5 text-xs text-muted-foreground line-clamp-1">{alert.description}</p>
          )}
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1 rounded bg-muted px-2 py-0.5 text-xs text-muted-foreground">
              <ArrowRight className="h-3 w-3" />
              {alert.board_name} &middot; {alert.phase_name}
            </span>
            <span
              className={cn(
                'inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium',
                PRIORITY_STYLES[alert.priority],
              )}
            >
              <Flag className="h-3 w-3" />
              {PRIORITY_LABEL[alert.priority]}
            </span>
            {alert.tags?.slice(0, 2).map((t) => (
              <span key={t} className="rounded bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary">
                {t}
              </span>
            ))}
          </div>
        </div>
        <div className="shrink-0 text-right">
          <div className={cn(
            'text-xs font-medium',
            alert.is_overdue ? 'text-destructive' : 'text-amber-600 dark:text-amber-400'
          )}>
            {formatDaysLeft(alert.due_date)}
          </div>
          <div className="mt-0.5 text-[11px] text-muted-foreground">
            <Calendar className="inline h-3 w-3 mr-0.5" />
            {formatShortDate(alert.due_date)}
          </div>
        </div>
      </div>
    </button>
  )
}
