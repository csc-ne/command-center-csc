import { useDroppable } from '@dnd-kit/core'
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable'
import { MoreVertical, Plus } from 'lucide-react'
import KanbanCard from './KanbanCard'
import { cn } from '@/lib/utils'

const PHASE_ACCENT = {
  slate: 'bg-slate-400',
  indigo: 'bg-indigo-500',
  blue: 'bg-blue-500',
  emerald: 'bg-emerald-500',
  amber: 'bg-amber-500',
  rose: 'bg-rose-500',
  violet: 'bg-violet-500',
  red: 'bg-red-500',
}

export default function KanbanColumn({
  phase,
  cards,
  onAddCard,
  onCardClick,
  onPhaseMenu,
  users = [],
  linkedCardIds = new Set(),
  phases = [],
  onMoveToPhase,
}) {
  const { setNodeRef, isOver } = useDroppable({
    id: `phase-${phase.id}`,
    data: { type: 'phase', phaseId: phase.id },
  })

  const accent = PHASE_ACCENT[phase.color] || PHASE_ACCENT.slate
  const overLimit = phase.wip_limit && cards.length > phase.wip_limit

  return (
    <div className="flex w-80 shrink-0 flex-col rounded-lg bg-surface-muted">
      {/* Column header */}
      <div className="flex items-center gap-2 border-b border-border/60 px-3 py-3">
        <span className={cn('h-2 w-2 rounded-full', accent)} />
        <h3 className="truncate text-sm font-semibold text-foreground">
          {phase.name}
        </h3>
        <span
          className={cn(
            'rounded-full bg-surface px-2 py-0.5 text-xs font-medium text-muted-foreground',
            overLimit && 'bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300',
          )}
          title={phase.wip_limit ? `Limite WIP: ${phase.wip_limit}` : undefined}
        >
          {cards.length}
          {phase.wip_limit ? ` / ${phase.wip_limit}` : ''}
        </span>
        <div className="ml-auto flex items-center gap-0.5">
          <button
            onClick={() => onAddCard?.(phase)}
            aria-label="Adicionar card"
            title="Adicionar card"
            className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground transition-colors cursor-pointer"
          >
            <Plus className="h-4 w-4" />
          </button>
          <button
            onClick={() => onPhaseMenu?.(phase)}
            aria-label="Opcoes da fase"
            title="Opcoes"
            className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground transition-colors cursor-pointer"
          >
            <MoreVertical className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Droppable list */}
      <div
        ref={setNodeRef}
        className={cn(
          'flex-1 space-y-2 overflow-y-auto p-2 scrollbar-thin transition-colors',
          isOver && 'bg-primary/5',
        )}
        style={{ minHeight: '120px', maxHeight: 'calc(100vh - 220px)' }}
      >
        <SortableContext
          items={cards.map((c) => c.id)}
          strategy={verticalListSortingStrategy}
        >
          {cards.map((c) => (
            <KanbanCard
              key={c.id}
              card={c}
              onClick={onCardClick}
              users={users}
              isLinked={linkedCardIds.has(c.id)}
              phases={phases}
              onMoveToPhase={onMoveToPhase}
            />
          ))}
        </SortableContext>
        {cards.length === 0 && (
          <div className="flex h-24 items-center justify-center rounded border border-dashed border-border/60 text-xs text-muted-foreground">
            Solte cards aqui
          </div>
        )}
      </div>

      {/* Add card at bottom */}
      <button
        type="button"
        onClick={() => onAddCard?.(phase)}
        className="flex items-center gap-2 border-t border-border/60 px-3 py-2 text-sm text-muted-foreground hover:bg-surface hover:text-foreground transition-colors cursor-pointer"
      >
        <Plus className="h-4 w-4" />
        Adicionar card
      </button>
    </div>
  )
}
