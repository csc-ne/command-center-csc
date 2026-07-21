import { useEffect, useState } from 'react'
import { Link2, Shield, Trash2, Plus, X } from 'lucide-react'
import toast from 'react-hot-toast'

import Modal from './ui/Modal'
import Button from './ui/Button'
import { api, errMsg } from '@/api/client'
import { useAuth } from '@/context/AuthContext'

/**
 * Board settings modal: connections + permissions (admin only).
 */
export default function BoardSettings({ open, onClose, board, phases = [] }) {
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin'
  const [tab, setTab] = useState('connections')

  if (!isAdmin || !board) return null

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`Configuracoes: ${board.name}`}
      size="lg"
      footer={
        <Button variant="ghost" onClick={onClose}>Fechar</Button>
      }
    >
      <div className="mb-4 flex gap-1 rounded-lg bg-muted/50 p-1">
        <button
          type="button"
          onClick={() => setTab('connections')}
          className={`flex-1 flex items-center justify-center gap-1.5 py-2 text-sm font-medium rounded-lg cursor-pointer transition-colors ${
            tab === 'connections'
              ? 'bg-primary text-primary-foreground shadow-sm'
              : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
          }`}
        >
          <Link2 className="h-4 w-4" /> Conexoes
        </button>
        <button
          type="button"
          onClick={() => setTab('permissions')}
          className={`flex-1 flex items-center justify-center gap-1.5 py-2 text-sm font-medium rounded-lg cursor-pointer transition-colors ${
            tab === 'permissions'
              ? 'bg-primary text-primary-foreground shadow-sm'
              : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
          }`}
        >
          <Shield className="h-4 w-4" /> Permissoes
        </button>
      </div>

      {tab === 'connections' && (
        <ConnectionsTab board={board} phases={phases} />
      )}
      {tab === 'permissions' && (
        <PermissionsTab board={board} />
      )}
    </Modal>
  )
}

// ---------- Connections Tab ----------

