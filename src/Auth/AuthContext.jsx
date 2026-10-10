import { useCallback, useEffect, useMemo, useState } from 'react'
import AuthContext from './authContextValue.js'
import { authRequest } from './authApi.js'

export function AuthProvider({ children }) {
  const [page, setPage] = useState('login')
  const [user, setUser] = useState(null)
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [isCheckingSession, setIsCheckingSession] = useState(true)

  useEffect(() => {
    let mounted = true

    async function restoreSession() {
      try {
        const restoredUser = await authRequest('/api/auth/me')
        if (mounted) {
          setUser(restoredUser)
          setPage('dashboard')
        }
      } catch (sessionError) {
        if (mounted && sessionError.status !== 401) {
          setError(sessionError.message)
        }
      } finally {
        if (mounted) setIsCheckingSession(false)
      }
    }

    restoreSession()
    return () => {
      mounted = false
    }
  }, [])

  const login = useCallback(async ({ email, password }) => {
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const authenticatedUser = await authRequest('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      })
      setUser(authenticatedUser)
      setPage('dashboard')
    } catch (loginError) {
      setError(loginError.message)
    } finally {
      setBusy(false)
    }
  }, [])

  const signup = useCallback(async ({ name, email, password }) => {
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const createdUser = await authRequest('/api/auth/signup', {
        method: 'POST',
        body: JSON.stringify({ name, email, password }),
      })
      setUser(createdUser)
      setNotice('Your account is ready. Sign in to continue.')
      setPage('login')
    } catch (signupError) {
      setError(signupError.message)
    } finally {
      setBusy(false)
    }
  }, [])

  const logout = useCallback(async () => {
    setBusy(true)
    setError('')
    try {
      await authRequest('/api/auth/logout', { method: 'POST' })
      setUser(null)
      setNotice('')
      setPage('login')
    } catch (logoutError) {
      setError(logoutError.message)
    } finally {
      setBusy(false)
    }
  }, [])

  const showLogin = useCallback(() => {
    setError('')
    setNotice('')
    setPage('login')
  }, [])

  const showSignup = useCallback(() => {
    setError('')
    setNotice('')
    setPage('signup')
  }, [])

  const value = useMemo(() => ({
    page,
    user,
    notice,
    error,
    busy,
    isCheckingSession,
    login,
    signup,
    logout,
    showLogin,
    showSignup,
  }), [
    page,
    user,
    notice,
    error,
    busy,
    isCheckingSession,
    login,
    signup,
    logout,
    showLogin,
    showSignup,
  ])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
