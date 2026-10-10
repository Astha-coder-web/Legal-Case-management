import { useAuth } from '../Auth/useAuth.js'

function Login() {
  const { user, notice, error, busy, login, showSignup } = useAuth()

  function handleSubmit(event) {
    event.preventDefault()
    const formData = new FormData(event.currentTarget)
    login({
      email: formData.get('email').trim(),
      password: formData.get('password'),
    })
  }

  return (
    <div className="auth-form-wrap">
      <span className="eyebrow form-eyebrow">YOUR WORKSPACE AWAITS</span>
      <h2 className="form-title">Welcome back<span>.</span></h2>
      <p className="form-intro">Sign in to pick up right where you left off.</p>

      {notice && <p className="form-notice" role="status">{notice}</p>}
      {error && <p className="form-error" role="alert">{error}</p>}

      <form className="auth-form" onSubmit={handleSubmit}>
        <label className="field-label" htmlFor="login-email">Email address</label>
        <input
          className="auth-input"
          id="login-email"
          name="email"
          type="email"
          autoComplete="email"
          placeholder="you@example.com"
          defaultValue={user?.email || ''}
          required
        />

        <label className="field-label" htmlFor="login-password">Password</label>
        <input
          className="auth-input"
          id="login-password"
          name="password"
          type="password"
          autoComplete="current-password"
          placeholder="Enter your password"
          required
        />

        <button className="primary-button" type="submit" disabled={busy}>
          <span>{busy ? 'Signing in…' : 'Sign in to your account'}</span><span aria-hidden="true">↗</span>
        </button>
      </form>

      <p className="form-switch">
        New to LegalSmart? <button className="text-button switch-link" onClick={showSignup}>Create an account <span aria-hidden="true">→</span></button>
      </p>
      <p className="demo-note">Your session is protected with a secure, server-verified token.</p>
    </div>
  )
}

export default Login