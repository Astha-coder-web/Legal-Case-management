import { useState } from 'react'
import { useAuth } from '../Auth/useAuth.js'

function Signup() {
  const [error, setError] = useState('')
  const { signup, showLogin, error: requestError, busy } = useAuth()

  function handleSubmit(event) {
    event.preventDefault()
    const formData = new FormData(event.currentTarget)
    const password = formData.get('password')
    const confirmPassword = formData.get('confirm-password')

    if (password !== confirmPassword) {
      setError('Those passwords do not match. Please try again.')
      return
    }

    setError('')
    signup({
      name: formData.get('full-name').trim(),
      email: formData.get('email').trim(),
      password,
    })
  }

  return (
    <div className="auth-form-wrap signup-wrap">
      <span className="eyebrow form-eyebrow">A FRESH START</span>
      <h2 className="form-title">Create your<br />account<span>.</span></h2>
      <p className="form-intro">Set up your LegalSmart workspace in just a moment.</p>

      {error && <p className="form-error" role="alert">{error}</p>}
      {requestError && <p className="form-error" role="alert">{requestError}</p>}

      <form className="auth-form signup-form" onSubmit={handleSubmit}>
        <label className="field-label" htmlFor="signup-name">Full name</label>
        <input
          className="auth-input"
          id="signup-name"
          name="full-name"
          type="text"
          autoComplete="name"
          placeholder="Your name"
          required
        />

        <label className="field-label" htmlFor="signup-email">Email address</label>
        <input
          className="auth-input"
          id="signup-email"
          name="email"
          type="email"
          autoComplete="email"
          placeholder="you@example.com"
          required
        />

        <label className="field-label" htmlFor="signup-password">Create password</label>
        <input
          className="auth-input"
          id="signup-password"
          name="password"
          type="password"
          autoComplete="new-password"
          placeholder="At least 8 characters"
          minLength={8}
          required
        />

        <label className="field-label" htmlFor="confirm-password">Confirm password</label>
        <input
          className="auth-input"
          id="confirm-password"
          name="confirm-password"
          type="password"
          autoComplete="new-password"
          placeholder="Enter your password again"
          minLength={8}
          required
        />

        <button className="primary-button" type="submit" disabled={busy}>
          <span>{busy ? 'Creating account…' : 'Create your account'}</span><span aria-hidden="true">↗</span>
        </button>
      </form>

      <p className="form-switch">
        Already have an account? <button className="text-button switch-link" onClick={showLogin}>Sign in <span aria-hidden="true">→</span></button>
      </p>
      <p className="demo-note">Your password is securely hashed before it is stored.</p>
    </div>
  )
}

export default Signup