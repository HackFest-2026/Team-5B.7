import React, { useState } from 'react';

export default function CopilotView({ onDomainGenerated }) {
  const [prompt, setPrompt] = useState(
    'Create an e-commerce dynamic pricing model for luxury goods based on MRP, customer loyalty tier, cart urgency score, and stock clearance level.'
  );
  const [loading, setLoading] = useState(false);
  const [copilotResult, setCopilotResult] = useState(null);

  const samplePrompts = [
    'Create a dynamic pricing pack for EV charging based on peak grid load, battery SOC level, and renewable energy ratio.',
    'Build a dynamic interest rate pack for personal loans using credit score, loan-to-income ratio, and prime rate adjustments.',
    'Generate a dynamic pricing pack for cloud container hosting using vCPU count, RAM GB, region demand multiplier, and spot instance tier.',
  ];

  const handleGenerate = async () => {
    if (!prompt.trim()) return;
    setLoading(true);
    setCopilotResult(null);

    try {
      const res = await fetch('/v1/copilot/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt }),
      });

      if (res.ok) {
        const data = await res.json();
        setCopilotResult(data);
      } else {
        const err = await res.json();
        alert('Copilot error: ' + (err.detail || JSON.stringify(err)));
      }
    } catch (e) {
      console.error(e);
      alert('Error generating domain pack: ' + e.message);
    } finally {
      setLoading(false);
    }
  };

  const handlePublishGeneratedPack = async () => {
    if (!copilotResult?.pack) return;
    const pack = copilotResult.pack;

    try {
      const draftRes = await fetch('/v1/draft', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pack }),
      });
      if (!draftRes.ok) throw new Error('Draft failed');

      const pubRes = await fetch('/v1/publish', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          pack_id: pack.pack_id,
          version: pack.version,
          actor: 'copilot',
        }),
      });

      if (pubRes.ok) {
        alert(`Successfully published AI-generated domain '${pack.pack_id}' v${pack.version}!`);
        if (onDomainGenerated) onDomainGenerated(pack.pack_id);
      } else {
        const err = await pubRes.json();
        alert('Publish failed: ' + JSON.stringify(err.detail));
      }
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="grid-2">
      {/* Left Column: AI Prompt & Preset Cards */}
      <div className="card">
        <div className="card-header">
          <h2 className="card-title">
            <span>🤖</span> Business Intent → Domain Pack
          </h2>
          <span className="badge badge-info">AI Copilot</span>
        </div>

        <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>
          Describe your pricing strategy in plain English. The AI Copilot transforms business intent into a fully structured, validated Monetize360 domain pack.
        </p>

        <div className="form-group">
          <label className="form-label">Natural Language Intent Prompt:</label>
          <textarea
            className="form-textarea"
            rows={4}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
          />
        </div>

        <div style={{ marginBottom: '1.2rem' }}>
          <label className="form-label">Try Pre-built Business Prompts:</label>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {samplePrompts.map((p, idx) => (
              <button
                key={idx}
                className="btn btn-secondary"
                style={{ textAlign: 'left', fontSize: '0.8rem', padding: '0.5rem' }}
                onClick={() => setPrompt(p)}
              >
                💡 {p}
              </button>
            ))}
          </div>
        </div>

        <button
          className="btn btn-primary"
          style={{ width: '100%', justifyContent: 'center' }}
          onClick={handleGenerate}
          disabled={loading}
        >
          {loading ? '✨ AI Engine Synthesizing Domain Pack...' : '✨ Generate Domain Pack with AI'}
        </button>
      </div>

      {/* Right Column: AI Output & Validation Preview */}
      <div className="card">
        <div className="card-header">
          <h2 className="card-title">
            <span>⚡</span> Synthesized Pack Preview
          </h2>
          {copilotResult && (
            <span className={`badge badge-${copilotResult.validation?.valid ? 'success' : 'warning'}`}>
              {copilotResult.validation?.valid ? 'Valid Draft ✓' : 'Needs Review'}
            </span>
          )}
        </div>

        {copilotResult ? (
          <div>
            <div style={{ marginBottom: '1rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h3 style={{ fontSize: '1.1rem', color: '#a5b4fc' }}>
                  Domain ID: {copilotResult.pack?.pack_id}
                </h3>
                <span className="badge badge-info">v{copilotResult.pack?.version}</span>
              </div>
              <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                {copilotResult.pack?.description}
              </p>
            </div>

            <h4 style={{ fontSize: '0.9rem', marginBottom: '0.4rem' }}>Extracted Signals:</h4>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', marginBottom: '1rem' }}>
              {copilotResult.pack?.signals && Object.keys(copilotResult.pack.signals).map((s) => (
                <span key={s} className="badge badge-info">{s}</span>
              ))}
            </div>

            <h4 style={{ fontSize: '0.9rem', marginBottom: '0.4rem' }}>Synthesized Rules ({copilotResult.pack?.rules?.length || 0}):</h4>
            <div style={{ maxHeight: '200px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0.4rem', marginBottom: '1rem' }}>
              {copilotResult.pack?.rules?.map((r) => (
                <div key={r.rule_id} style={{ background: 'rgba(0,0,0,0.2)', padding: '0.5rem', borderRadius: '6px', fontSize: '0.8rem' }}>
                  <strong>{r.rule_id}</strong>: {r.description}
                </div>
              ))}
            </div>

            <button
              className="btn btn-accent"
              style={{ width: '100%', justifyContent: 'center' }}
              onClick={handlePublishGeneratedPack}
            >
              🚀 Approve & Publish to Engine
            </button>
          </div>
        ) : (
          <p style={{ color: 'var(--text-muted)' }}>
            Enter a prompt on the left to synthesize a new domain pack dynamically.
          </p>
        )}
      </div>
    </div>
  );
}
