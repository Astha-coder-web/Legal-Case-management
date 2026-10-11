import { useCallback, useEffect, useRef, useState } from 'react'
import { useAuth } from '../../Auth/useAuth.js'
import { authRequest } from '../../Auth/authApi.js'
import CasesPage from './CasesPage.jsx'
import ClientsPage from './ClientsPage.jsx'
import CreateCasePage from './CreateCasePage.jsx'
import DashboardHome from './DashboardHome.jsx'
import DictionaryPage from './DictionaryPage.jsx'
import PaymentsPage from './PaymentsPage.jsx'
import Sidebar from './Sidebar.jsx'
import ThemeToggle from '../ThemeToggle.jsx'
import './dashboard.css'

const pageTitles = {
  overview: 'Overview',
  'create-case': 'Create a case',
  cases: 'All cases',
  payments: 'Payment ledger',
  clients: 'All clients',
  dictionary: 'Legal dictionary',
}

export default function Dashboard({ theme, onToggleTheme }) {
  const { user, error: authError, busy: authBusy, logout } = useAuth()
  const [page, setPage] = useState('overview')
  const [cases, setCases] = useState([])
  const [editingCase, setEditingCase] = useState(null)
  const [clients, setClients] = useState([])
  const [payments, setPayments] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [reminderMessage, setReminderMessage] = useState('')
  const [notificationPermission, setNotificationPermission] = useState(
    () => ('Notification' in window ? Notification.permission : 'unsupported'),
  )
  const handledReminders = useRef(new Set())

  const loadWorkspace = useCallback(async () => {
    const [loadedCases, loadedClients, loadedPayments] = await Promise.all([
      authRequest('/api/cases'),
      authRequest('/api/clients'),
      authRequest('/api/payments'),
    ])
    setCases(loadedCases)
    setClients(loadedClients)
    setPayments(loadedPayments)
  }, [])

  useEffect(() => {
    let mounted = true
    async function load() {
      try {
        await loadWorkspace()
      } catch (loadError) {
        if (mounted) setError(loadError.message)
      } finally {
        if (mounted) setLoading(false)
      }
    }
    load()
    return () => {
      mounted = false
    }
  }, [loadWorkspace])

  useEffect(() => {
    let mounted = true
    async function checkReminders() {
      try {
        const reminders = await authRequest('/api/reminders/pending')
        for (const reminder of reminders) {
          if (!mounted || handledReminders.current.has(reminder.id)) continue
          handledReminders.current.add(reminder.id)
          const title = `Hearing reminder: ${reminder.case_name}`
          const time = new Intl.DateTimeFormat(undefined, {
            dateStyle: 'medium',
            timeStyle: 'short',
          }).format(new Date(reminder.hearing_at))
          const message = `${reminder.client_name} · ${time}`
          setReminderMessage(`${title} — ${message}`)
          if ('Notification' in window && Notification.permission === 'granted') {
            new Notification(title, { body: message, tag: reminder.id })
          }
          await authRequest(`/api/reminders/${reminder.id}/delivered`, {
            method: 'POST',
          })
        }
      } catch (reminderError) {
        if (mounted) setError(reminderError.message)
      }
    }
    checkReminders()
    const interval = window.setInterval(checkReminders, 10000)
    return () => {
      mounted = false
      window.clearInterval(interval)
    }
  }, [])

  async function enableNotifications() {
    if (!('Notification' in window)) {
      setNotificationPermission('unsupported')
      return
    }
    const permission = await Notification.requestPermission()
    setNotificationPermission(permission)
    if (permission === 'granted') {
      setNotice('Browser reminders are enabled while this dashboard is open.')
      setError('')
    } else {
      setError('Notifications were not enabled. Keep this dashboard open to see reminder alerts here.')
    }
  }

  async function saveRecord(path, data, successMessage) {
    setSaving(true)
    setError('')
    setNotice('')
    try {
      await authRequest(path, {
        method: 'POST',
        body: JSON.stringify(data),
      })
      await loadWorkspace()
      setNotice(successMessage)
      return true
    } catch (saveError) {
      setError(saveError.message)
      return false
    } finally {
      setSaving(false)
    }
  }

  async function saveCase(data) {
    setSaving(true)
    setError('')
    setNotice('')
    const { attachments, ...caseFields } = data
    let savedCase
    try {
      savedCase = await authRequest(
        editingCase ? `/api/cases/${editingCase.id}` : '/api/cases',
        {
          method: editingCase ? 'PUT' : 'POST',
          body: JSON.stringify(caseFields),
        },
      )
    } catch (saveError) {
      setError(saveError.message)
      setSaving(false)
      return
    }

    try {
      if (attachments.length) {
        const formData = new FormData()
        attachments.forEach((file) => formData.append('files', file))
        await authRequest(`/api/cases/${savedCase.id}/attachments`, {
          method: 'POST',
          body: formData,
        })
      }
      await loadWorkspace()
      setNotice(editingCase ? 'Case updated.' : 'Case saved with its hearing reminder.')
      setEditingCase(null)
      setPage('cases')
    } catch (saveError) {
      try {
        await loadWorkspace()
      } catch (reloadError) {
        setError(`${saveError.message} The case list could not be refreshed: ${reloadError.message}`)
        setSaving(false)
        return
      }
      setEditingCase(null)
      setPage('cases')
      setError(`Case details were saved, but the image upload failed: ${saveError.message}`)
    } finally {
      setSaving(false)
    }
  }

  async function deleteCase(item) {
    if (!window.confirm(`Delete "${item.case_name}" and its attached images and reminder?`)) {
      return
    }
    setError('')
    setNotice('')
    try {
      await authRequest(`/api/cases/${item.id}`, { method: 'DELETE' })
      await loadWorkspace()
      setNotice('Case, attached images, and reminder deleted.')
    } catch (deleteError) {
      setError(deleteError.message)
    }
  }

  async function saveClient(data, onSaved) {
    if (await saveRecord('/api/clients', data, 'Client added to your directory.')) onSaved()
  }

  async function savePayment(data, onSaved) {
    if (await saveRecord('/api/payments', data, 'Payment record saved.')) onSaved()
  }

  function renderPage() {
    if (loading) {
      return <div className="workspace-loading" aria-live="polite">Loading your workspace…</div>
    }
    switch (page) {
      case 'create-case':
        return (
          <CreateCasePage
            busy={saving}
            caseItem={editingCase}
            clients={clients}
            onCancel={() => {
              setEditingCase(null)
              setPage('overview')
            }}
            onSave={saveCase}
          />
        )
      case 'cases':
        return (
          <CasesPage
            cases={cases}
            onCreate={() => {
              setEditingCase(null)
              setPage('create-case')
            }}
            onDelete={deleteCase}
            onEdit={(item) => {
              setEditingCase(item)
              setPage('create-case')
            }}
          />
        )
      case 'payments':
        return <PaymentsPage busy={saving} onSave={savePayment} payments={payments} />
      case 'clients':
        return <ClientsPage busy={saving} clients={clients} onSave={saveClient} />
      case 'dictionary':
        return <DictionaryPage />
      default:
        return (
          <DashboardHome
            cases={cases}
            clients={clients}
            onEditCase={(item) => {
              setEditingCase(item)
              setPage('create-case')
            }}
            onNavigate={setPage}
            payments={payments}
          />
        )
    }
  }

  return (
    <main className="workspace-shell">
      <header className="workspace-header">
        <div>
          <span className="workspace-brand"><span className="brand-mark" aria-hidden="true">L</span> Legal<span>Smart</span></span>
          <h1>Welcome, {user?.name || 'there'}</h1>
        </div>
        <div className="workspace-header-actions">
          <span className="header-page-label">{pageTitles[page]}</span>
          <ThemeToggle onToggle={onToggleTheme} theme={theme} />
          <button
            className={`notification-button${notificationPermission === 'granted' ? ' notification-enabled' : ''}`}
            disabled={notificationPermission === 'granted' || notificationPermission === 'unsupported'}
            onClick={enableNotifications}
            type="button"
          >
            <span aria-hidden="true">♧</span>
            {notificationPermission === 'granted' ? 'Reminders on' : 'Enable reminders'}
          </button>
          <button className="text-button dashboard-logout" disabled={authBusy} onClick={logout} type="button">
            {authBusy ? 'Signing out…' : 'Sign out'}
          </button>
        </div>
      </header>
      <div className="workspace-layout">
        <Sidebar onNavigate={setPage} page={page} />
        <section className="workspace-main" aria-label={pageTitles[page]}>
          {error && <p className="workspace-alert workspace-error" role="alert">{authError || error}</p>}
          {notice && <p className="workspace-alert workspace-success" role="status">{notice}</p>}
          {reminderMessage && (
            <div className="workspace-alert workspace-reminder" role="status">
              <span aria-hidden="true">✳</span>
              <span>{reminderMessage}</span>
              <button aria-label="Dismiss reminder" onClick={() => setReminderMessage('')} type="button">×</button>
            </div>
          )}
          {renderPage()}
        </section>
      </div>
      <footer className="workspace-footer">
        <span>Legal practice management</span>
        <span>© 2026 LegalSmart</span>
      </footer>
    </main>
  )
}
