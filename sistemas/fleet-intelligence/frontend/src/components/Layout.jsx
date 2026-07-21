import { useEffect, useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { LogOut, Workflow, Users, BarChart3, Bell } from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import { api } from '@/api/client'
import ThemeToggle from './ThemeToggle'
import { cn } from '@/lib/utils'

const NAV_ITEMS = [
  { to: '/boards', label: 'Fluxos', icon: Workflow },
  { to: '/alerts', label: 'Alertas', icon: Bell },
  { to: '/reports', label: 'Relatorios', icon: BarChart3, disabled: true },
  { to: '/users', label: 'Usuarios', icon: Users },
]

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [alertCount, setAlertCount] = useState(0)

  // Fetch alert count periodically
  useEffect(() => {
    function fetchCount() {
      api.get('/alerts/count?days=7')
        .then(({ data }) => setAlertCount(data.count))
        .catch(() => {})
    }
    fetchCount()
    const interval = setInterval(fetchCount, 60000) // every minute
    return () => clearInterval(interval)
  }, [])

  const handleLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }

  const initials = (user?.full_name || user?.username || '?')
    .split(' ')
    .map((s) => s[0])
    .filter(Boolean)
    .slice(0, 2)
    .join('')
    .toUpperCase()

  return (
    <div className="flex min-h-screen bg-background">
      {/* Sidebar */}
      <aside className="sticky top-0 flex h-screen w-60 flex-col border-r border-border bg-surface">
        <div className="flex h-16 items-center gap-2 px-5 border-b border-border">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground font-bold">
            FI
          </div>
          <div className="min-w-0">
            <div className="truncate text-sm font-semibold">Fleet Intelligence</div>
            <div className="truncate text-xs text-muted-foreground">Veneza</div>
          </div>
        </div>

        <nav className="flex-1 space-y-1 p-3">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon
            if (item.disabled) {
              return (
                <div
                  key={item.to}
                  className="flex items-center gap-3 rounded-md px-3 py-2 text-sm text-muted-foreground/60 cursor-not-allowed"
                  title="Em breve"
                >
                  <Icon className="h-4 w-4" />
                  <span>{item.label}</span>
                  <span className="ml-auto rounded-full bg-muted px-1.5 py-0.5 text-[10px] font-medium">
                    Em breve
                  </span>
                </div>
              )
            }
            return (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                    isActive
                      ? 'bg-primary/10 text-primary'
                      : 'text-foreground/80 hover:bg-muted hover:text-foreground',
                  )
                }
              >
                <Icon className="h-4 w-4" />
                {item.label}
                {item.to === '/alerts' && alertCount > 0 && (
                  <span className="ml-auto flex h-5 min-w-5 items-center justify-center rounded-full bg-destructive text-[10px] font-bold text-white px-1">
                    {alertCount > 99 ? '99+' : alertCount}
                  </span>
                )}
              </NavLink>
            )
          })}
        </nav>

        <div className="border-t border-border p-3">
          <div className="flex items-center gap-3 rounded-md px-2 py-2">
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-primary/15 text-primary text-sm font-semibold">
              {initials}
            </div>
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-medium">{user?.full_name}</div>
              <div className="truncate text-xs text-muted-foreground capitalize">
                {user?.role}
              </div>
            </div>
            <button
              onClick={handleLogout}
              aria-label="Sair"
              title="Sair"
              className="rounded-md p-2 text-muted-foreground hover:bg-muted hover:text-foreground transition-colors cursor-pointer"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 min-w-0">
        <header className="sticky top-0 z-10 flex h-16 items-center justify-end gap-2 border-b border-border bg-surface/80 px-6 backdrop-blur">
          {/* Alert bell in header */}
          <NavLink
            to="/alerts"
            className="relative rounded-md p-2 text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
            title="Alertas"
          >
            <Bell className="h-5 w-5" />
            {alertCount > 0 && (
              <span className="absolute -top-0.5 -right-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive text-[9px] font-bold text-white px-0.5">
                {alertCount > 99 ? '99+' : alertCount}
              </span>
            )}
          </NavLink>
          <ThemeToggle />
        </header>
        <div className="p-6">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
