const navigation = [
  { id: 'overview', label: 'Overview', icon: '⌂' },
  { id: 'create-case', label: 'Create new case', icon: '+' },
  { id: 'cases', label: 'View all cases', icon: '▤' },
  { id: 'payments', label: 'Payment', icon: '$' },
  { id: 'clients', label: 'All clients', icon: '♧' },
  { id: 'dictionary', label: 'Dictionary', icon: 'Aa' },
]

export default function Sidebar({ page, onNavigate }) {
  return (
    <aside className="workspace-sidebar">
      <span className="sidebar-label">WORKSPACE</span>
      <nav aria-label="Workspace pages">
        {navigation.map((item) => (
          <button
            className={`sidebar-link${page === item.id ? ' is-active' : ''}`}
            key={item.id}
            onClick={() => onNavigate(item.id)}
            type="button"
            aria-current={page === item.id ? 'page' : undefined}
          >
            <span className="sidebar-icon" aria-hidden="true">{item.icon}</span>
            <span>{item.label}</span>
          </button>
        ))}
      </nav>
      <div className="sidebar-help">
        <span className="sidebar-help-mark" aria-hidden="true">✦</span>
        <p>Case management<br />and client records.</p>
      </div>
    </aside>
  )
}
