import React from 'react';

export default function Header({ activeTab, setActiveTab, activeDomain, setActiveDomain, domains }) {
  return (
    <header className="header">
      <div className="brand">
        <div className="brand-icon">M</div>
        <div>
          <h1 className="brand-title">Monetize360</h1>
          <p className="brand-subtitle">Universal Dynamic Pricing Engine</p>
        </div>
      </div>

      <div className="nav-tabs">
        <button
          className={`nav-tab ${activeTab === 'simulator' ? 'active' : ''}`}
          onClick={() => setActiveTab('simulator')}
        >
          <span>🎯</span> Simulator
        </button>
        <button
          className={`nav-tab ${activeTab === 'studio' ? 'active' : ''}`}
          onClick={() => setActiveTab('studio')}
        >
          <span>⚙️</span> Rule Studio
        </button>
        <button
          className={`nav-tab ${activeTab === 'copilot' ? 'active' : ''}`}
          onClick={() => setActiveTab('copilot')}
        >
          <span>🤖</span> AI Copilot
        </button>
        <button
          className={`nav-tab ${activeTab === 'validation' ? 'active' : ''}`}
          onClick={() => setActiveTab('validation')}
        >
          <span>🛡️</span> Guardrails
        </button>
        <button
          className={`nav-tab ${activeTab === 'scorecard' ? 'active' : ''}`}
          onClick={() => setActiveTab('scorecard')}
        >
          <span>📊</span> Benchmark
        </button>
        <button
          className={`nav-tab ${activeTab === 'dashboard' ? 'active' : ''}`}
          onClick={() => setActiveTab('dashboard')}
          id="nav-tab-dashboard"
        >
          <span>📈</span> Dashboard
        </button>
        <button
          className={`nav-tab ${activeTab === 'store' ? 'active' : ''}`}
          onClick={() => setActiveTab('store')}
          id="nav-tab-store"
          style={activeTab === 'store' ? { background: '#0f766e', color: '#fff' } : { color: '#2dd4bf' }}
        >
          <span>🛍️</span> Live Store
        </button>
      </div>

      <div className="domain-select-bar">
        <span className="form-label" style={{ margin: 0 }}>Active Domain:</span>
        <select
          className="form-select"
          style={{ width: 'auto', padding: '0.4rem 0.8rem' }}
          value={activeDomain}
          onChange={(e) => setActiveDomain(e.target.value)}
        >
          {domains.map((d) => (
            <option key={d.pack_id || d.id} value={d.pack_id || d.id}>
              {d.name || d.pack_id} {d.status === 'published' ? '✓' : ''}
            </option>
          ))}
        </select>
      </div>
    </header>
  );
}
