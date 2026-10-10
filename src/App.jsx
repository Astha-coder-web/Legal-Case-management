import { useEffect } from 'react'
import { useAuth } from './Auth/useAuth.js'
import Login from './Components/Login.jsx'
import Signup from './Components/Signup.jsx'
import './App.css'

function App() {
  const { page, user, error, busy, isCheckingSession, logout } = useAuth()

  useEffect(() => {
    document.title = page === 'dashboard'
      ? 'Dashboard | LegalSmart'
      : page === 'signup'
        ? 'Create account | LegalSmart'
        : 'Sign in | LegalSmart'
  }, [page])

  if (isCheckingSession) {
    return <main className="session-loading" aria-live="polite">Checking your secure session…</main>
  }

  if (page === 'dashboard') {
    return (
      <main className="dashboard">
        <header className="dashboard-header">
          <a className="brand" href="#dashboard" aria-label="LegalSmart home">
            <span className="brand-mark" aria-hidden="true">L</span>
            <span>Legal<span className="brand-light">Smart</span></span>
          </a>
          <button className="text-button dashboard-logout" onClick={logout} disabled={busy}>
            {busy ? 'Signing out…' : 'Sign out'}
          </button>
        </header>
        <section className="dashboard-content" id="dashboard">
          <span className="eyebrow">YOUR LEGAL WORKSPACE</span>
          <h1>Good to see you, {user?.name || 'there'}.</h1>
          <p className="dashboard-intro">
            Your cases, documents, and next steps will have a home here.
          </p>
          {error && <p className="form-error" role="alert">{error}</p>}
          <div className="dashboard-card">
            <span className="dashboard-card-icon" aria-hidden="true">✦</span>
            <div>
              <h2>Your workspace is ready</h2>
              <p>You’re signed in as {user?.email}. Connect your case data to get started.</p>
            </div>
          </div>
        </section>
        <footer className="dashboard-footer">A clearer way forward. <span>© 2025 LegalSmart</span></footer>
      </main>
    )
  }

  return (
    <main className="auth-page">
      <aside className="auth-visual" aria-label="LegalSmart introduction">
        <div className="visual-topline">
          <a className="brand brand-on-dark" href="#home" aria-label="LegalSmart home">
            <span className="brand-mark" aria-hidden="true">L</span>
            <span>Legal<span className="brand-light">Smart</span></span>
          </a>
          <span className="secure-label"><span aria-hidden="true">✳</span> YOUR SPACE, SECURED</span>
        </div>
        <div className="visual-copy" id="home">
          <span className="eyebrow visual-eyebrow">CLARITY IN EVERY CASE</span>
          <h1>Make room<br />for <em>what matters.</em></h1>
          <p>Bring your legal work into focus. A thoughtful workspace for your cases, documents, and the people behind them.</p>
          <div className="visual-rule"><span></span><span></span><span></span></div>
          <span className="visual-caption">A little more clarity. A lot more confidence.</span>
        </div>
        <div className="visual-bottom">
          <span>BUILT FOR YOUR NEXT CHAPTER</span>
          <span>01 — 03</span>
        </div>
      </aside>

      <section className="auth-panel">
        <div className="auth-panel-top">
          <span>WELCOME TO LEGALSMART</span>
          <span className="panel-dot" aria-hidden="true"></span>
        </div>
        {page === 'signup' ? <Signup /> : <Login />}
        <footer className="auth-footer">
          <span>© 2025 LEGALSMART</span>
          <span>MADE FOR PEACE OF MIND</span>
        </footer>
      </section>
    </main>
  )
}

export default App
