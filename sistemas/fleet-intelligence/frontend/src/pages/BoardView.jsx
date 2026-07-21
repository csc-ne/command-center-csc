import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  closestCorners,
  useSensor,
  useSensors,
} from '@dnd-kit/core'
import { arrayMove } from '@dnd-kit/sortable'
import { ArrowLeft, Plus, Settings } from 'lucide-react'
import toast from 'react-hot-toast'

import { api, errMsg } from '@/api/client'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import Modal from '@/components/ui/Modal'
import KanbanColumn from '@/components/KanbanColumn'
import KanbanCard from '@/components/KanbanCard'
import CardEditor from '@/components/CardEditor'
import BoardSettings from '@/components/BoardSettings'
import { useAuth } from '@/context/AuthContext'

export default function BoardView() {
  const { boardId } = useParams()
  const { user: currentUser } = useAuth()
  const isAdmin = currentUser?.role === 'admin'
  const [board, setBoard] = useState(null)
  const [loading, setLoading] = useState(true)

  const [phases, setPhases] = useState([])
  const [cardsByPhase, setCardsByPhase] = useState({})

  const [users, setUsers] = useState([])
  const [linkedCardIds, setLinkedCardIds] = useState(new Set())
  const [activeCard, setActiveCard] = useState(null)

  const [editorCard, setEditorCard] = useState(null)
  const [editorPhaseId, setEditorPhaseId] = useState(null)
  const [editorOpen, setEditorOpen] = useState(false)
  const [phaseModalOpen, setPhaseModalOpen] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [phaseName, setPhaseName] = useState('')
  const [creatingPhase, setCreatingPhase] = useState(false)

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
  )

  useEffect(() => {
    api.get('/users').then(({ data }) => setUsers(data)).catch(() => {})
  }, [])

  const fetchBoard = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await api.get(`/boards/${boardId}`)
      setBoard(data)
      const sortedPhases = [...(data.phases || [])].sort(
        (a, b) => a.position - b.position,
      )
      setPhases(sortedPhases)
      const map = {}
      for (const p of sortedPhases) {
        map[p.id] = [...(p.cards || [])].sort((a, b) => a.position - b.position)
      }
      setCardsByPhase(map)
      api.get(`/card-links/board/${boardId}`).then(({ data }) => {
        setLinkedCardIds(new Set(data))
      }).catch(() => {})
    } catch (err) {
      toast.error(errMsg(err, 'Erro ao carregar fluxo'))
    } finally {
      setLoading(false)
    }
  }, [boardId])

  useEffect(() => {
    fetchBoard()
  }, [fetchBoard])

  /* ---------- Card CRUD ---------- */
  const handleAddCard = (phase) => {
    setEditorCard(null)
    setEditorPhaseId(phase.id)
    setEditorOpen(true)
  }
  const handleCardClick = (card) => {
    setEditorCard(card)
    setEditorPhaseId(null)
    setEditorOpen(true)
  }
  const handleCardSaved = (saved) => {
    setCardsByPhase((prev) => {
      const next = { ...prev }
      for (const pid of Object.keys(next)) {
        next[pid] = next[pid].filter((c) => c.id !== saved.id)
      }
      next[saved.phase_id] = [...(next[saved.phase_id] || []), saved].sort(
        (a, b) => a.position - b.position,
      )
      return next
    })
  }
  const handleCardDeleted = (card) => {
    setCardsByPhase((prev) => {
      const next = { ...prev }
      next[card.phase_id] = (next[card.phase_id] || []).filter(
        (c) => c.id !== card.id,
      )
      return next
    })
  }

  // After approve/reject the card may have moved to another board's phase — full refresh
  const handleApprovalAction = () => {
    setEditorOpen(false)
    fetchBoard()
  }

  /* ---------- Move to phase (dropdown) ---------- */
  const handleMoveToPhase = async (card, targetPhase) => {
    if (card.phase_id === targetPhase.id) return
    const sourcePhaseId = card.phase_id

    // Optimistic UI
    setCardsByPhase((prev) => {
      const next = { ...prev }
      next[sourcePhaseId] = (next[sourcePhaseId] || []).filter((c) => c.id !== card.id)
      const updated = { ...card, phase_id: targetPhase.id }
      next[targetPhase.id] = [...(next[targetPhase.id] || []), updated]
      return next
    })

    try {
      await api.post(`/cards/${card.id}/move`, {
        target_phase_id: targetPhase.id,
        target_position: 999,
      })
      toast.success(`Card movido para "${targetPhase.name}"`)
      // Refresh to catch any cross-flow auto-advance effects
      fetchBoard()
    } catch (err) {
      toast.error(errMsg(err, 'Falha ao mover card'))
      fetchBoard()
    }
  }

  /* ---------- Phase create ---------- */
  const handleCreatePhase = async (e) => {
    e?.preventDefault()
    if (!phaseName.trim()) return
    setCreatingPhase(true)
    try {
      const { data } = await api.post(`/boards/${boardId}/phases`, {
        name: phaseName.trim(),
        color: 'slate',
      })
      setPhases((p) => [...p, data])
      setCardsByPhase((m) => ({ ...m, [data.id]: [] }))
      setPhaseName('')
      setPhaseModalOpen(false)
      toast.success('Fase criada')
    } catch (err) {
      toast.error(errMsg(err, 'Erro ao criar fase'))
    } finally {
      setCreatingPhase(false)
    }
  }

  /* ---------- Drag & drop ---------- */
  const findCard = (id) => {
    for (const pid of Object.keys(cardsByPhase)) {
      const c = cardsByPhase[pid].find((c) => c.id === id)
      if (c) return c
    }
    return null
  }

  function handleDragStart(event) {
    const { active } = event
    const card = findCard(active.id)
    setActiveCard(card || null)
  }

  function handleDragOver(event) {
    const { active, over } = event
    if (!over) return

    const activeId = active.id
    const overId = over.id

    const activePhaseId = active.data.current?.phaseId
    let overPhaseId = over.data.current?.phaseId
    if (!overPhaseId && typeof overId === 'string' && overId.startsWith('phase-')) {
      overPhaseId = overId.replace('phase-', '')
    }
    if (!activePhaseId || !overPhaseId || activePhaseId === overPhaseId) return

    setCardsByPhase((prev) => {
      const src = [...(prev[activePhaseId] || [])]
      const dst = [...(prev[overPhaseId] || [])]
      const idx = src.findIndex((c) => c.id === activeId)
      if (idx === -1) return prev
      const [moved] = src.splice(idx, 1)
      let insertIdx = dst.length
      if (over.data.current?.type === 'card') {
        insertIdx = dst.findIndex((c) => c.id === overId)
        if (insertIdx === -1) insertIdx = dst.length
      }
      const movedUpdated = { ...moved, phase_id: overPhaseId }
      dst.splice(insertIdx, 0, movedUpdated)
      return { ...prev, [activePhaseId]: src, [overPhaseId]: dst }
    })
  }

  async function handleDragEnd(event) {
    const { active, over } = event
    setActiveCard(null)
    if (!over) return

    const activeId = active.id
    const overId = over.id

    const activeCardRef = findCard(activeId)
    if (!activeCardRef) return

    const activePhaseId = activeCardRef.phase_id
    let overPhaseId = over.data.current?.phaseId
    if (!overPhaseId && typeof overId === 'string' && overId.startsWith('phase-')) {
      overPhaseId = overId.replace('phase-', '')
    }
    if (!overPhaseId) overPhaseId = activePhaseId

    let finalTargetPos = 0
    setCardsByPhase((prev) => {
      let next = prev
      if (activePhaseId === overPhaseId && activeId !== overId) {
        const items = prev[overPhaseId] || []
        const oldIdx = items.findIndex((c) => c.id === activeId)
        const newIdx = items.findIndex((c) => c.id === overId)
        if (oldIdx !== -1 && newIdx !== -1) {
          next = { ...prev, [overPhaseId]: arrayMove(items, oldIdx, newIdx) }
        }
      }
      const list = next[overPhaseId] || []
      const idx = list.findIndex((c) => c.id === activeId)
      finalTargetPos = idx >= 0 ? idx : list.length
      return next
    })

    try {
      await api.post(`/cards/${activeId}/move`, {
        target_phase_id: overPhaseId,
        target_position: finalTargetPos,
      })
      if (activePhaseId !== overPhaseId) {
        fetchBoard()
      }
    } catch (err) {
      toast.error(errMsg(err, 'Falha ao mover card'))
      fetchBoard()
    }
  }

  /* ---------- Render ---------- */
  if (loading) {
    return (
      <div className="flex h-[60vh] items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    )
  }

  if (!board) {
    return (
      <div className="flex h-[60vh] flex-col items-center justify-center gap-3">
        <p className="text-muted-foreground">Fluxo nao encontrado.</p>
        <Link to="/boards">
          <Button variant="ghost">
            <ArrowLeft className="h-4 w-4" /> Voltar
          </Button>
        </Link>
      </div>
    )
  }

  return (
    <div className="flex h-[calc(100vh-104px)] flex-col">
      {/* Board header */}
      <div className="mb-4 flex items-center gap-3">
        <Link
          to="/boards"
          className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
          aria-label="Voltar para fluxos"
        >
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <div className="flex-1 min-w-0">
          <h1 className="truncate text-xl font-bold tracking-tight">{board.name}</h1>
          {board.description && (
            <p className="truncate text-sm text-muted-foreground">{board.description}</p>
          )}
        </div>
        {isAdmin && (
          <Button variant="ghost" onClick={() => setSettingsOpen(true)} title="Configuracoes do fluxo">
            <Settings className="h-4 w-4" />
          </Button>
        )}
        <Button variant="secondary" onClick={() => setPhaseModalOpen(true)}>
          <Plus className="h-4 w-4" />
          Nova fase
        </Button>
      </div>

      {/* Kanban */}
      <div className="flex-1 overflow-x-auto scrollbar-thin pb-4">
        <DndContext
          sensors={sensors}
          collisionDetection={closestCorners}
          onDragStart={handleDragStart}
          onDragOver={handleDragOver}
          onDragEnd={handleDragEnd}
          onDragCancel={() => setActiveCard(null)}
        >
          <div className="flex h-full gap-4">
            {phases.map((phase) => (
              <KanbanColumn
                key={phase.id}
                phase={phase}
                cards={cardsByPhase[phase.id] || []}
                onAddCard={handleAddCard}
                onCardClick={handleCardClick}
                users={users}
                linkedCardIds={linkedCardIds}
                phases={phases}
                onMoveToPhase={handleMoveToPhase}
              />
            ))}
            {phases.length === 0 && (
              <div className="flex flex-1 items-center justify-center">
                <div className="text-center">
                  <p className="text-muted-foreground">Nenhuma fase configurada.</p>
                  <Button className="mt-3" onClick={() => setPhaseModalOpen(true)}>
                    <Plus className="h-4 w-4" />
                    Criar primeira fase
                  </Button>
                </div>
              </div>
            )}
          </div>
          <DragOverlay>
            {activeCard ? (
              <div className="rotate-1 opacity-90">
                <KanbanCard card={activeCard} users={users} />
              </div>
            ) : null}
          </DragOverlay>
        </DndContext>
      </div>

      {/* Modals */}
      <CardEditor
        open={editorOpen}
        card={editorCard}
        phaseId={editorPhaseId}
        onClose={() => setEditorOpen(false)}
        onSaved={handleCardSaved}
        onDeleted={handleCardDeleted}
        onApprovalAction={handleApprovalAction}
        users={users}
      />

      <Modal
        open={phaseModalOpen}
        onClose={() => !creatingPhase && setPhaseModalOpen(false)}
        title="Nova fase"
        footer={
          <>
            <Button variant="ghost" onClick={() => setPhaseModalOpen(false)} disabled={creatingPhase}>
              Cancelar
            </Button>
            <Button onClick={handleCreatePhase} loading={creatingPhase} form="phase-form" type="submit">
              Criar fase
            </Button>
          </>
        }
      >
        <form id="phase-form" onSubmit={handleCreatePhase}>
          <label className="mb-1.5 block text-sm font-medium" htmlFor="p-name">
            Nome da fase
          </label>
          <Input
            id="p-name"
            autoFocus
            value={phaseName}
            onChange={(e) => setPhaseName(e.target.value)}
            placeholder="Ex.: Aguardando aprovacao"
          />
        </form>
      </Modal>

      <BoardSettings
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        board={board}
        phases={phases}
      />
    </div>
  )
}
