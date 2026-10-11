import { useState } from 'react'

function money(cents, currency) {
  return new Intl.NumberFormat(undefined, {
    style: 'currency',
    currency,
  }).format(cents / 100)
}

export default function PaymentsPage({ payments, onSave, busy }) {
  const [isAdding, setIsAdding] = useState(false)

  function handleSubmit(event) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const dueAt = form.get('due-at')
    onSave({
      description: form.get('description').trim(),
      amount_cents: Math.round(Number(form.get('amount')) * 100),
      currency: 'USD',
      due_at: dueAt ? new Date(dueAt).toISOString() : null,
      status: form.get('status'),
    }, () => setIsAdding(false))
  }

  return (
    <div className="workspace-page">
      <div className="page-heading page-heading-row">
        <div>
          <span className="eyebrow">A CLEARER VIEW OF YOUR FEES</span>
          <h2>Payment ledger<span>.</span></h2>
          <p>Track payment records. This ledger does not process card payments.</p>
        </div>
        <button className="primary-button compact-button" onClick={() => setIsAdding(!isAdding)} type="button">
          <span>{isAdding ? 'Close form' : 'Add payment'}</span><span aria-hidden="true">{isAdding ? '−' : '+'}</span>
        </button>
      </div>
      {isAdding && (
        <form className="workspace-form content-card compact-form" onSubmit={handleSubmit}>
          <label className="workspace-field">
            <span>Description</span>
            <input maxLength={160} name="description" placeholder="e.g. Initial consultation" required />
          </label>
          <div className="form-field-row">
            <label className="workspace-field">
              <span>Amount (USD)</span>
              <input min="0.01" name="amount" placeholder="0.00" required step="0.01" type="number" />
            </label>
            <label className="workspace-field">
              <span>Due date <small>Optional</small></span>
              <input name="due-at" type="datetime-local" />
            </label>
          </div>
          <label className="workspace-field">
            <span>Status</span>
            <select defaultValue="pending" name="status">
              <option value="pending">Pending</option>
              <option value="paid">Paid</option>
            </select>
          </label>
          <button className="primary-button compact-button" disabled={busy} type="submit">
            <span>{busy ? 'Saving…' : 'Save payment record'}</span><span aria-hidden="true">↗</span>
          </button>
        </form>
      )}
      {payments.length ? (
        <div className="content-card ledger-card">
          <div className="ledger-header"><span>DESCRIPTION</span><span>DATE</span><span>AMOUNT</span><span>STATUS</span></div>
          {payments.map((payment) => (
            <article className="ledger-row" key={payment.id}>
              <strong>{payment.description}</strong>
              <time dateTime={payment.due_at || payment.created_at}>
                {new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(new Date(payment.due_at || payment.created_at))}
              </time>
              <span>{money(payment.amount_cents, payment.currency)}</span>
              <span className={`payment-status payment-${payment.status}`}>{payment.status}</span>
            </article>
          ))}
        </div>
      ) : (
        !isAdding && (
          <div className="content-card empty-state">
            <span className="empty-mark" aria-hidden="true">$</span>
            <h4>Your ledger, at a glance.</h4>
            <p>Add a record to keep track of payments and outstanding fees.</p>
            <button className="primary-button compact-button" onClick={() => setIsAdding(true)} type="button">
              <span>Add a payment record</span><span aria-hidden="true">↗</span>
            </button>
          </div>
        )
      )}
    </div>
  )
}
