import { useEffect, useState } from 'react'
import { useAuth } from './Auth/useAuth.js'
import Login from './Components/Login.jsx'
import Signup from './Components/Signup.jsx'
import ThemeToggle from './Components/ThemeToggle.jsx'
import Dashboard from './Components/Dashboard/Dashboard.jsx'
import './App.css'

function App() {
  const { page, isCheckingSession } = useAuth()
  const [theme, setTheme] = useState(() => {
    try {
      return window.localStorage.getItem('legalsmart-theme') === 'dark' ? 'dark' : 'light'
    } catch {
      return 'light'
    }
  })

  function toggleTheme() {
    setTheme((currentTheme) => currentTheme === 'dark' ? 'light' : 'dark')
  }

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    document.documentElement.style.colorScheme = theme
    try {
      window.localStorage.setItem('legalsmart-theme', theme)
    } catch {
      // The selected theme still applies for this session when storage is unavailable.
    }
  }, [theme])

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
    return <Dashboard onToggleTheme={toggleTheme} theme={theme} />
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
          <ThemeToggle onToggle={toggleTheme} theme={theme} />
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
