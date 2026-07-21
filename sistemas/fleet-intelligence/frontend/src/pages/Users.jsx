import { useEffect, useState } from 'react'
import { Activity, ChevronDown, ChevronUp, Clock, Shield, ShieldCheck, Eye, Users as UsersIcon } from 'lucide-react'
import toast from 'react-hot-toast'

import { api, errMsg } from '@/api/client'
import { useAuth } from '@/context/AuthContext'
import Modal from '@/components/ui/Modal'
import Button from '@/components/ui/Button'
import { cn } from '@/lib/utils'

const ROLE_CONFIG = {
  admin: { label: 'Admin', icon: ShieldCheck, color: 'text-primary bg-primary/10' },
  operator: { label: 'Operador', icon: Shield, color: 'text-amber-600 bg-amber-50 dark:text-amber-400 dark:bg-amber-950' },
  viewer: { label: 'Visualizador', icon: Eye, color: 'text-slate-500 bg-slate-100 dark:text-slate-400 dark:bg-slate-800' },
}

const ACTION_LABELS = {
  create_board: 'Criou fluxo',
  update_board: 'Atualizou fluxo',
  delete_board: 'Excluiu fluxo',
  create_phase: 'Criou fase',
  update_phase: 'Atualizou fase',
  delete_phase: 'Excluiu fase',
  create_card: 'Criou card',
  update_card: 'Atualizou card',
  delete_card: 'Excluiu card',
  move_card: 'Moveu card',
  create_user: 'Criou usuario',
  update_user: 'Atualizou usuario',
  delete_user: 'Excluiu usuario',
}

function formatDateTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleString('pt-BR', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

function UserInitials({ name, size = 'md' }) {
  const initials = (name || '?')
    .split(' ')
    .map((s) => s[0])
    .filter(Boolean)
    .slice(0, 2)
    .join('')
    .toUpperCase()

  const sizes = {
    sm: 'h-8 w-8 text-xs',
    md: 'h-10 w-10 text-sm',
    lg: 'h-14 w-14 text-lg',
  }

  return (
    <div className={cn('flex items-center justify-center rounded-full bg-primary/15 text-primary font-semibold', sizes[size])}>
      {initials}
    </div>
  )
}

export default function UsersPage() {
  const { user: currentUser } = useAuth()
  const isAdmin = currentUser?.role === 'admin'

  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)

  // Activity log modal
  const [logUser, setLogUser] = useState(null)
  const [logs, setLogs] = useState([])
  const [logsLoading, setLogsLoading] = useState(false)

  useEffect(() => {
    document.title = 'Usuarios - Fleet Intelligence'
    fetchUsers()
  }, [])

  async function fetchUsers() {
    setLoading(true)
    try {
      const { data } = await api.get('/users')
      setUsers(data)
    } catch (err) {
      toast.error(errMsg(err))
    } finally {
      setLoading(false)
    }
  }

  async function openActivityLog(user) {
    setLogUser(user)
    setLogsLoading(true)
    setLogs([])
    try {
      const { data } = await api.get(`/activity-logs?user_id=${user.id}&limit=100`)
      setLogs(data)
    } catch (err) {
      toast.error(errMsg(err, 'Erro ao carregar logs'))
    } finally {
      setLogsLoading(false)
    }
  }

  // Sort: admins first, then operators, then viewers
  const sortedUsers = [...users].sort((a, b) => {
    const order = { admin: 0, operator: 1, viewer: 2 }
    return (order[a.role] ?? 9) - (order[b.role] ?? 9)
  })

  if (loading) {
    return (
      <div className="flex h-[60vh] items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    )
  }

  return (
    <div>
      <div className="mb-6 flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <UsersIcon className="h-5 w-5" />
        </div>
        <div>
          <h1 className="text-xl font-bold tracking-tight">Usuarios</h1>
          <p className="text-sm text-muted-foreground">{users.length} usuarios cadastrados</p>
        </div>
      </div>

      <div className="rounded-xl border border-border bg-surface overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/30">
              <th className="px-4 py-3 text-left font-medium text-muted-foreground">Usuario</th>
              <th className="px-4 py-3 text-left font-medium text-muted-foreground">Email</th>
              <th className="px-4 py-3 text-left font-medium text-muted-foreground">Nivel</th>
              <th className="px-4 py-3 text-left font-medium text-muted-foreground">Cadastro</th>
              {isAdmin && <th className="px-4 py-3 text-right font-medium text-muted-foreground">Acoes</th>}
            </tr>
          </thead>
          <tbody>
            {sortedUsers.map((u) => {
              const role = ROLE_CONFIG[u.role] || ROLE_CONFIG.viewer
              const RoleIcon = role.icon
              return (
                <tr key={u.id} className="border-b border-border/50 last:border-0 hover:bg-muted/20 transition-colors">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <UserInitials name={u.full_name} size="sm" />
                      <div>
                        <div className="font-medium text-foreground">{u.full_name}</div>
                        <div className="text-xs text-muted-foreground">@{u.username}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">{u.email}</td>
                  <td className="px-4 py-3">
                    <span className={cn('inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium', role.color)}>
                      <RoleIcon className="h-3.5 w-3.5" />
                      {role.label}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground text-xs">
                    {formatDateTime(u.created_at)}
                  </td>
                  {isAdmin && (
                    <td className="px-4 py-3 text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => openActivityLog(u)}
                        title="Ver log de atividades"
                      >
                        <Activity className="h-4 w-4" />
                        Log
                      </Button>
                    </td>
                  )}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Activity Log Modal */}
      <Modal
        open={Boolean(logUser)}
        onClose={() => setLogUser(null)}
        title={logUser ? `Atividades de ${logUser.full_name}` : ''}
        size="lg"
        footer={
          <Button variant="ghost" onClick={() => setLogUser(null)}>
            Fechar
          </Button>
        }
      >
        {logsLoading ? (
          <div className="flex items-center justify-center py-8">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          </div>
        ) : logs.length === 0 ? (
          <div className="py-8 text-center text-sm text-muted-foreground">
            Nenhuma atividade registrada.
          </div>
        ) : (
          <div className="max-h-[60vh] overflow-y-auto space-y-1">
            {logs.map((log) => {
              const label = ACTION_LABELS[log.action] || log.action
              const detail = log.details?.title || log.details?.name || log.details?.username || ''
              return (
                <div
                  key={log.id}
                  className="flex items-start gap-3 rounded-md px-3 py-2 hover:bg-muted/30 transition-colors"
                >
                  <div className="mt-0.5 flex h-6 w-6 items-center justify-center rounded-full bg-muted text-muted-foreground">
                    <Clock className="h-3.5 w-3.5" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm">
                      <span className="font-medium text-foreground">{label}</span>
                      {detail && (
                        <span className="text-muted-foreground"> — {detail}</span>
                      )}
                    </div>
                    <div className="text-xs text-muted-foreground mt-0.5">
                      {formatDateTime(log.created_at)}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </Modal>
    </div>
  )
}
