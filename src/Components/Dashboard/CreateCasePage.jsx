import { useState } from 'react'

function localDateTime(value) {
  if (!value) return ''
  const date = new Date(value)
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16)
}

export default function CreateCasePage({
  clients,
  onSave,
  onCancel,
  busy,
  caseItem,
}) {
  const hasSavedClient = clients.some((client) => client.name === caseItem?.client_name)
  const [useCustomClient, setUseCustomClient] = useState(
    Boolean(caseItem?.client_name && !hasSavedClient),
  )

  function handleSubmit(event) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const localHearing = form.get('hearing-at')
    const clientChoice = form.get('client-choice')
    onSave({
      case_name: form.get('case-name').trim(),
      client_name: clientChoice === '__custom__'
        ? form.get('client-name').trim()
        : clientChoice,
      case_number: form.get('case-number').trim(),
      case_type: form.get('case-type'),
      court_name: form.get('court-name').trim(),
      status: form.get('status'),
      hearing_at: new Date(localHearing).toISOString(),
      hearing_timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC',
      notes: form.get('notes').trim(),
      attachments: form.getAll('attachments').filter((file) => file.size > 0),
    })
  }

  return (
    <div className="workspace-page">
      <div className="page-heading">
        <span className="eyebrow">{caseItem ? 'UPDATE YOUR MATTER' : 'A NEW MATTER'}</span>
        <h2>{caseItem ? 'Edit case' : 'Create a case'}<span>.</span></h2>
        <p>Add the key details and we’ll remind you when the hearing is due.</p>
      </div>
      <form className="workspace-form content-card" onSubmit={handleSubmit}>
        <label className="workspace-field">
          <span>Case name</span>
          <input autoComplete="off" defaultValue={caseItem?.case_name || ''} maxLength={160} name="case-name" placeholder="e.g. Patel v. Northwind" required />
        </label>
        <div className="form-field-row">
          <label className="workspace-field">
            <span>Case number <small>Optional</small></span>
            <input autoComplete="off" defaultValue={caseItem?.case_number || ''} maxLength={80} name="case-number" placeholder="e.g. 2026-CV-00123" />
          </label>
          <label className="workspace-field">
            <span>Case type</span>
            <select defaultValue={caseItem?.case_type || 'other'} name="case-type" required>
              <option value="criminal">Criminal</option>
              <option value="civil">Civil</option>
              <option value="family">Family</option>
              <option value="corporate">Corporate</option>
              <option value="property">Property</option>
              <option value="labor">Labor</option>
              <option value="consumer">Consumer</option>
              <option value="other">Other</option>
            </select>
          </label>
        </div>
        <label className="workspace-field">
          <span>Client name</span>
          <select
            defaultValue={useCustomClient ? '__custom__' : caseItem?.client_name || ''}
            name="client-choice"
            onChange={(event) => setUseCustomClient(event.target.value === '__custom__')}
            required
          >
            <option disabled value="">Choose a client</option>
            {clients.map((client) => <option key={client.id} value={client.name}>{client.name}</option>)}
            <option value="__custom__">Enter a client name</option>
          </select>
          {useCustomClient && (
            <input
              autoComplete="off"
              defaultValue={hasSavedClient ? '' : caseItem?.client_name || ''}
              maxLength={100}
              name="client-name"
              placeholder="Enter client name"
              required
            />
          )}
        </label>
        <div className="form-field-row">
          <label className="workspace-field">
            <span>Court name <small>Optional</small></span>
            <input autoComplete="off" defaultValue={caseItem?.court_name || ''} maxLength={160} name="court-name" placeholder="e.g. District Court" />
          </label>
          <label className="workspace-field">
            <span>Case status</span>
            <select defaultValue={caseItem?.status || 'active'} name="status" required>
              <option value="active">Active</option>
              <option value="pending">Pending</option>
              <option value="closed">Closed</option>
            </select>
          </label>
        </div>
        <div className="form-field-row">
          <label className="workspace-field">
            <span>Hearing date &amp; time</span>
            <input defaultValue={localDateTime(caseItem?.hearing_at)} name="hearing-at" type="datetime-local" required />
            <small>We’ll use your local time and convert it for your reminder.</small>
          </label>
        </div>
        <label className="workspace-field">
          <span>Notes <small>Optional</small></span>
          <textarea defaultValue={caseItem?.notes || ''} maxLength={4000} name="notes" placeholder="Add a note about this matter…" rows={4} />
        </label>
        {caseItem?.attachments?.length > 0 && (
          <div className="workspace-field">
            <span>Attached images</span>
            <div className="attached-image-list">
              {caseItem.attachments.map((attachment) => (
                <a
                  href={`/api/cases/${caseItem.id}/attachments/${attachment.id}`}
                  key={attachment.id}
                  rel="noreferrer"
                  target="_blank"
                >
                  {attachment.filename}
                </a>
              ))}
            </div>
          </div>
        )}
        <label className="workspace-field">
          <span>{caseItem ? 'Attach more images' : 'Attach images'} <small>Optional</small></span>
          <input accept="image/*" multiple name="attachments" type="file" />
          <small>Image formats supported. Files stream to MongoDB GridFS; total upload size depends on available server and database storage.</small>
        </label>
        <div className="form-actions">
          <button className="secondary-button" onClick={onCancel} type="button">Cancel</button>
          <button className="primary-button compact-button" disabled={busy} type="submit">
            <span>{busy ? 'Saving case…' : caseItem ? 'Save changes' : 'Save case & reminder'}</span><span aria-hidden="true">↗</span>
          </button>
        </div>
      </form>
      <p className="privacy-note">Case details are private to your account.</p>
    </div>
  )
}
