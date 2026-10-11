import { useState } from 'react'

const terms = [
  { term: 'Affidavit', definition: 'A written statement of facts confirmed by oath or affirmation, used as evidence in legal proceedings.' },
  { term: 'Appeal', definition: 'A request for a higher court to review a decision made by a lower court.' },
  { term: 'Burden of proof', definition: 'The responsibility to prove the facts or claims required to succeed in a legal matter.' },
  { term: 'Case law', definition: 'Law established through the published decisions of courts.' },
  { term: 'Civil law', definition: 'The area of law concerning disputes between individuals, organizations, or both.' },
  { term: 'Claimant', definition: 'A person or organization that brings a claim in a civil proceeding.' },
  { term: 'Contract', definition: 'An agreement between parties that creates legally enforceable obligations.' },
  { term: 'Damages', definition: 'Money a court may award to compensate a party for a legally recognized loss.' },
  { term: 'Defendant', definition: 'The person or organization a claim or charge is brought against.' },
  { term: 'Deposition', definition: 'A witness’s sworn, out-of-court testimony recorded for possible use in a case.' },
  { term: 'Evidence', definition: 'Information presented to help establish facts in a legal proceeding.' },
  { term: 'Hearing', definition: 'A court proceeding where parties present arguments or evidence on a particular issue.' },
  { term: 'Jurisdiction', definition: 'A court’s legal authority to hear a matter and make decisions about it.' },
  { term: 'Litigation', definition: 'The process of resolving a dispute through the court system.' },
  { term: 'Motion', definition: 'A formal request asking a court to make a ruling or take a particular action.' },
  { term: 'Negligence', definition: 'A failure to use the level of care required by law, which causes harm to another.' },
  { term: 'Plaintiff', definition: 'The person or organization that starts a civil lawsuit by filing a complaint.' },
  { term: 'Precedent', definition: 'A prior court decision that may guide how similar later cases are decided.' },
  { term: 'Settlement', definition: 'An agreement that resolves a dispute, often without continuing to trial.' },
  { term: 'Testimony', definition: 'A witness’s formal statement, usually given under oath during a proceeding.' },
]

export default function DictionaryPage() {
  const [query, setQuery] = useState('')
  const filteredTerms = terms.filter(({ term, definition }) => (
    `${term} ${definition}`.toLowerCase().includes(query.trim().toLowerCase())
  ))

  return (
    <div className="workspace-page">
      <div className="page-heading">
        <span className="eyebrow">A QUICK REFERENCE</span>
        <h2>Legal dictionary<span>.</span></h2>
        <p>Plain-language definitions for commonly used legal terms.</p>
      </div>
      <label className="dictionary-search">
        <span className="sr-only">Search legal terms</span>
        <span aria-hidden="true">⌕</span>
        <input
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search a term or definition…"
          type="search"
          value={query}
        />
      </label>
      {filteredTerms.length ? (
        <dl className="dictionary-list">
          {filteredTerms.map(({ term, definition }) => (
            <div className="content-card dictionary-entry" key={term}>
              <dt>{term}</dt>
              <dd>{definition}</dd>
            </div>
          ))}
        </dl>
      ) : (
        <div className="content-card empty-state dictionary-empty">
          <h4>No matching terms.</h4>
          <p>Try a broader search or check your spelling.</p>
        </div>
      )}
      <p className="privacy-note">Definitions are general information, not legal advice. Meaning and application may vary by jurisdiction.</p>
    </div>
  )
}
