import { useEffect, useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { AlertCircle, CheckCircle2, Eye, EyeOff, UserPlus, Workflow } from 'lucide-react'
import toast from 'react-hot-toast'

import { useAuth } from '@/context/AuthContext'
import { api, errMsg } from '@/api/client'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import ThemeToggle from '@/components/ThemeToggle'

// ---------- sub-components ----------

function ErrorBanner({ message }) {
  if (!message) return null
  return (
    <div role="alert" className="mb-4 flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
      <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
      <span>{message}</span>
    </div>
  )
}

function TabButton({ active, children, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex-1 py-2.5 text-sm font-medium transition-colors rounded-lg cursor-pointer ${
        active
          ? 'bg-primary text-primary-foreground shadow-sm'
          : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
      }`}
    >
      {children}
    </button>
  )
}

// ---------- Login form ----------

function LoginForm() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPwd, setShowPwd] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    if (!username.trim() || !password) {
      setError('Preencha usuario e senha')
      return
    }
    setSubmitting(true)
    const res = await login(username.trim(), password)
    setSubmitting(false)
    if (res.ok) {
      toast.success('Bem-vindo!')
      navigate('/boards', { replace: true })
    } else {
      setError(res.error)
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <div className="mb-4">
        <label htmlFor="username" className="mb-1.5 block text-sm font-medium text-foreground">
          Usuario ou e-mail
        </label>
        <Input id="username" autoComplete="username" autoFocus value={username}
          onChange={(e) => setUsername(e.target.value)} placeholder="seu.email@venezanet.com" required />
      </div>
      <div className="mb-4">
        <label htmlFor="password" className="mb-1.5 block text-sm font-medium text-foreground">
          Senha
        </label>
        <div className="relative">
          <Input id="password" type={showPwd ? 'text' : 'password'} autoComplete="current-password"
            value={password} onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••" required className="pr-10" />
          <button type="button" onClick={() => setShowPwd((s) => !s)} tabIndex={-1}
            aria-label={showPwd ? 'Ocultar senha' : 'Mostrar senha'}
            className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1.5 text-muted-foreground hover:text-foreground transition-colors cursor-pointer">
            {showPwd ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </button>
        </div>
      </div>
      <ErrorBanner message={error} />
      <Button type="submit" loading={submitting} className="w-full" size="lg">
        Entrar
      </Button>
    </form>
  )
}

// ---------- Register form ----------

function RegisterForm({ onSuccess }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [showPwd, setShowPwd] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    if (password !== confirm) {
      setError('As senhas nao conferem')
      return
    }
    setSubmitting(true)
    try {
      await api.post('/auth/register', { email, password, confirm_password: confirm })
      onSuccess()
    } catch (err) {
      setError(errMsg(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <div className="mb-4">
        <label htmlFor="reg-email" className="mb-1.5 block text-sm font-medium text-foreground">
          E-mail corporativo
        </label>
        <Input id="reg-email" type="email" autoComplete="email" autoFocus value={email}
          onChange={(e) => setEmail(e.target.value)} placeholder="seu.nome@venezanet.com" required />
      </div>
      <div className="mb-4">
        <label htmlFor="reg-password" className="mb-1.5 block text-sm font-medium text-foreground">
          Senha
        </label>
        <div className="relative">
          <Input id="reg-password" type={showPwd ? 'text' : 'password'} autoComplete="new-password"
            value={password} onChange={(e) => setPassword(e.target.value)}
            placeholder="Minimo 6 caracteres" required minLength={6} className="pr-10" />
          <button type="button" onClick={() => setShowPwd((s) => !s)} tabIndex={-1}
            className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1.5 text-muted-foreground hover:text-foreground transition-colors cursor-pointer">
            {showPwd ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </button>
        </div>
      </div>
      <div className="mb-4">
        <label htmlFor="reg-confirm" className="mb-1.5 block text-sm font-medium text-foreground">
          Confirmar senha
        </label>
        <Input id="reg-confirm" type={showPwd ? 'text' : 'password'} autoComplete="new-password"
          value={confirm} onChange={(e) => setConfirm(e.target.value)}
          placeholder="Repita a senha" required minLength={6} />
      </div>
      <ErrorBanner message={error} />
      <Button type="submit" loading={submitting} className="w-full" size="lg">
        <UserPlus className="h-4 w-4 mr-2" /> Cadastrar
      </Button>
    </form>
  )
}

// ---------- Success screen ----------

function SuccessScreen({ onBackToLogin }) {
  return (
    <div className="text-center py-4">
      <div className="inline-flex h-14 w-14 items-center justify-center rounded-full bg-green-100 text-green-600 mb-4">
        <CheckCircle2 className="h-7 w-7" />
      </div>
      <h3 className="text-lg font-semibold text-foreground mb-2">Cadastro realizado!</h3>
      <p className="text-sm text-muted-foreground mb-6">
        Sua conta foi criada com sucesso. Voce ja pode fazer login com suas credenciais.
      </p>
      <Button onClick={onBackToLogin} className="w-full" size="lg">
        Ir para o login
      </Button>
    </div>
  )
}

// ---------- Main page ----------

export default function LoginPage() {
  const { user, loading } = useAuth()
  const [tab, setTab] = useState('login') // 'login' | 'register'
  const [step, setStep] = useState('form') // 'form' | 'success'

  useEffect(() => {
    document.title = tab === 'login'
      ? 'Entrar \u00b7 Fleet Intelligence'
      : 'Cadastro \u00b7 Fleet Intelligence'
  }, [tab])

  if (loading) return null
  if (user) return <Navigate to="/boards" replace />

  function handleRegisterSuccess() {
    setStep('success')
  }

  function handleBackToLogin() {
    setStep('form')
    setTab('login')
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center bg-background p-4 overflow-hidden">
      <div className="pointer-events-none absolute -top-32 -left-32 h-96 w-96 rounded-full bg-primary/20 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-32 -right-32 h-96 w-96 rounded-full bg-accent/20 blur-3xl" />

      <div className="absolute right-4 top-4">
        <ThemeToggle />
      </div>

      <div className="relative w-full max-w-md animate-slide-up">
        <div className="mb-8 text-center">
          <div className="inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-card mb-4">
            <Workflow className="h-7 w-7" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight">Fleet Intelligence</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Plataforma de workflow para gestao de frota
          </p>
        </div>

        <div className="rounded-xl border border-border bg-surface p-6 shadow-card">
          {step === 'form' && (
            <>
              <div className="mb-6 flex gap-1 rounded-lg bg-muted/50 p-1">
                <TabButton active={tab === 'login'} onClick={() => setTab('login')}>
                  Entrar
                </TabButton>
                <TabButton active={tab === 'register'} onClick={() => setTab('register')}>
                  Cadastrar
                </TabButton>
              </div>

              {tab === 'login'
                ? <LoginForm />
                : <RegisterForm onSuccess={handleRegisterSuccess} />
              }
            </>
          )}

          {step === 'success' && (
            <SuccessScreen onBackToLogin={handleBackToLogin} />
          )}
        </div>

        <p className="mt-6 text-center text-xs text-muted-foreground">
          Veneza Fleet &middot; &copy; {new Date().getFullYear()}
        </p>
      </div>
    </div>
  )
}
