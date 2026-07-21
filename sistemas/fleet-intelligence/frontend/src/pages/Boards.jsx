import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { FlaskConical, Plus, Workflow, Archive } from 'lucide-react'
import toast from 'react-hot-toast'

import { api, errMsg } from '@/api/client'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import Modal from '@/components/ui/Modal'
import { useAuth } from '@/context/AuthContext'

const BOARD_COLORS = [
  { id: 'indigo', cls: 'bg-indigo-500' },
  { id: 'blue', cls: 'bg-blue-500' },
  { id: 'emerald', cls: 'bg-emerald-500' },
  { id: 'amber', cls: 'bg-amber-500' },
  { id: 'rose', cls: 'bg-rose-500' },
  { id: 'violet', cls: 'bg-violet-500' },
  { id: 'slate', cls: 'bg-slate-500' },
]

function colorCls(id) {
  return BOARD_COLORS.find((c) => c.id === id)?.cls || 'bg-indigo-500'
}

export default function BoardsPage() {
  const { user: currentUser } = useAuth()
  const isAdmin = currentUser?.role === 'admin'

  const [boards, setBoards] = useState([])
  const [loading, setLoading] = useState(true)
  const [modalOpen, setModalOpen] = useState(false)
  const [creating, setCreating] = useState(false)
  const [seedingDemo, setSeedingDemo] = useState(false)
  const [form, setForm] = useState({ name: '', description: '', color: 'indigo' })

  async function fetchBoards() {
    setLoading(true)
    try {
      const { data } = await api.get('/boards')
      setBoards(data)
    } catch (err) {
      toast.error(errMsg(err, 'Erro ao carregar fluxos'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchBoards()
  }, [])

  async function handleCreate(e) {
    e.preventDefault()
    if (!form.name.trim()) return
    setCreating(true)
    try {
      const { data } = await api.post('/boards', form)
      await Promise.all([
        api.post(`/boards/${data.id}/phases`, { name: 'A Fazer', color: 'slate', position: 0 }),
        api.post(`/boards/${data.id}/phases`, { name: 'Em Andamento', color: 'amber', position: 1 }),
        api.post(`/boards/${data.id}/phases`, { name: 'Concluido', color: 'emerald', position: 2 }),
      ])
      toast.success('Fluxo criado')
      setModalOpen(false)
      setForm({ name: '', description: '', color: 'indigo' })
      fetchBoards()
    } catch (err) {
      toast.error(errMsg(err, 'Nao foi possivel criar o fluxo'))
    } finally {
      setCreating(false)
    }
  }

  async function handleSeedDemo() {
    setSeedingDemo(true)
    try {
      const { data } = await api.post('/boards/seed-demo')
      if (data.created) {
        toast.success('Fluxos de demonstracao criados! Fluxo Principal + Subfluxo - Documentacao.')
      } else {
        toast('Os fluxos de demonstracao ja existem.', { icon: 'ℹ️' })
      }
      fetchBoards()
    } catch (err) {
      toast.error(errMsg(err, 'Erro ao criar fluxos demo'))
    } finally {
      setSeedingDemo(false)
    }
  }

  return (
    <div className="mx-auto max-w-6xl">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Fluxos de trabalho</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Organize o trabalho por responsabilidade e prioridade.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {isAdmin && (
            <Button
              variant="secondary"
              onClick={handleSeedDemo}
              loading={seedingDemo}
              title="Cria o Fluxo Principal + Subfluxo de Documentacao para demonstracao"
            >
              <FlaskConical className="h-4 w-4" />
              Setup Demo
            </Button>
          )}
          <Button onClick={() => setModalOpen(true)}>
            <Plus className="h-4 w-4" />
            Novo fluxo
          </Button>
        </div>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[...Array(3)].map((_, i) => (
            <div
              key={i}
              className="h-32 animate-pulse rounded-lg border border-border bg-surface-muted"
            />
          ))}
        </div>
      ) : boards.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border bg-surface py-16 text-center">
          <Workflow className="mb-3 h-10 w-10 text-muted-foreground" />
          <h3 className="text-lg font-semibold">Nenhum fluxo ainda</h3>
          <p className="mt-1 max-w-sm text-sm text-muted-foreground">
            Crie seu primeiro fluxo para comecar a organizar tarefas em fases.
          </p>
          <div className="mt-4 flex gap-2">
            {isAdmin && (
              <Button variant="secondary" onClick={handleSeedDemo} loading={seedingDemo}>
                <FlaskConical className="h-4 w-4" />
                Setup Demo
              </Button>
            )}
            <Button onClick={() => setModalOpen(true)}>
              <Plus className="h-4 w-4" />
              Criar fluxo
            </Button>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {boards.map((b) => (
            <Link
              key={b.id}
              to={`/boards/${b.id}`}
              className="group rounded-lg border border-border bg-surface p-5 shadow-card transition-all hover:shadow-card-hover hover:-translate-y-0.5"
            >
              <div className="flex items-start gap-3">
                <div className={`h-10 w-10 shrink-0 rounded-lg ${colorCls(b.color)} flex items-center justify-center text-white shadow-sm`}>
                  <Workflow className="h-5 w-5" />
                </div>
                <div className="min-w-0 flex-1">
                  <h3 className="truncate text-base font-semibold group-hover:text-primary transition-colors">
                    {b.name}
                  </h3>
                  {b.description && (
                    <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">
                      {b.description}
                    </p>
                  )}
                </div>
                {b.is_archived && (
                  <Archive className="h-4 w-4 text-muted-foreground" aria-label="Arquivado" />
                )}
              </div>
            </Link>
          ))}
        </div>
      )}

      <Modal
        open={modalOpen}
        onClose={() => !creating && setModalOpen(false)}
        title="Novo fluxo"
        footer={
          <>
            <Button variant="ghost" onClick={() => setModalOpen(false)} disabled={creating}>
              Cancelar
            </Button>
            <Button onClick={handleCreate} loading={creating} type="submit" form="create-board-form">
              Criar fluxo
            </Button>
          </>
        }
      >
        <form id="create-board-form" onSubmit={handleCreate} className="space-y-4">
          <div>
            <label htmlFor="b-name" className="mb-1.5 block text-sm font-medium">
              Nome
            </label>
            <Input
              id="b-name"
              autoFocus
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              placeholder="Ex.: Revisoes de equipamento"
              required
            />
          </div>
          <div>
            <label htmlFor="b-desc" className="mb-1.5 block text-sm font-medium">
              Descricao <span className="text-muted-foreground font-normal">(opcional)</span>
            </label>
            <textarea
              id="b-desc"
              rows={3}
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              className="flex w-full rounded-md border border-border bg-surface px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:border-transparent transition-colors resize-none"
              placeholder="Para que serve este fluxo?"
            />
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium">Cor</label>
            <div className="flex flex-wrap gap-2">
              {BOARD_COLORS.map((c) => (
                <button
                  key={c.id}
                  type="button"
                  onClick={() => setForm((f) => ({ ...f, color: c.id }))}
                  aria-label={c.id}
                  className={`h-8 w-8 rounded-full ${c.cls} transition-all cursor-pointer ${
                    form.color === c.id
                      ? 'ring-2 ring-ring ring-offset-2 ring-offset-surface scale-110'
                      : 'opacity-75 hover:opacity-100'
                  }`}
                />
              ))}
            </div>
          </div>
        </form>
      </Modal>
    </div>
  )
}