function ConnectionsTab({ board, phases }) {
  const [connections, setConnections] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [boards, setBoards] = useState([])
  const [targetPhases, setTargetPhases] = useState([])

  const [form, setForm] = useState({
    target_board_id: '',
    trigger_phase_id: '',
    target_phase_id: '',
    completion_phase_id: '',
    advance_to_phase_id: '',
  })
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    fetchConnections()
    api.get('/boards?include_archived=true').then(({ data }) =>
      setBoards(data.filter((b) => b.id !== board.id))
    ).catch(() => {})
  }, [board.id])

  async function fetchConnections() {
    setLoading(true)
    try {
      const { data } = await api.get(`/boards/${board.id}/connections`)
      setConnections(data)
    } catch (err) {
      toast.error(errMsg(err))
    } finally {
      setLoading(false)
    }
  }

  // When target board changes, fetch its phases
  useEffect(() => {
    if (form.target_board_id) {
      api.get(`/boards/${form.target_board_id}`).then(({ data }) => {
        const sorted = [...(data.phases || [])].sort((a, b) => a.position - b.position)
        setTargetPhases(sorted)
      }).catch(() => setTargetPhases([]))
    } else {
      setTargetPhases([])
    }
  }, [form.target_board_id])

  async function handleCreate() {
    if (!form.target_board_id || !form.trigger_phase_id || !form.target_phase_id ||
        !form.completion_phase_id || !form.advance_to_phase_id) {
      toast.error('Preencha todos os campos')
      return
    }
    setSaving(true)
    try {
      await api.post(`/boards/${board.id}/connections`, {
        source_board_id: board.id,
        ...form,
      })
      toast.success('Conexao criada')
      setShowForm(false)
      setForm({ target_board_id: '', trigger_phase_id: '', target_phase_id: '', completion_phase_id: '', advance_to_phase_id: '' })
      fetchConnections()
    } catch (err) {
      toast.error(errMsg(err))
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete(id) {
    if (!confirm('Remover esta conexao?')) return
    try {
      await api.delete(`/connections/${id}`)
      toast.success('Conexao removida')
      fetchConnections()
    } catch (err) {
      toast.error(errMsg(err))
    }
  }

  if (loading) return <div className="text-center py-4 text-sm text-muted-foreground">Carregando...</div>

  return (
    <div>
      <p className="text-xs text-muted-foreground mb-3">
        Defina quais fluxos se comunicam. Quando um card chegar na fase gatilho, um card filho sera criado no fluxo destino.
      </p>

      {connections.length === 0 && !showForm && (
        <div className="py-6 text-center text-sm text-muted-foreground">
          Nenhuma conexao configurada.
        </div>
      )}

      {connections.map((c) => (
        <div key={c.id} className="mb-2 rounded-md border border-border p-3 text-sm">
          <div className="flex items-start justify-between">
            <div>
              <div className="font-medium">{c.source_board_name} → {c.target_board_name}</div>
              <div className="text-xs text-muted-foreground mt-1 space-y-0.5">
                <div>Gatilho: <strong>{c.trigger_phase_name}</strong></div>
                <div>Destino: <strong>{c.target_phase_name}</strong></div>
                <div>Conclusao: <strong>{c.completion_phase_name}</strong></div>
                <div>Avanca para: <strong>{c.advance_to_phase_name}</strong></div>
              </div>
            </div>
            <button onClick={() => handleDelete(c.id)}
              className="rounded p-1 text-destructive hover:bg-destructive/10 cursor-pointer">
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        </div>
      ))}

      {showForm ? (
        <div className="rounded-md border border-primary/30 bg-primary/5 p-3 space-y-3 mt-2">
          <div>
            <label className="text-xs font-medium mb-1 block">Fluxo destino</label>
            <select value={form.target_board_id}
              onChange={(e) => setForm((f) => ({ ...f, target_board_id: e.target.value, target_phase_id: '', completion_phase_id: '' }))}
              className="w-full rounded border border-border bg-surface px-2 py-1.5 text-sm">
              <option value="">Selecione...</option>
              {boards.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-xs font-medium mb-1 block">Fase gatilho (neste fluxo)</label>
              <select value={form.trigger_phase_id}
                onChange={(e) => setForm((f) => ({ ...f, trigger_phase_id: e.target.value }))}
                className="w-full rounded border border-border bg-surface px-2 py-1.5 text-sm">
                <option value="">Selecione...</option>
                {phases.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-medium mb-1 block">Avanca para (neste fluxo)</label>
              <select value={form.advance_to_phase_id}
                onChange={(e) => setForm((f) => ({ ...f, advance_to_phase_id: e.target.value }))}
                className="w-full rounded border border-border bg-surface px-2 py-1.5 text-sm">
                <option value="">Selecione...</option>
                {phases.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-xs font-medium mb-1 block">Fase destino (fluxo destino)</label>
              <select value={form.target_phase_id}
                onChange={(e) => setForm((f) => ({ ...f, target_phase_id: e.target.value }))}
                className="w-full rounded border border-border bg-surface px-2 py-1.5 text-sm"
                disabled={!form.target_board_id}>
                <option value="">Selecione...</option>
                {targetPhases.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-medium mb-1 block">Fase conclusao (fluxo destino)</label>
              <select value={form.completion_phase_id}
                onChange={(e) => setForm((f) => ({ ...f, completion_phase_id: e.target.value }))}
                className="w-full rounded border border-border bg-surface px-2 py-1.5 text-sm"
                disabled={!form.target_board_id}>
                <option value="">Selecione...</option>
                {targetPhases.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </div>
          </div>

          <div className="flex gap-2 justify-end">
            <Button variant="ghost" size="sm" onClick={() => setShowForm(false)}>Cancelar</Button>
            <Button size="sm" onClick={handleCreate} loading={saving}>Criar conexao</Button>
          </div>
        </div>
      ) : (
        <Button variant="secondary" size="sm" className="mt-2 w-full" onClick={() => setShowForm(true)}>
          <Plus className="h-4 w-4" /> Nova conexao
        </Button>
      )}
    </div>
  )
}

// ---------- Permissions Tab ----------

function PermissionsTab({ board }) {
  const [users, setUsers] = useState([])
  const [permittedIds, setPermittedIds] = useState(new Set())
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    Promise.all([
      api.get('/users'),
      api.get(`/boards/${board.id}/permissions`),
    ]).then(([usersRes, permsRes]) => {
      setUsers(usersRes.data)
      setPermittedIds(new Set(permsRes.data.user_ids))
    }).catch((err) => toast.error(errMsg(err)))
      .finally(() => setLoading(false))
  }, [board.id])

  function toggle(userId) {
    setPermittedIds((prev) => {
      const next = new Set(prev)
      if (next.has(userId)) next.delete(userId)
      else next.add(userId)
      return next
    })
  }

  async function handleSave() {
    setSaving(true)
    try {
      await api.put(`/boards/${board.id}/permissions`, {
        user_ids: Array.from(permittedIds),
      })
      toast.success('Permissoes salvas')
    } catch (err) {
      toast.error(errMsg(err))
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <div className="text-center py-4 text-sm text-muted-foreground">Carregando...</div>

  return (
    <div>
      <p className="text-xs text-muted-foreground mb-3">
        Selecione quais usuarios podem ver este fluxo. Se nenhum for selecionado, todos terao acesso. Admins sempre tem acesso.
      </p>

      <div className="max-h-64 overflow-y-auto space-y-1 mb-4">
        {users.filter((u) => u.role !== 'admin').map((u) => (
          <label key={u.id}
            className="flex items-center gap-3 rounded-md px-3 py-2 hover:bg-muted/30 transition-colors cursor-pointer">
            <input
              type="checkbox"
              checked={permittedIds.has(u.id)}
              onChange={() => toggle(u.id)}
              className="h-4 w-4 rounded border-border text-primary cursor-pointer"
            />
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium truncate">{u.full_name}</div>
              <div className="text-xs text-muted-foreground">{u.email} — {u.role}</div>
            </div>
          </label>
        ))}
      </div>

      <div className="flex items-center justify-between">
        <span className="text-xs text-muted-foreground">
          {permittedIds.size === 0 ? 'Aberto para todos' : `${permittedIds.size} usuario(s) selecionado(s)`}
        </span>
        <Button size="sm" onClick={handleSave} loading={saving}>
          Salvar permissoes
        </Button>
      </div>
    </div>
  )
}
