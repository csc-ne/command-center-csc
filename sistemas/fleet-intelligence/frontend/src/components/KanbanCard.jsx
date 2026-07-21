import { useRef, useState } from 'react'
import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { Calendar, CheckCircle2, ChevronDown, Flag, GripVertical, Link2 } from 'lucide-react'
import { PRIORITY_LABEL, PRIORITY_STYLES, cn, formatShortDate } from '@/lib/utils'

export default function KanbanCard({
  card,
  onClick,
  users = [],
  isLinked = false,
  phases = [],
  onMoveToPhase,
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({
      id: card.id,
      data: { type: 'card', phaseId: card.phase_id, card },
    })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  }

  const isCompleted = Boolean(card.card_metadata?._completed || card.metadata?._completed)

  const assignee = card.assignee_id
    ? users.find((u) => u.id === card.assignee_id)
    : null

  const assigneeInitials = assignee
    ? assignee.full_name
        .split(' ')
        .map((s) => s[0])
        .filter(Boolean)
        .slice(0, 2)
        .join('')
        .toUpperCase()
    : null

  // Phase dropdown
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const dropdownRef = useRef(null)
  const otherPhases = phases.filter((p) => p.id !== card.phase_id)

  function handlePhaseSelect(e, phase) {
    e.stopPropagation()
    setDropdownOpen(false)
    onMoveToPhase?.(card, phase)
  }

  function handleDropdownToggle(e) {
    e.stopPropagation()
    setDropdownOpen((v) => !v)
  }

  function handleBlur(e) {
    if (!dropdownRef.current?.contains(e.relatedTarget)) {
      setDropdownOpen(false)
    }
  }

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={cn(
        'group rounded-lg border bg-surface p-3 shadow-card transition-shadow',
        'hover:shadow-card-hover cursor-pointer',
        isDragging && 'opacity-40 shadow-card-drag',
        isCompleted
          ? 'border-emerald-400/60 dark:border-emerald-600/60 bg-emerald-50/40 dark:bg-emerald-950/20'
          : 'border-border',
      )}
      onClick={() => {
        if (!isDragging) onClick?.(card)
      }}
    >
      <div className="flex items-start gap-2">
        <button
          type="button"
          aria-label="Arrastar card"
          {...attributes}
          {...listeners}
          onClick={(e) => e.stopPropagation()}
          className="mt-0.5 shrink-0 cursor-grab rounded p-0.5 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100 hover:bg-muted active:cursor-grabbing"
        >
          <GripVertical className="h-4 w-4" />
        </button>

        <div className="min-w-0 flex-1">
          <h4 className="text-sm font-medium leading-snug text-foreground">
            {card.title}
          </h4>
          {card.description && (
            <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">
              {card.description}
            </p>
          )}

          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            {isCompleted && (
              <span className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-semibold bg-emerald-100 dark:bg-emerald-900/50 text-emerald-700 dark:text-emerald-400">
                <CheckCircle2 className="h-3 w-3" />
                Concluído
              </span>
            )}
            <span
              className={cn(
                'inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium',
                PRIORITY_STYLES[card.priority],
              )}
            >
              <Flag className="h-3 w-3" />
              {PRIORITY_LABEL[card.priority]}
            </span>
            {card.due_date && (
              <span className={cn(
                'inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium',
                !isCompleted && new Date(card.due_date) < new Date()
                  ? 'bg-destructive/15 text-destructive'
                  : 'bg-muted text-muted-foreground'
              )}>
                <Calendar className="h-3 w-3" />
                {formatShortDate(card.due_date)}
              </span>
            )}
            {card.tags?.slice(0, 3).map((t) => (
              <span
                key={t}
                className="rounded bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary"
              >
                {t}
              </span>
            ))}
            {isLinked && (
              <span
                className="inline-flex items-center gap-0.5 rounded bg-blue-100 dark:bg-blue-950 px-1.5 py-0.5 text-[10px] font-medium text-blue-600 dark:text-blue-400"
                title="Card vinculado a outro fluxo"
              >
                <Link2 className="h-3 w-3" />
                Vinculado
              </span>
            )}
          </div>

          {/* Assignee */}
          {assignee && (
            <div className="mt-2 flex items-center gap-1.5">
              <div className="flex h-5 w-5 items-center justify-center rounded-full bg-primary/15 text-[9px] font-semibold text-primary">
                {assigneeInitials}
              </div>
              <span className="text-[11px] text-muted-foreground truncate">
                {assignee.full_name}
              </span>
            </div>
          )}

          {/* Phase selector dropdown */}
          {otherPhases.length > 0 && (
            <div
              className="relative mt-2"
              ref={dropdownRef}
              onBlur={handleBlur}
            >
              <button
                type="button"
                onClick={handleDropdownToggle}
                className="inline-flex items-center gap-1 rounded border border-border/60 bg-muted/40 px-2 py-0.5 text-[10px] text-muted-foreground hover:bg-muted hover:text-foreground transition-colors cursor-pointer opacity-0 group-hover:opacity-100"
                title="Mover para outra fase"
              >
                <ChevronDown className="h-3 w-3" />
                Mover para fase
              </button>

              {dropdownOpen && (
                <div
                  className="absolute left-0 top-full z-50 mt-1 min-w-[190px] rounded-md border border-border bg-surface shadow-lg"
                  onClick={(e) => e.stopPropagation()}
                >
                  <div className="py-1">
                    <p className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                      Selecionar fase
                    </p>
                    {otherPhases.map((phase) => (
                      <button
                        key={phase.id}
                        type="button"
                        onMouseDown={(e) => handlePhaseSelect(e, phase)}
                        className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs hover:bg-muted transition-colors cursor-pointer"
                      >
                        <span className="h-2 w-2 rounded-full bg-primary/50 shrink-0" />
                        {phase.name}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
