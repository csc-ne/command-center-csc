import clsx from 'clsx'
import { twMerge } from 'tailwind-merge'

/** Compose Tailwind classes conditionally, with conflict resolution. */
export function cn(...inputs) {
  return twMerge(clsx(inputs))
}

/** Priority badge color mapping. */
export const PRIORITY_STYLES = {
  low:      'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
  medium:   'bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300',
  high:     'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300',
  critical: 'bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300',
}

export const PRIORITY_LABEL = {
  low: 'Baixa',
  medium: 'Média',
  high: 'Alta',
  critical: 'Crítica',
}

/** Format ISO date to "15 abr" pt-BR short form. */
export function formatShortDate(iso) {
  if (!iso) return null
  try {
    return new Date(iso).toLocaleDateString('pt-BR', {
      day: '2-digit',
      month: 'short',
    })
  } catch {
    return null
  }
}
