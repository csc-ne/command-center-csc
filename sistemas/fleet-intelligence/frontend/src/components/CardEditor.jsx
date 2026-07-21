import { useEffect, useRef, useState } from 'react'
import toast from 'react-hot-toast'
import {
  CheckCircle2,
  Download,
  FileText,
  Image,
  Link2,
  Loader2,
  Paperclip,
  Search,
  Trash2,
  Upload,
  User,
  X,
  XCircle,
} from 'lucide-react'

import Modal from './ui/Modal'
import Button from './ui/Button'
import Input from './ui/Input'
import { api, errMsg } from '@/api/client'
import { cn } from '@/lib/utils'

const PRIORITIES = [
  { id: 'low', label: 'Baixa' },
  { id: 'medium', label: 'Media' },
  { id: 'high', label: 'Alta' },
  { id: 'critical', label: 'Critica' },
]

export default function CardEditor({
  open,
  card,
  phaseId,
  onClose,
  onSaved,
  onDeleted,
  onApprovalAction,
  users = [],
  creatorName,
}) {
  const isEdit = Boolean(card)
  const fileRef = useRef(null)

  const [form, setForm] = useState({
    title: '',
    description: '',
    priority: 'medium',
    due_date: '',
    tags: '',
    assignee_id: '',
  })
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [approving, setApproving] = useState(false)
  const [rejecting, setRejecting] = useState(false)

  // Attachments
  const [attachments, setAttachments] = useState([])
  const [uploading, setUploading] = useState(false)

  // Cross-flow links
  const [cardLinks, setCardLinks] = useState([])

  // Target card attachments (for approval download)
  const [targetAttachments, setTargetAttachments] = useState([])

  // Chassi lookup
  const [chassi, setChassi] = useState('')
  const [chassiData, setChassiData] = useState(null)
  const [lookingUp, setLookingUp] = useState(false)

  useEffect(() => {
    if (open && card) {
      setForm({
        title: card.title || '',
        description: card.description || '',
        priority: card.priority || 'medium',
        due_date: card.due_date ? card.due_date.slice(0, 10) : '',
        tags: (card.tags || []).join(', '),
        assignee_id: card.assignee_id || '',
      })
      // Load chassi from metadata
      const meta = card.metadata || {}
      setChassi(meta.chassi || '')
      setChassiData(meta.chassi_data || null)

      api.get(`/attachments/card/${card.id}`).then(({ data }) => setAttachments(data)).catch(() => {})
      api.get(`/card-links/card/${card.id}`).then(({ data }) => setCardLinks(data)).catch(() => {})
    } else if (open) {
      setForm({ title: '', description: '', priority: 'medium', due_date: '', tags: '', assignee_id: '' })
      setAttachments([])
      setCardLinks([])
      setChassi('')
      setChassiData(null)
      setTargetAttachments([])
    }
  }, [open, card])

  // This card is awaiting manager approval (source card, link status=completed)
  const approvalLink = cardLinks.find(
    (lk) => lk.source_card_id === card?.id && lk.status === 'completed'
  )

  // Fetch target card's attachments for the manager to download
  useEffect(() => {
    if (approvalLink?.target_card_id) {
      api.get(`/attachments/card/${approvalLink.target_card_id}`)
        .then(({ data }) => setTargetAttachments(data))
        .catch(() => setTargetAttachments([]))
    } else {
      setTargetAttachments([])
    }
  }, [approvalLink?.target_card_id])

  const isBusy = saving || deleting || approving || rejecting

  /* ---------- Chassi lookup ---------- */
  async function handleChassiLookup() {
    if (!chassi.trim()) return
    setLookingUp(true)
    setChassiData(null)
    try {
      const { data } = await api.get('/cards/chassi-lookup', {
        params: { chassi: chassi.trim().toUpperCase() },
      })
      setChassiData(data)
      toast.success(`Equipamento encontrado: ${data.cliente || data.chassi}`)
    } catch (err) {
      toast.error(errMsg(err, `Chassi "${chassi}" nao encontrado`))
    } finally {
      setLookingUp(false)
    }
  }

  /* ---------- Save ---------- */
  async function handleSave(e) {
    e?.preventDefault()
    if (!form.title.trim()) { toast.error('Titulo e obrigatorio'); return }
    const metadata = {}
    if (chassi.trim()) metadata.chassi = chassi.trim().toUpperCase()
    if (chassiData) metadata.chassi_data = chassiData

    const payload = {
      title: form.title.trim(),
      description: form.description.trim() || null,
      priority: form.priority,
      due_date: form.due_date ? form.due_date + 'T12:00:00Z' : null,
      tags: form.tags.split(',').map((t) => t.trim()).filter(Boolean),
      assignee_id: form.assignee_id || null,
      metadata,
    }
    setSaving(true)
    try {
      if (isEdit) {
        const { data } = await api.patch(`/cards/${card.id}`, payload)
        toast.success('Card atualizado')
        onSaved?.(data)
      } else {
        const { data } = await api.post('/cards', { ...payload, phase_id: phaseId })
        toast.success('Card criado')
        onSaved?.(data)
      }
      onClose?.()
    } catch (err) {
      toast.error(errMsg(err, 'Erro ao salvar'))
    } finally {
      setSaving(false)
    }
  }

  /* ---------- Delete ---------- */
  async function handleDelete() {
    if (!isEdit) return
    if (!confirm('Excluir este card? Essa acao nao pode ser desfeita.')) return
    setDeleting(true)
    try {
      await api.delete(`/cards/${card.id}`)
      toast.success('Card excluido')
      onDeleted?.(card)
      onClose?.()
    } catch (err) {
      toast.error(errMsg(err, 'Erro ao excluir'))
    } finally {
      setDeleting(false)
    }
  }

  /* ---------- Approve / Reject ---------- */
  async function handleApprove() {
    if (!card) return
    setApproving(true)
    try {
      await api.post(`/cards/${card.id}/approve`)
      toast.success('Documento aprovado! Card concluido em ambos os fluxos.')
      onApprovalAction?.()
    } catch (err) {
      toast.error(errMsg(err, 'Erro ao aprovar'))
    } finally {
      setApproving(false)
    }
  }

  async function handleReject() {
    if (!card) return
    if (!confirm('Rejeitar o documento? O card voltara para revisao e o responsavel precisara enviar novamente.')) return
    setRejecting(true)
    try {
      await api.post(`/cards/${card.id}/reject`)
      toast.success('Documento rejeitado. Card enviado de volta para revisao.')
      onApprovalAction?.()
    } catch (err) {
      toast.error(errMsg(err, 'Erro ao rejeitar'))
    } finally {
      setRejecting(false)
    }
  }

  /* ---------- Attachments ---------- */
  async function handleUpload(e) {
    const file = e.target.files?.[0]
    if (!file || !card) return
    if (file.size > 5 * 1024 * 1024) { toast.error('Arquivo muito grande. Limite: 5MB'); return }
    setUploading(true)
    const formData = new FormData()
    formData.append('file', file)
    try {
      const { data } = await api.post(`/attachments/card/${card.id}`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setAttachments((prev) => [data, ...prev])
      toast.success('Anexo enviado')
    } catch (err) {
      toast.error(errMsg(err, 'Erro ao enviar anexo'))
    } finally {
      setUploading(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  async function handleDeleteAttachment(att) {
    try {
      await api.delete(`/attachments/${att.id}`)
      setAttachments((prev) => prev.filter((a) => a.id !== att.id))
      toast.success('Anexo removido')
    } catch (err) {
      toast.error(errMsg(err))
    }
  }

  function downloadUrl(att) {
    return `${api.defaults.baseURL}/attachments/${att.id}/download`
  }

  const creator = isEdit && card?.created_by
    ? users.find((u) => u.id === card.created_by)
    : null

  const isCompleted = Boolean((card?.metadata || {})._completed)

  return (
    <Modal
      open={open}
      onClose={() => !isBusy && onClose?.()}
      title={isEdit ? 'Editar card' : 'Novo card'}
      size="lg"
      footer={
        <>
          {isEdit && (
            <Button variant="ghost" onClick={handleDelete} loading={deleting} disabled={isBusy}
              className="mr-auto text-destructive hover:bg-destructive/10">
              <Trash2 className="h-4 w-4" /> Excluir
            </Button>
          )}
          <Button variant="ghost" onClick={onClose} disabled={isBusy}>Cancelar</Button>
          <Button onClick={handleSave} loading={saving} disabled={isBusy} form="card-form" type="submit">
            {isEdit ? 'Salvar' : 'Criar card'}
          </Button>
        </>
      }
    >
      <form id="card-form" onSubmit={handleSave} className="space-y-4">

        {/* Completed badge */}
        {isCompleted && (
          <div className="flex items-center gap-2 rounded-md bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 px-3 py-2 text-xs text-emerald-700 dark:text-emerald-400">
            <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
            <span className="font-medium">Card concluido</span>
          </div>
        )}

        {/* Creator info */}
        {isEdit && (creator || creatorName) && (
          <div className="flex items-center gap-2 rounded-md bg-muted/50 px-3 py-2 text-xs text-muted-foreground">
            <User className="h-3.5 w-3.5" />
            <span>Criado por <strong className="text-foreground">{creator?.full_name || creatorName || 'Desconhecido'}</strong></span>
          </div>
        )}

        {/* Approval banner */}
        {approvalLink && (
          <div className="rounded-lg border border-violet-200 bg-violet-50 dark:border-violet-800 dark:bg-violet-950/40 p-4 space-y-3">
            <div className="flex items-center gap-2">
              <div className="h-2 w-2 animate-pulse rounded-full bg-violet-500" />
              <span className="text-sm font-semibold text-violet-800 dark:text-violet-300">
                Documento aguardando aprovacao
              </span>
            </div>
            <p className="text-xs text-violet-600 dark:text-violet-400">
              O subfluxo enviou o documento para revisao. Baixe e analise antes de decidir.
            </p>

            {/* Documents from subflow card */}
            {targetAttachments.length > 0 && (
              <div className="space-y-1.5">
                <p className="text-xs font-medium text-violet-700 dark:text-violet-300">Documentos enviados:</p>
                {targetAttachments.map((att) => {
                  const isImage = att.mime_type?.startsWith('image/')
                  return (
                    <a
                      key={att.id}
                      href={downloadUrl(att)}
                      target="_blank"
                      rel="noreferrer"
                      className="flex items-center gap-2 rounded-md border border-violet-200 dark:border-violet-700 bg-white dark:bg-violet-900/30 px-3 py-2 text-xs hover:bg-violet-50 dark:hover:bg-violet-800/40 transition-colors"
                    >
                      {isImage
                        ? <Image className="h-4 w-4 text-blue-500 shrink-0" />
                        : <FileText className="h-4 w-4 text-red-500 shrink-0" />}
                      <span className="flex-1 truncate text-violet-800 dark:text-violet-200">{att.filename}</span>
                      <span className="text-violet-500 shrink-0">{(att.file_size / 1024).toFixed(0)}KB</span>
                      <Download className="h-3.5 w-3.5 text-violet-500 shrink-0" />
                    </a>
                  )
                })}
              </div>
            )}
            {targetAttachments.length === 0 && (
              <p className="text-xs text-violet-500 italic">Nenhum documento anexado no subfluxo.</p>
            )}

            <div className="flex gap-2 pt-1">
              <Button type="button" onClick={handleApprove} loading={approving} disabled={isBusy}
                className="flex-1 bg-emerald-600 hover:bg-emerald-700 text-white border-0">
                <CheckCircle2 className="h-4 w-4" /> Aprovar
              </Button>
              <Button type="button" variant="ghost" onClick={handleReject} loading={rejecting} disabled={isBusy}
                className="flex-1 text-destructive hover:bg-destructive/10">
                <XCircle className="h-4 w-4" /> Rejeitar
              </Button>
            </div>
          </div>
        )}

        {/* Card links info */}
        {cardLinks.length > 0 && !approvalLink && (
          <div className="space-y-1">
            {cardLinks.map((lk) => (
              <div key={lk.id} className="flex items-center gap-2 rounded-md bg-blue-50 dark:bg-blue-950 px-3 py-2 text-xs">
                <Link2 className="h-3.5 w-3.5 text-blue-500" />
                <span className="text-blue-700 dark:text-blue-300">
                  {lk.source_card_id === card?.id
                    ? <>Vinculado a: <strong>{lk.target_card_title || 'Card filho'}</strong> em {lk.target_board_name}</>
                    : <>Originado de: <strong>{lk.source_card_title || 'Card pai'}</strong> em {lk.source_board_name}</>}
                  {' '}&mdash;{' '}
                  <span className={cn(
                    lk.status === 'approved' ? 'text-emerald-600' :
                    lk.status === 'completed' ? 'text-violet-600' : 'text-amber-600'
                  )}>
                    {lk.status === 'approved' ? 'Aprovado' :
                     lk.status === 'completed' ? 'Aguardando aprovacao' : 'Pendente'}
                  </span>
                </span>
              </div>
            ))}
          </div>
        )}

        {/* Title */}
        <div>
          <label className="mb-1.5 block text-sm font-medium" htmlFor="c-title">Titulo</label>
          <Input id="c-title" autoFocus value={form.title}
            onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
            placeholder="O que precisa ser feito?" required />
        </div>

        {/* Description */}
        <div>
          <label className="mb-1.5 block text-sm font-medium" htmlFor="c-desc">Descricao</label>
          <textarea id="c-desc" rows={3} value={form.description}
            onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
            className="flex w-full rounded-md border border-border bg-surface px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:border-transparent transition-colors resize-y"
            placeholder="Contexto, detalhes, links..." />
        </div>

        {/* Priority + Due date */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="mb-1.5 block text-sm font-medium" htmlFor="c-prio">Prioridade</label>
            <select id="c-prio" value={form.priority}
              onChange={(e) => setForm((f) => ({ ...f, priority: e.target.value }))}
              className="flex h-10 w-full rounded-md border border-border bg-surface px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring transition-colors cursor-pointer">
              {PRIORITIES.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
            </select>
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium" htmlFor="c-due">Data limite</label>
            <Input id="c-due" type="date" value={form.due_date}
              onChange={(e) => setForm((f) => ({ ...f, due_date: e.target.value }))} />
          </div>
        </div>

        {/* Assignee */}
        <div>
          <label className="mb-1.5 block text-sm font-medium" htmlFor="c-assignee">Responsavel</label>
          <select id="c-assignee" value={form.assignee_id}
            onChange={(e) => setForm((f) => ({ ...f, assignee_id: e.target.value }))}
            className="flex h-10 w-full rounded-md border border-border bg-surface px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring transition-colors cursor-pointer">
            <option value="">Nenhum</option>
            {users.map((u) => <option key={u.id} value={u.id}>{u.full_name} ({u.role})</option>)}
          </select>
        </div>

        {/* Tags */}
        <div>
          <label className="mb-1.5 block text-sm font-medium" htmlFor="c-tags">
            Tags <span className="text-muted-foreground font-normal">(separadas por virgula)</span>
          </label>
          <Input id="c-tags" value={form.tags}
            onChange={(e) => setForm((f) => ({ ...f, tags: e.target.value }))}
            placeholder="ex: revisao, urgente, frota-a" />
        </div>

        {/* Chassi lookup */}
        <div className="rounded-lg border border-border bg-muted/20 p-3 space-y-3">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Consulta por Chassi</p>
          <div className="flex gap-2">
            <Input
              value={chassi}
              onChange={(e) => { setChassi(e.target.value.toUpperCase()); if (chassiData) setChassiData(null) }}
              onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), handleChassiLookup())}
              placeholder="Digite o numero do chassi..."
              className="flex-1 font-mono text-sm uppercase"
            />
            <button
              type="button"
              onClick={handleChassiLookup}
              disabled={lookingUp || !chassi.trim()}
              title="Consultar chassi"
              className="inline-flex items-center justify-center gap-1.5 rounded-md border border-border bg-surface px-3 py-2 text-sm font-medium text-foreground hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed transition-colors cursor-pointer"
            >
              {lookingUp
                ? <Loader2 className="h-4 w-4 animate-spin" />
                : <Search className="h-4 w-4" />}
            </button>
          </div>

          {chassiData && (
            <div className="grid grid-cols-2 gap-x-4 gap-y-2 rounded-md bg-surface border border-border p-3 text-xs">
              <ChassiField label="Nome do cliente" value={chassiData.cliente} />
              <ChassiField label="CPF / CNPJ" value={chassiData.cpf_cnpj} />
              <ChassiField label="Email" value={chassiData.email} />
              <ChassiField label="Telefone" value={chassiData.telefone || chassiData.contato} />
              <ChassiField
                label="Horimetro"
                value={chassiData.horimetro
                  ? `${chassiData.horimetro}h${chassiData.data_horimetro ? ' (em ' + new Date(chassiData.data_horimetro).toLocaleDateString('pt-BR') + ')' : ''}`
                  : null}
              />
              <ChassiField
                label="Localizacao"
                value={[chassiData.cidade, chassiData.estado, chassiData.regional].filter(Boolean).join(' / ') || null}
              />
            </div>
          )}

          {!chassiData && chassi.trim() && !lookingUp && (
            <p className="text-xs text-muted-foreground italic">Clique na lupa para buscar os dados do equipamento.</p>
          )}
        </div>

        {/* Attachments (edit mode only) */}
        {isEdit && (
          <div>
            <div className="mb-1.5 flex items-center justify-between">
              <label className="text-sm font-medium">
                <Paperclip className="inline h-3.5 w-3.5 mr-1" />
                Anexos
              </label>
              <button type="button" onClick={() => fileRef.current?.click()} disabled={uploading}
                className="inline-flex items-center gap-1 text-xs text-primary hover:underline cursor-pointer disabled:opacity-50">
                <Upload className="h-3 w-3" />
                {uploading ? 'Enviando...' : 'Enviar arquivo'}
              </button>
              <input ref={fileRef} type="file" accept=".png,.jpg,.jpeg,.webp,.pdf"
                onChange={handleUpload} className="hidden" />
            </div>

            {attachments.length === 0 ? (
              <div className="rounded-md border border-dashed border-border p-4 text-center text-xs text-muted-foreground">
                Nenhum anexo. Clique em "Enviar arquivo" para adicionar (PNG, JPG, PDF — max 5MB).
              </div>
            ) : (
              <div className="space-y-1.5">
                {attachments.map((att) => {
                  const isImage = att.mime_type?.startsWith('image/')
                  return (
                    <div key={att.id} className="flex items-center gap-2 rounded-md border border-border px-3 py-2 text-xs">
                      {isImage
                        ? <Image className="h-4 w-4 text-blue-500 shrink-0" />
                        : <FileText className="h-4 w-4 text-red-500 shrink-0" />}
                      <span className="flex-1 truncate">{att.filename}</span>
                      <span className="text-muted-foreground shrink-0">{(att.file_size / 1024).toFixed(0)}KB</span>
                      <a href={downloadUrl(att)} target="_blank" rel="noreferrer"
                        className="rounded p-1 text-muted-foreground hover:text-foreground hover:bg-muted">
                        <Download className="h-3.5 w-3.5" />
                      </a>
                      <button type="button" onClick={() => handleDeleteAttachment(att)}
                        className="rounded p-1 text-destructive hover:bg-destructive/10 cursor-pointer">
                        <X className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        )}
      </form>
    </Modal>
  )
}

function ChassiField({ label, value }) {
  if (!value || value === 'nao tem') return null
  return (
    <div>
      <p className="text-muted-foreground mb-0.5">{label}</p>
      <p className="font-medium text-foreground truncate">{value}</p>
    </div>
  )
}
