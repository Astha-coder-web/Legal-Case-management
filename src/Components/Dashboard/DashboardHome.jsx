import { useState } from 'react'

function dateKey(date) {
  return [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, '0'),
    String(date.getDate()).padStart(2, '0'),
  ].join('-')
}

function formatDate(value, options = { dateStyle: 'medium' }) {
  return new Intl.DateTimeFormat(undefined, options).format(new Date(value))
}

function caseColor(item, hearingDay, today) {
  if (item.status === 'closed') return 'previous'
  if (hearingDay < today) return 'missed'
  return item.status === 'pending' ? 'pending' : 'active'
}

function statusLabel(item, hearingDay, today) {
  const color = caseColor(item, hearingDay, today)
  if (color === 'previous') return 'Closed'
  if (color === 'missed') return 'Missed'
  return color === 'pending' ? 'Pending' : 'Active'
}

export default function DashboardHome({
  cases,
  clients,
  payments,
  onNavigate,
  onEditCase,
}) {
  const [now] = useState(() => new Date())
  const [displayedMonth, setDisplayedMonth] = useState(
    () => new Date(now.getFullYear(), now.getMonth(), 1),
  )
  const [selectedDate, setSelectedDate] = useState('')
  const [selectedCase, setSelectedCase] = useState(null)
  const today = dateKey(now)
  const monthStart = new Date(
    displayedMonth.getFullYear(),
    displayedMonth.getMonth(),
    1,
  )
  const gridStart = new Date(
    monthStart.getFullYear(),
    monthStart.getMonth(),
    1 - monthStart.getDay(),
  )
  const calendarDays = Array.from({ length: 42 }, (_, index) => {
    const date = new Date(
      gridStart.getFullYear(),
      gridStart.getMonth(),
      gridStart.getDate() + index,
    )
    return {
      date,
      key: dateKey(date),
      inMonth: date.getMonth() === displayedMonth.getMonth(),
    }
  })
  const casesByDate = cases.reduce((groupedCases, item) => {
    const key = dateKey(new Date(item.hearing_at))
    groupedCases[key] = [...(groupedCases[key] || []), item]
    return groupedCases
  }, {})
  const selectedDateCases = casesByDate[selectedDate] || []
  const pendingCents = payments
    .filter((payment) => payment.status === 'pending')
    .reduce((total, payment) => total + payment.amount_cents, 0)

  function moveMonth(offset) {
    setDisplayedMonth(
      (month) => new Date(month.getFullYear(), month.getMonth() + offset, 1),
    )
    setSelectedDate('')
  }

  function selectDate(key) {
    setSelectedDate(key)
    const dateCases = casesByDate[key] || []
    if (dateCases.length === 1) setSelectedCase(dateCases[0])
  }

  return (
    <div className="workspace-page overview-page">
      <div className="page-intro">
        <div className="page-intro-copy">
          <span className="eyebrow">YOUR MATTERS</span>
          <h2>Case calendar</h2>
          <p>Hearings and case dates at a glance. Select a date or case to view its details.</p>
        </div>
        <button
          className="primary-button compact-button"
          onClick={() => onNavigate('create-case')}
          type="button"
        >
          <span>New case</span><span aria-hidden="true">+</span>
        </button>
      </div>

      <section aria-label="Case calendar" className="content-card case-calendar">
        <div className="calendar-toolbar">
          <div>
            <span className="eyebrow">SCHEDULE</span>
            <h3>{formatDate(displayedMonth, { month: 'long', year: 'numeric' })}</h3>
          </div>
          <div className="calendar-navigation">
            <button aria-label="Previous month" onClick={() => moveMonth(-1)} type="button">‹</button>
            <button onClick={() => {
              setDisplayedMonth(new Date(now.getFullYear(), now.getMonth(), 1))
              setSelectedDate('')
            }} type="button">Today</button>
            <button aria-label="Next month" onClick={() => moveMonth(1)} type="button">›</button>
          </div>
        </div>

        <div className="calendar-legend" aria-label="Case status legend">
          <span><i className="calendar-dot calendar-dot-active" />Active</span>
          <span><i className="calendar-dot calendar-dot-missed" />Missed hearing</span>
          <span><i className="calendar-dot calendar-dot-pending" />Pending</span>
          <span><i className="calendar-dot calendar-dot-previous" />Closed / previous</span>
        </div>

        <div className="calendar-grid-scroll">
          <div className="calendar-grid" role="grid" aria-label={formatDate(displayedMonth, { month: 'long', year: 'numeric' })}>
            {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((day) => (
              <div className="calendar-weekday" key={day} role="columnheader">{day}</div>
            ))}
            {calendarDays.map(({ date, key, inMonth }) => {
              const dayCases = casesByDate[key] || []
              return (
                <div
                  aria-selected={selectedDate === key}
                  className={`calendar-day${inMonth ? '' : ' is-outside'}${key === today ? ' is-today' : ''}${selectedDate === key ? ' is-selected' : ''}`}
                  key={key}
                  role="gridcell"
                >
                  <button
                    aria-label={`${formatDate(date)}${dayCases.length ? `, ${dayCases.length} ${dayCases.length === 1 ? 'case' : 'cases'}` : ''}`}
                    className="calendar-date-button"
                    onClick={() => selectDate(key)}
                    type="button"
                  >
                    {date.getDate()}
                  </button>
                  <div className="calendar-day-cases">
                    {dayCases.slice(0, 2).map((item) => {
                      const color = caseColor(item, key, today)
                      return (
                        <button
                          className={`calendar-case calendar-case-${color}`}
                          key={item.id}
                          onClick={() => setSelectedCase(item)}
                          title={`${item.case_name} · ${statusLabel(item, key, today)}`}
                          type="button"
                        >
                          {item.case_number ? `${item.case_number} · ` : ''}{item.case_name}
                        </button>
                      )
                    })}
                    {dayCases.length > 2 && (
                      <button className="calendar-more" onClick={() => selectDate(key)} type="button">
                        +{dayCases.length - 2} more
                      </button>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
        {selectedDate && selectedDateCases.length > 1 && (
          <div className="selected-day-cases">
            <div>
              <span className="eyebrow">CASES ON THIS DATE</span>
              <h4>{formatDate(`${selectedDate}T12:00:00`)}</h4>
            </div>
            {selectedDateCases.map((item) => (
              <button
                className="selected-day-case"
                key={item.id}
                onClick={() => setSelectedCase(item)}
                type="button"
              >
                <span className={`calendar-dot calendar-dot-${caseColor(item, selectedDate, today)}`} />
                <span>{item.case_number ? `${item.case_number} · ` : ''}{item.case_name}</span>
                <span>{formatDate(item.hearing_at, { timeStyle: 'short' })}</span>
              </button>
            ))}
          </div>
        )}
        {selectedDate && selectedDateCases.length === 0 && (
          <p className="calendar-no-cases">{formatDate(`${selectedDate}T12:00:00`)} · No cases scheduled.</p>
        )}
      </section>

      <div className="overview-stats">
        <article className="stat-card">
          <span className="stat-label">ALL MATTERS</span>
          <strong>{cases.length}</strong>
          <button type="button" onClick={() => onNavigate('cases')}>View all cases <span aria-hidden="true">→</span></button>
        </article>
        <article className="stat-card">
          <span className="stat-label">CLIENTS</span>
          <strong>{clients.length}</strong>
          <button type="button" onClick={() => onNavigate('clients')}>View directory <span aria-hidden="true">→</span></button>
        </article>
        <article className="stat-card">
          <span className="stat-label">PENDING PAYMENTS</span>
          <strong>{new Intl.NumberFormat(undefined, {
            style: 'currency',
            currency: 'USD',
            maximumFractionDigits: 0,
          }).format(pendingCents / 100)}</strong>
          <button type="button" onClick={() => onNavigate('payments')}>Open ledger <span aria-hidden="true">→</span></button>
        </article>
      </div>

      {selectedCase && (
        <div className="case-dialog-backdrop" onClick={() => setSelectedCase(null)}>
          <section
            aria-labelledby="case-dialog-title"
            aria-modal="true"
            className="case-dialog content-card"
            onClick={(event) => event.stopPropagation()}
            role="dialog"
          >
            <div className="case-dialog-header">
              <div>
                <span className="eyebrow">CASE DETAILS</span>
                <h3 id="case-dialog-title">{selectedCase.case_name}</h3>
              </div>
              <button aria-label="Close case details" className="case-dialog-close" onClick={() => setSelectedCase(null)} type="button">×</button>
            </div>
            <dl className="case-detail-grid">
              {selectedCase.case_number && <div><dt>Case number</dt><dd>{selectedCase.case_number}</dd></div>}
              <div><dt>Client</dt><dd>{selectedCase.client_name}</dd></div>
              <div><dt>Case type</dt><dd>{selectedCase.case_type || 'Other'}</dd></div>
              <div><dt>Status</dt><dd>{statusLabel(selectedCase, dateKey(new Date(selectedCase.hearing_at)), today)}</dd></div>
              {selectedCase.court_name && <div><dt>Court</dt><dd>{selectedCase.court_name}</dd></div>}
              <div><dt>Hearing</dt><dd>{formatDate(selectedCase.hearing_at, { dateStyle: 'medium', timeStyle: 'short' })}</dd></div>
              {selectedCase.notes && <div className="case-detail-notes"><dt>Notes</dt><dd>{selectedCase.notes}</dd></div>}
            </dl>
            {selectedCase.attachments?.length > 0 && (
              <div className="case-detail-attachments">
                <strong>Attachments</strong>
                {selectedCase.attachments.map((attachment) => (
                  <a href={`/api/cases/${selectedCase.id}/attachments/${attachment.id}`} key={attachment.id} rel="noreferrer" target="_blank">
                    {attachment.filename}
                  </a>
                ))}
              </div>
            )}
            <div className="form-actions">
              <button className="secondary-button" onClick={() => setSelectedCase(null)} type="button">Close</button>
              <button className="primary-button compact-button" onClick={() => {
                setSelectedCase(null)
                onEditCase(selectedCase)
              }} type="button">Edit case</button>
            </div>
          </section>
        </div>
      )}
    </div>
  )
}
