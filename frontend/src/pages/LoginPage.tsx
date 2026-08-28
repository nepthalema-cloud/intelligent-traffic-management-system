import { type FormEvent, useEffect, useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import { GlassCard } from '@/components/ui/GlassCard'
import { TextInput } from '@/components/ui/TextInput'
import { PasswordInput } from '@/components/ui/PasswordInput'
import { PrimaryButton } from '@/components/ui/PrimaryButton'
import { SecondaryButton } from '@/components/ui/SecondaryButton'

export function LoginPage() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const { login, isLoading, error, isAuthenticated, clearError } = useAuthStore()
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: { pathname: string } })?.from?.pathname ?? '/dashboard'

  useEffect(() => {
    if (isAuthenticated) {
      navigate(from, { replace: true })
    }
  }, [isAuthenticated, navigate, from])

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    clearError()
    await login(username, password)
  }

  function fillDemo() {
    clearError()
    setUsername('Admin')
    setPassword('admin1234')
  }

  return (
    <div className="min-h-screen lg:flex bg-[radial-gradient(circle_at_top_left,rgba(33,212,253,0.12),transparent_14%),linear-gradient(180deg,#050B16_0%,#020613_100%)]">
      <aside className="hidden lg:flex lg:w-1/2 relative overflow-hidden">
        <div
          className="absolute inset-0 bg-cover bg-center"
          style={{ backgroundImage: "url('/login-hero.png')" }}
        />
        <div className="absolute inset-0 bg-slate-950/15" />
        <div className="absolute inset-0 bg-linear-to-b from-transparent via-slate-950/10 to-slate-950/80" />
      </aside>

      <main className="flex flex-1 items-center justify-center px-6 py-10 sm:px-8 lg:px-14">
        <GlassCard className="w-full max-w-2xl ring-1 ring-white/10">
          <div className="space-y-8">
            <div className="space-y-4 text-center">
              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full border border-cyan-400/20 bg-slate-950/70 shadow-[0_20px_50px_rgba(33,212,253,0.16)]">
                <svg viewBox="0 0 24 24" className="h-8 w-8 text-cyan-300" fill="none" stroke="currentColor" strokeWidth="1.6">
                  <path d="M12 3l9 5-9 5-9-5 9-5Zm0 7v11" />
                  <path d="M3 8.5v6c0 1.2.7 2.3 1.8 2.8L12 21l7.2-3.7A2.8 2.8 0 0 0 21 14.5v-6" />
                </svg>
              </div>
              <p className="text-sm uppercase tracking-[0.34em] text-cyan-200/80">TrafficOps</p>
              <h1 className="text-4xl font-semibold tracking-tight text-white sm:text-5xl">
                AI-Powered Smart Traffic Operations
              </h1>
              <p className="mx-auto max-w-lg text-sm leading-7 text-slate-300/85">
                Sign in to access your secure enterprise traffic command center.
              </p>
            </div>

            {error && (
              <div className="rounded-[22px] border border-rose-400/15 bg-rose-400/10 px-4 py-3 text-sm text-rose-100">
                {error}
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-6">
              <div className="space-y-4">
                <TextInput
                  id="username"
                  name="username"
                  label="Username"
                  value={username}
                  onChange={e => setUsername(e.target.value)}
                  placeholder="admin"
                  required
                />
                <PasswordInput
                  id="password"
                  name="password"
                  label="Password"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  required
                />
              </div>

              <PrimaryButton type="submit" disabled={isLoading} className="h-14">
                {isLoading ? 'Signing in…' : 'Sign in'}
              </PrimaryButton>
            </form>

            <div className="rounded-[22px] border border-white/10 bg-slate-950/70 px-5 py-4 text-sm text-slate-300">
              <div className="text-xs uppercase tracking-[0.32em] text-slate-400">Demo Account</div>
              <div className="mt-3 space-y-1">
                <p className="text-slate-100"><span className="font-semibold">Username:</span> Admin</p>
                <p className="text-slate-100"><span className="font-semibold">Password:</span> admin1234</p>
              </div>
              <div className="mt-4">
                <SecondaryButton type="button" onClick={fillDemo}>
                  Fill demo credentials
                </SecondaryButton>
              </div>
            </div>

            <p className="text-center text-xs uppercase tracking-[0.3em] text-slate-500">
              Access restricted to authorised personnel only
            </p>
          </div>
        </GlassCard>
      </main>
    </div>
  )
}
