import { useState } from 'react'

function formatDateTime(value) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

export default function CasesPage({ cases, onCreate, onEdit, onDelete }) {
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const searchTerm = query.trim().toLocaleLowerCase()
  const filteredCases = cases.filter((item) => {
    const matchesStatus = statusFilter === 'all'
      || (item.status || 'active').toLocaleLowerCase() === statusFilter
    const matchesSearch = [
      item.case_name,
      item.case_number,
      item.client_name,
      item.case_type,
      item.court_name,
      item.status,
      item.notes,
    ].some((value) => value?.toLocaleLowerCase().includes(searchTerm))

    return matchesStatus && matchesSearch
  })

  return (
    <div className="workspace-page">
      <div className="page-heading page-heading-row">
        <div>
          <span className="eyebrow">YOUR MATTERS</span>
          <h2>All cases<span>.</span></h2>
          <p>Showing {filteredCases.length} of {cases.length} {cases.length === 1 ? 'matter' : 'matters'} in your workspace.</p>
        </div>
        <div className="case-page-actions">
          <label className="case-status-filter">
            <span className="sr-only">Filter cases by status</span>
            <select
              aria-label="Filter cases by status"
              onChange={(event) => setStatusFilter(event.target.value)}
              value={statusFilter}
            >
              <option value="all">All statuses</option>
              <option value="active">Active</option>
              <option value="pending">Pending</option>
              <option value="closed">Closed</option>
            </select>
          </label>
          <button className="primary-button compact-button" onClick={onCreate} type="button">
            <span>New case</span><span aria-hidden="true">+</span>
          </button>
        </div>
      </div>
      {cases.length > 0 && (
        <label className="directory-search">
          <span aria-hidden="true">⌕</span>
          <input
            aria-label="Search cases"
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search by case, number, client, court, or notes"
            type="search"
            value={query}
          />
          {query && <button aria-label="Clear case search" onClick={() => setQuery('')} type="button">×</button>}
        </label>
      )}
      {filteredCases.length ? (
        <div className="case-list">
          {filteredCases.map((item) => (
            <article className="content-card case-card" key={item.id}>
              <div className="case-card-top">
                <span className="case-tag">{item.case_number || 'CASE'}</span>
                <time dateTime={item.hearing_at}>{formatDateTime(item.hearing_at)}</time>
              </div>
              <h3>{item.case_name}</h3>
              <p className="case-client"><span aria-hidden="true">♧</span> {item.client_name}</p>
              <div className="case-meta">
                <span>{item.case_type || 'Other'}</span>
                <span>{item.status || 'Active'}</span>
                {item.court_name && <span>{item.court_name}</span>}
              </div>
              {item.notes && <p className="case-notes">{item.notes}</p>}
              {item.attachments?.length > 0 && (
                <div className="case-attachments">
                  {item.attachments.map((attachment) => (
                    <a
                      href={`/api/cases/${item.id}/attachments/${attachment.id}`}
                      key={attachment.id}
                      rel="noreferrer"
                      target="_blank"
                    >
                      <span aria-hidden="true">▧</span> {attachment.filename}
                    </a>
                  ))}
                </div>
              )}
              <div className="case-actions">
                <button className="secondary-button" onClick={() => onEdit(item)} type="button">Edit case</button>
                <button className="case-delete-button" onClick={() => onDelete(item)} type="button">Delete case</button>
              </div>
            </article>
          ))}
        </div>
      ) : cases.length ? (
        <div className="content-card empty-state">
          <span className="empty-mark" aria-hidden="true">⌕</span>
          <h4>No matching cases found.</h4>
          <p>Try a different case name, number, client, court, or search term.</p>
          <button
            className="secondary-button"
            onClick={() => {
              setQuery('')
              setStatusFilter('all')
            }}
            type="button"
          >
            Clear filters
          </button>
        </div>
      ) : (
        <div className="content-card empty-state">
          <span className="empty-mark" aria-hidden="true">✳</span>
          <h4>Your cases will find a home here.</h4>
          <p>Create a case to add its details and schedule a hearing reminder.</p>
          <button className="primary-button compact-button" onClick={onCreate} type="button">
            <span>Create your first case</span><span aria-hidden="true">↗</span>
          </button>
        </div>
      )}
    </div>
  )
}
