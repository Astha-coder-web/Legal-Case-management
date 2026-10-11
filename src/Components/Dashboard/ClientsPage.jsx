import { useState } from 'react'

export default function ClientsPage({ clients, onSave, busy }) {
  const [isAdding, setIsAdding] = useState(false)
  const [query, setQuery] = useState('')
  const searchTerm = query.trim().toLocaleLowerCase()
  const filteredClients = clients.filter((client) => [
    client.name,
    client.email,
    client.phone,
    client.notes,
  ].some((value) => value?.toLocaleLowerCase().includes(searchTerm)))

  function handleSubmit(event) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    onSave({
      name: form.get('name').trim(),
      email: form.get('email').trim(),
      phone: form.get('phone').trim(),
      notes: form.get('notes').trim(),
    }, () => setIsAdding(false))
  }

  return (
    <div className="workspace-page">
      <div className="page-heading page-heading-row">
        <div>
          <span className="eyebrow">THE PEOPLE BEHIND THE MATTERS</span>
          <h2>All clients<span>.</span></h2>
          <p>Showing {filteredClients.length} of {clients.length} {clients.length === 1 ? 'client' : 'clients'} in your private directory.</p>
        </div>
        <button className="primary-button compact-button" onClick={() => setIsAdding(!isAdding)} type="button">
          <span>{isAdding ? 'Close form' : 'Add client'}</span><span aria-hidden="true">{isAdding ? '−' : '+'}</span>
        </button>
      </div>
      {clients.length > 0 && (
        <label className="directory-search">
          <span aria-hidden="true">⌕</span>
          <input
            aria-label="Search clients"
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search by name, email, phone, or notes"
            type="search"
            value={query}
          />
          {query && <button aria-label="Clear client search" onClick={() => setQuery('')} type="button">×</button>}
        </label>
      )}
      {isAdding && (
        <form className="workspace-form content-card compact-form" onSubmit={handleSubmit}>
          <label className="workspace-field">
            <span>Full name</span>
            <input autoComplete="name" maxLength={100} name="name" required />
          </label>
          <div className="form-field-row">
            <label className="workspace-field">
              <span>Email address</span>
              <input autoComplete="email" maxLength={254} name="email" type="email" />
            </label>
            <label className="workspace-field">
              <span>Phone number</span>
              <input autoComplete="tel" maxLength={40} name="phone" type="tel" />
            </label>
          </div>
          <label className="workspace-field">
            <span>Notes</span>
            <textarea maxLength={2000} name="notes" rows={2} />
          </label>
          <button className="primary-button compact-button" disabled={busy} type="submit">
            <span>{busy ? 'Saving…' : 'Save client'}</span><span aria-hidden="true">↗</span>
          </button>
        </form>
      )}
      {filteredClients.length ? (
        <div className="client-list">
          {filteredClients.map((client) => (
            <article className="content-card client-card" key={client.id}>
              <span className="client-avatar" aria-hidden="true">{client.name.charAt(0).toUpperCase()}</span>
              <div className="client-details">
                <h3>{client.name}</h3>
                {client.email && <a href={`mailto:${client.email}`}>{client.email}</a>}
                {client.phone && <a href={`tel:${client.phone}`}>{client.phone}</a>}
                {client.notes && <p>{client.notes}</p>}
              </div>
            </article>
          ))}
        </div>
      ) : clients.length ? (
        <div className="content-card empty-state">
          <span className="empty-mark" aria-hidden="true">⌕</span>
          <h4>No matching clients found.</h4>
          <p>Try a different name, email address, phone number, or search term.</p>
          <button className="secondary-button" onClick={() => setQuery('')} type="button">Clear search</button>
        </div>
      ) : (
        !isAdding && (
          <div className="content-card empty-state">
            <span className="empty-mark" aria-hidden="true">♧</span>
            <h4>Your client directory starts here.</h4>
            <p>Add a client to keep their contact details close to their matters.</p>
            <button className="primary-button compact-button" onClick={() => setIsAdding(true)} type="button">
              <span>Add your first client</span><span aria-hidden="true">↗</span>
            </button>
          </div>
        )
      )}
    </div>
  )
}
