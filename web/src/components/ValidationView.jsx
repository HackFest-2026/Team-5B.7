import React, { useState, useEffect } from 'react';

export default function ValidationView({ activeDomainPack }) {
  const [validationData, setValidationData] = useState(null);

  useEffect(() => {
    if (activeDomainPack) {
      fetch('/v1/validate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pack: activeDomainPack }),
      })
        .then((res) => res.json())
        .then((data) => setValidationData(data))
        .catch((e) => console.error(e));
    }
  }, [activeDomainPack]);

  const errorCatalog = [
    { code: 'C1', name: 'Unknown Signal', desc: 'Rule condition references a signal name not declared in the domain signals definition block.' },
    { code: 'C2', name: 'Invalid Operator', desc: 'Condition operator is not in allowed set (==, !=, >, >=, <, <=, in, not_in).' },
    { code: 'C3', name: 'Out-of-Range Value', desc: 'Constant value exceeds declared min/max boundaries for the signal.' },
    { code: 'C4', name: 'Priority Ambiguity', desc: 'Multiple rules in the same stage share identical priority order without tiebreakers.' },
    { code: 'C5', name: 'Rule Overlap / Contradiction', desc: 'Two rules trigger under identical signal conditions with conflicting adjustments.' },
    { code: 'C6', name: 'Missing Floor/Ceiling', desc: 'Domain pack lacks required financial safety floor or ceiling safety bounds.' },
    { code: 'C7', name: 'Unsupported Formula Symbol', desc: 'Formula expression uses disallowed functions or unsafe operators.' },
  ];

  return (
    <div className="grid-2">
      {/* Left Column: Active Pack Validation Status */}
      <div className="card">
        <div className="card-header">
          <h2 className="card-title">
            <span>🛡️</span> Guardrail Status ({activeDomainPack?.pack_id})
          </h2>
          {validationData && (
            <span className={`badge badge-${validationData.valid ? 'success' : 'danger'}`}>
              {validationData.valid ? 'CLEAN PASS' : 'ISSUES DETECTED'}
            </span>
          )}
        </div>

        {validationData ? (
          <div>
            <div className={`price-display-box`} style={{ textAlign: 'left', padding: '1rem', marginBottom: '1.2rem' }}>
              <div style={{ fontWeight: 700, fontSize: '1.1rem', color: validationData.valid ? '#10b981' : '#ef4444' }}>
                {validationData.valid ? '✓ Publish Guardrails Verification Passed' : '⚠️ Validation Errors Detected'}
              </div>
              <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                Total Errors: {validationData.errors?.length || 0} | Total Warnings: {validationData.warnings?.length || 0}
              </div>
            </div>

            <h4 style={{ marginBottom: '0.6rem' }}>Static Check Results:</h4>
            {validationData.errors?.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {validationData.errors.map((err, idx) => (
                  <div key={idx} className="badge badge-danger" style={{ display: 'block', textAlign: 'left', padding: '0.6rem' }}>
                    <strong>[{err.code}]</strong> {err.message}
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                <div className="badge badge-success" style={{ display: 'block', textAlign: 'left', padding: '0.6rem' }}>
                  ✓ C1 Signal Reference Check: All signals resolved.
                </div>
                <div className="badge badge-success" style={{ display: 'block', textAlign: 'left', padding: '0.6rem' }}>
                  ✓ C2 Operator Schema Check: Syntax verified.
                </div>
                <div className="badge badge-success" style={{ display: 'block', textAlign: 'left', padding: '0.6rem' }}>
                  ✓ C5 Rule Overlap Engine: No conflicting priority collisions.
                </div>
                <div className="badge badge-success" style={{ display: 'block', textAlign: 'left', padding: '0.6rem' }}>
                  ✓ C6 Floor/Ceiling Safeguard: Bounds active.
                </div>
              </div>
            )}
          </div>
        ) : (
          <p style={{ color: 'var(--text-muted)' }}>Running static validation checks...</p>
        )}
      </div>

      {/* Right Column: Error Code Catalog */}
      <div className="card">
        <div className="card-header">
          <h2 className="card-title">
            <span>📋</span> Static Analyzer Guardrail Rules (C1-C7)
          </h2>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          {errorCatalog.map((item) => (
            <div key={item.code} style={{ background: 'rgba(0,0,0,0.25)', padding: '0.75rem', borderRadius: '8px', borderLeft: '3px solid var(--primary)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.2rem' }}>
                <span className="badge badge-info">{item.code}</span>
                <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>{item.name}</span>
              </div>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{item.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
