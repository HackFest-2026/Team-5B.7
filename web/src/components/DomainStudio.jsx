import React, { useState, useEffect } from 'react';
import {
  validatePack,
  saveDraft,
  submitLifecycle,
  approveLifecycle,
  rejectLifecycle,
  publishPack,
  rollbackPack,
  bumpDomainVersion,
  fetchDomainVersions,
  fetchAuditVerification,
  getCurrencySymbol,
} from '../api.js';

export default function DomainStudio({ activeDomainPack, onPackUpdated }) {
  const [jsonText, setJsonText] = useState('');
  const [validationResult, setValidationResult] = useState(null);
  const [activeTab, setActiveTab] = useState('visual'); // 'visual', 'governance', 'json'
  const [message, setMessage] = useState(null);
  const [loading, setLoading] = useState(false);

  // Governance state
  const [actor, setActor] = useState('alice');
  const [enforceRoleSeparation, setEnforceRoleSeparation] = useState(true);
  const [requireApproval, setRequireApproval] = useState(false);
  const [rejectionReason, setRejectionReason] = useState('');
  const [bumpType, setBumpType] = useState('minor');
  const [versions, setVersions] = useState([]);
  const [versionsLoading, setVersionsLoading] = useState(false);
  const [auditVerification, setAuditVerification] = useState(null);

  useEffect(() => {
    if (activeDomainPack) {
      setJsonText(JSON.stringify(activeDomainPack, null, 2));
      setValidationResult(null);
      setMessage(null);
      loadVersions(activeDomainPack.pack_id);
      loadAuditVerification(activeDomainPack.pack_id);
    }
  }, [activeDomainPack]);

  const loadVersions = async (domainId) => {
    if (!domainId) return;
    setVersionsLoading(true);
    const { data } = await fetchDomainVersions(domainId);
    setVersionsLoading(false);
    if (data && Array.isArray(data)) {
      setVersions(data);
    }
  };

  const loadAuditVerification = async (domainId) => {
    if (!domainId) return;
    const { data } = await fetchAuditVerification(domainId);
    if (data) {
      setAuditVerification(data);
    }
  };

  const currentStatus = activeDomainPack?.status || 'published';
  const currencySymbol = getCurrencySymbol(activeDomainPack);

  // --------------------------------------------------------------------------
  // Validation
  // --------------------------------------------------------------------------
  const handleValidate = async () => {
    try {
      const parsed = JSON.parse(jsonText);
      setLoading(true);
      const { data, error } = await validatePack(parsed, actor);
      setLoading(false);

      if (error) {
        setValidationResult({ valid: false, errors: [{ code: 'API_ERROR', message: error }], warnings: [] });
        setMessage({ type: 'danger', text: error });
        return;
      }

      setValidationResult(data);
      if (data.valid) {
        setMessage({
          type: 'success',
          text: `Validation Passed! Clean schema and guardrails (${data.warnings?.length || 0} warnings).`,
        });
      } else {
        setMessage({
          type: 'danger',
          text: `Validation Failed with ${data.errors?.length || 0} error(s).`,
        });
      }
    } catch (e) {
      setValidationResult({
        valid: false,
        errors: [{ code: 'JSON_SYNTAX', message: e.message }],
        warnings: [],
      });
      setMessage({ type: 'danger', text: 'Invalid JSON format: ' + e.message });
    }
  };

  // --------------------------------------------------------------------------
  // Save Draft
  // --------------------------------------------------------------------------
  const handleSaveDraft = async () => {
    try {
      const parsed = JSON.parse(jsonText);
      setLoading(true);
      const { data, error } = await saveDraft(parsed, actor);
      setLoading(false);

      if (error) {
        setMessage({ type: 'danger', text: `Draft Save Failed: ${error}` });
      } else {
        setMessage({ type: 'success', text: `Draft saved successfully for ${parsed.pack_id} v${parsed.version}!` });
        if (onPackUpdated) onPackUpdated();
        loadVersions(parsed.pack_id);
      }
    } catch (e) {
      setMessage({ type: 'danger', text: 'Invalid JSON: ' + e.message });
    }
  };

  // --------------------------------------------------------------------------
  // Submit for Review
  // --------------------------------------------------------------------------
  const handleSubmitReview = async () => {
    if (!activeDomainPack) return;
    setLoading(true);
    const { data, error } = await submitLifecycle(activeDomainPack.pack_id, activeDomainPack.version, actor);
    setLoading(false);

    if (error) {
      setMessage({ type: 'danger', text: `Submit Failed: ${error}` });
    } else {
      setMessage({ type: 'success', text: `Pack submitted for review (status: in_review).` });
      if (onPackUpdated) onPackUpdated();
      loadVersions(activeDomainPack.pack_id);
    }
  };

  // --------------------------------------------------------------------------
  // Approve Review
  // --------------------------------------------------------------------------
  const handleApprove = async () => {
    if (!activeDomainPack) return;
    setLoading(true);
    const { data, error } = await approveLifecycle(
      activeDomainPack.pack_id,
      activeDomainPack.version,
      actor,
      enforceRoleSeparation
    );
    setLoading(false);

    if (error) {
      setMessage({ type: 'danger', text: `Approval Blocked: ${error}` });
    } else {
      setMessage({ type: 'success', text: `Pack approved by ${actor}! Ready to publish.` });
      if (onPackUpdated) onPackUpdated();
      loadVersions(activeDomainPack.pack_id);
    }
  };

  // --------------------------------------------------------------------------
  // Reject Review
  // --------------------------------------------------------------------------
  const handleReject = async () => {
    if (!activeDomainPack) return;
    setLoading(true);
    const { data, error } = await rejectLifecycle(
      activeDomainPack.pack_id,
      activeDomainPack.version,
      actor,
      rejectionReason || 'Rejected by reviewer'
    );
    setLoading(false);

    if (error) {
      setMessage({ type: 'danger', text: `Rejection Failed: ${error}` });
    } else {
      setMessage({ type: 'warning', text: `Pack returned to draft status.` });
      setRejectionReason('');
      if (onPackUpdated) onPackUpdated();
      loadVersions(activeDomainPack.pack_id);
    }
  };

  // --------------------------------------------------------------------------
  // Publish
  // --------------------------------------------------------------------------
  const handlePublish = async () => {
    if (!activeDomainPack) return;
    setLoading(true);
    const { data, error } = await publishPack(
      activeDomainPack.pack_id,
      activeDomainPack.version,
      actor,
      null,
      {
        enforceRoleSeparation,
        requireApproval,
        runGoldenTests: true,
      }
    );
    setLoading(false);

    if (error) {
      setMessage({ type: 'danger', text: `Publish Blocked: ${error}` });
    } else {
      setMessage({
        type: 'success',
        text: `Successfully published ${activeDomainPack.pack_id} v${activeDomainPack.version}! Version is now immutable.`,
      });
      if (onPackUpdated) onPackUpdated();
      loadVersions(activeDomainPack.pack_id);
      loadAuditVerification(activeDomainPack.pack_id);
    }
  };

  // --------------------------------------------------------------------------
  // Version Bump
  // --------------------------------------------------------------------------
  const handleBumpVersion = async () => {
    if (!activeDomainPack) return;
    setLoading(true);
    const { data, error } = await bumpDomainVersion(activeDomainPack.pack_id, bumpType, actor);
    setLoading(false);

    if (error) {
      setMessage({ type: 'danger', text: `Version Bump Failed: ${error}` });
    } else {
      setMessage({
        type: 'success',
        text: `Created new draft version ${data.pack?.version}!`,
      });
      if (onPackUpdated) onPackUpdated();
      loadVersions(activeDomainPack.pack_id);
    }
  };

  // --------------------------------------------------------------------------
  // Rollback
  // --------------------------------------------------------------------------
  const handleRollback = async (targetVersion) => {
    if (!activeDomainPack || !targetVersion) return;
    if (!confirm(`Are you sure you want to rollback ${activeDomainPack.pack_id} to v${targetVersion}?`)) return;

    setLoading(true);
    const { data, error } = await rollbackPack(activeDomainPack.pack_id, targetVersion, actor);
    setLoading(false);

    if (error) {
      setMessage({ type: 'danger', text: `Rollback Failed: ${error}` });
    } else {
      setMessage({
        type: 'success',
        text: `Successfully rolled back to v${targetVersion}! Previous version archived in audit log.`,
      });
      if (onPackUpdated) onPackUpdated();
      loadVersions(activeDomainPack.pack_id);
      loadAuditVerification(activeDomainPack.pack_id);
    }
  };

  if (!activeDomainPack) return <div className="card">Loading domain studio...</div>;

  return (
    <div className="grid-2">
      {/* ── Left Column: Visual Inspector / Governance / JSON Editor ──── */}
      <div className="card">
        <div className="card-header">
          <h2 className="card-title">
            <span>⚙️</span> Domain Studio ({activeDomainPack.pack_id})
          </h2>
          <div style={{ display: 'flex', gap: '0.4rem' }}>
            <button
              className={`btn ${activeTab === 'visual' ? 'btn-primary' : 'btn-secondary'}`}
              style={{ padding: '0.3rem 0.6rem', fontSize: '0.8rem' }}
              onClick={() => setActiveTab('visual')}
            >
              Visual
            </button>
            <button
              className={`btn ${activeTab === 'governance' ? 'btn-primary' : 'btn-secondary'}`}
              style={{ padding: '0.3rem 0.6rem', fontSize: '0.8rem' }}
              onClick={() => setActiveTab('governance')}
            >
              Governance
            </button>
            <button
              className={`btn ${activeTab === 'json' ? 'btn-primary' : 'btn-secondary'}`}
              style={{ padding: '0.3rem 0.6rem', fontSize: '0.8rem' }}
              onClick={() => setActiveTab('json')}
            >
              JSON Spec
            </button>
          </div>
        </div>

        {/* Identity & Role Separation Bar */}
        <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '0.6rem 0.8rem', marginBottom: '1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Actor Identity:</span>
            <input
              type="text"
              value={actor}
              onChange={(e) => setActor(e.target.value)}
              style={{ background: 'rgba(0,0,0,0.4)', border: '1px solid var(--border-color)', color: '#fff', borderRadius: '4px', padding: '0.2rem 0.5rem', fontSize: '0.8rem', width: '90px' }}
            />
            <button
              className="btn btn-secondary"
              style={{ padding: '0.2rem 0.5rem', fontSize: '0.75rem' }}
              onClick={() => setActor(actor === 'alice' ? 'bob' : 'alice')}
              title="Toggle between Author (Alice) and Approver (Bob)"
            >
              Switch to {actor === 'alice' ? 'Bob (Approver)' : 'Alice (Author)'}
            </button>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span className={`badge badge-${currentStatus === 'published' ? 'success' : currentStatus === 'approved' ? 'info' : currentStatus === 'in_review' ? 'warning' : 'secondary'}`}>
              Status: {currentStatus.toUpperCase()}
            </span>
            <span className="badge badge-info">v{activeDomainPack.version}</span>
          </div>
        </div>

        {message && (
          <div
            className={`badge badge-${message.type}`}
            style={{ display: 'block', padding: '0.6rem', marginBottom: '1rem', width: '100%', textAlign: 'left' }}
          >
            {message.text}
          </div>
        )}

        {/* ── TAB 1: Visual Spec Breakdown ─────────────────────────────── */}
        {activeTab === 'visual' && (
          <div style={{ maxHeight: '550px', overflowY: 'auto', paddingRight: '0.25rem' }}>
            {/* Base Calculation */}
            <h3 style={{ fontSize: '0.95rem', color: '#a5b4fc', marginBottom: '0.5rem' }}>
              🎯 Base Pricing Anchor
            </h3>
            <div style={{ background: 'rgba(0,0,0,0.3)', padding: '0.75rem', borderRadius: '8px', fontSize: '0.85rem', marginBottom: '1rem', border: '1px solid rgba(255,255,255,0.06)' }}>
              <div><strong>Type:</strong> <code style={{ color: '#38bdf8' }}>{activeDomainPack.base?.type}</code></div>
              {activeDomainPack.base?.type === 'formula' && (
                <div style={{ marginTop: '0.3rem' }}>
                  <strong>Formula Expression:</strong> <code style={{ color: '#10b981' }}>{activeDomainPack.base?.expr}</code>
                </div>
              )}
              {activeDomainPack.base?.type === 'fixed' && (
                <div style={{ marginTop: '0.3rem' }}>
                  <strong>Fixed Base:</strong> <code style={{ color: '#10b981' }}>{currencySymbol}{activeDomainPack.base?.value}</code>
                </div>
              )}
              {activeDomainPack.base?.type === 'table' && (
                <div style={{ marginTop: '0.3rem' }}>
                  <strong>Lookup Key Signal:</strong> <code style={{ color: '#f59e0b' }}>{activeDomainPack.base?.by}</code>
                  <div style={{ marginTop: '0.4rem', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '0.4rem' }}>
                    {Object.entries(activeDomainPack.base?.values || {}).map(([k, v]) => (
                      <div key={k} style={{ background: 'rgba(0,0,0,0.25)', padding: '0.3rem 0.5rem', borderRadius: '4px', fontSize: '0.8rem' }}>
                        {k}: <strong>{currencySymbol}{v}</strong>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Stages */}
            <h3 style={{ fontSize: '0.95rem', color: '#a5b4fc', marginBottom: '0.5rem' }}>
              🪜 Evaluation Stages ({activeDomainPack.stages?.length || 0})
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', marginBottom: '1rem' }}>
              {activeDomainPack.stages?.map((stage) => (
                <div key={stage.id} style={{ background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border-color)', padding: '0.5rem 0.75rem', borderRadius: '6px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <span style={{ fontWeight: 600, color: '#f3f4f6', marginRight: '0.5rem' }}>{stage.id}</span>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{stage.description}</span>
                  </div>
                  <span className="badge badge-info" style={{ fontSize: '0.75rem' }}>Stacking: {stage.stacking}</span>
                </div>
              ))}
            </div>

            {/* Rules */}
            <h3 style={{ fontSize: '0.95rem', color: '#a5b4fc', marginBottom: '0.5rem' }}>
              ⚡ Rules ({activeDomainPack.rules?.length || 0})
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', marginBottom: '1rem' }}>
              {activeDomainPack.rules?.map((rule) => (
                <div key={rule.id} style={{ background: 'rgba(0,0,0,0.25)', border: '1px solid var(--border-color)', padding: '0.65rem', borderRadius: '8px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.25rem' }}>
                    <div>
                      <span style={{ fontWeight: 600, color: '#f3f4f6', marginRight: '0.5rem' }}>{rule.id}</span>
                      <span className="badge badge-secondary" style={{ fontSize: '0.7rem' }}>Stage: {rule.stage}</span>
                    </div>
                    <span className="badge badge-info" style={{ fontSize: '0.7rem' }}>Priority {rule.priority}</span>
                  </div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{rule.description}</div>
                  {/* Condition preview */}
                  <div style={{ marginTop: '0.3rem', fontSize: '0.75rem', color: '#cbd5e1' }}>
                    <strong>When: </strong>
                    {rule.when?.all ? (
                      rule.when.all.map((c, idx) => (
                        <span key={idx} style={{ background: 'rgba(0,0,0,0.3)', padding: '0.1rem 0.35rem', borderRadius: '3px', marginRight: '0.3rem' }}>
                          {c.signal} {c.op} {String(c.value)}
                        </span>
                      ))
                    ) : rule.when?.any ? (
                      rule.when.any.map((c, idx) => (
                        <span key={idx} style={{ background: 'rgba(0,0,0,0.3)', padding: '0.1rem 0.35rem', borderRadius: '3px', marginRight: '0.3rem' }}>
                          (OR) {c.signal} {c.op} {String(c.value)}
                        </span>
                      ))
                    ) : (
                      <span style={{ color: 'var(--text-dim)' }}>Always triggers</span>
                    )}
                  </div>
                  {/* Action preview */}
                  <div style={{ marginTop: '0.3rem', fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color: '#10b981' }}>
                    Action: <strong>{rule.then?.op}</strong> {rule.then?.value !== undefined ? String(rule.then.value) : ''}
                  </div>
                </div>
              ))}
            </div>

            {/* Guardrail Constraints */}
            <h3 style={{ fontSize: '0.95rem', color: '#a5b4fc', marginBottom: '0.5rem' }}>
              🛡️ Safety Constraints ({activeDomainPack.constraints?.length || 0})
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', marginBottom: '1rem' }}>
              {activeDomainPack.constraints?.map((c) => (
                <div key={c.id} style={{ background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border-color)', padding: '0.5rem 0.75rem', borderRadius: '6px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <span style={{ fontWeight: 600, color: '#f3f4f6', marginRight: '0.4rem' }}>{c.id}</span>
                    <span className="badge badge-warning" style={{ fontSize: '0.7rem' }}>{c.type}</span>
                  </div>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color: '#cbd5e1' }}>
                    {c.expr ? `Formula: ${c.expr}` : c.value !== undefined ? `±${c.value}%` : ''}
                  </div>
                </div>
              ))}
            </div>

            {/* Rounding Policy */}
            <h3 style={{ fontSize: '0.95rem', color: '#a5b4fc', marginBottom: '0.5rem' }}>
              🔢 Rounding Guardrail
            </h3>
            <div style={{ background: 'rgba(0,0,0,0.2)', padding: '0.5rem 0.75rem', borderRadius: '6px', fontSize: '0.85rem' }}>
              Mode: <strong>{activeDomainPack.rounding?.mode}</strong> | Step: <strong>{activeDomainPack.rounding?.step}</strong>
            </div>
          </div>
        )}

        {/* ── TAB 2: Governance & Version History ─────────────────────── */}
        {activeTab === 'governance' && (
          <div style={{ maxHeight: '550px', overflowY: 'auto' }}>
            {/* Role Separation & Approval Flags */}
            <div style={{ background: 'rgba(0,0,0,0.3)', padding: '0.75rem', borderRadius: '8px', marginBottom: '1rem', border: '1px solid var(--border-color)' }}>
              <h4 style={{ fontSize: '0.9rem', marginBottom: '0.5rem', color: '#a5b4fc' }}>
                Governance Gates & Policies
              </h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', fontSize: '0.85rem' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={enforceRoleSeparation}
                    onChange={(e) => setEnforceRoleSeparation(e.target.checked)}
                  />
                  <span>Enforce Four-Eyes Role Separation (Author cannot approve own pack)</span>
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={requireApproval}
                    onChange={(e) => setRequireApproval(e.target.checked)}
                  />
                  <span>Require Explicit Approval Before Publishing</span>
                </label>
              </div>
            </div>

            {/* Lifecycle State Actions */}
            <div style={{ background: 'rgba(0,0,0,0.3)', padding: '0.75rem', borderRadius: '8px', marginBottom: '1rem', border: '1px solid var(--border-color)' }}>
              <h4 style={{ fontSize: '0.9rem', marginBottom: '0.5rem', color: '#a5b4fc' }}>
                Lifecycle Actions for Current Version ({activeDomainPack.version})
              </h4>
              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                {currentStatus === 'draft' && (
                  <>
                    <button className="btn btn-secondary" onClick={handleSaveDraft} disabled={loading}>
                      💾 Update Draft
                    </button>
                    <button className="btn btn-primary" onClick={handleSubmitReview} disabled={loading}>
                      📋 Submit for Review
                    </button>
                    <button className="btn btn-accent" onClick={handlePublish} disabled={loading}>
                      🚀 Publish Directly
                    </button>
                  </>
                )}

                {currentStatus === 'in_review' && (
                  <>
                    <button className="btn btn-primary" onClick={handleApprove} disabled={loading}>
                      ✅ Approve as {actor}
                    </button>
                    <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center', width: '100%', marginTop: '0.5rem' }}>
                      <input
                        type="text"
                        placeholder="Rejection reason..."
                        value={rejectionReason}
                        onChange={(e) => setRejectionReason(e.target.value)}
                        style={{ flex: 1, padding: '0.35rem 0.6rem', fontSize: '0.8rem', background: 'rgba(0,0,0,0.4)', border: '1px solid var(--border-color)', color: '#fff', borderRadius: '4px' }}
                      />
                      <button className="btn btn-secondary" onClick={handleReject} disabled={loading}>
                        ↩️ Reject to Draft
                      </button>
                    </div>
                  </>
                )}

                {currentStatus === 'approved' && (
                  <button className="btn btn-accent" onClick={handlePublish} disabled={loading}>
                    🚀 Publish Approved Version
                  </button>
                )}

                {currentStatus === 'published' && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', width: '100%' }}>
                    <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Create Next Version:</span>
                    <select
                      className="form-select"
                      style={{ width: 'auto', padding: '0.3rem 0.6rem', fontSize: '0.8rem' }}
                      value={bumpType}
                      onChange={(e) => setBumpType(e.target.value)}
                    >
                      <option value="patch">Patch (+0.0.1)</option>
                      <option value="minor">Minor (+0.1.0)</option>
                      <option value="major">Major (+1.0.0)</option>
                    </select>
                    <button className="btn btn-primary" onClick={handleBumpVersion} disabled={loading}>
                      ➕ Create Draft vNext
                    </button>
                  </div>
                )}
              </div>
            </div>

            {/* Version History & Rollback Table */}
            <div style={{ background: 'rgba(0,0,0,0.3)', padding: '0.75rem', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                <h4 style={{ fontSize: '0.9rem', color: '#a5b4fc', margin: 0 }}>
                  📜 Version History & Rollback
                </h4>
                <button
                  className="btn btn-secondary"
                  style={{ padding: '0.2rem 0.5rem', fontSize: '0.75rem' }}
                  onClick={() => loadVersions(activeDomainPack.pack_id)}
                >
                  Refresh
                </button>
              </div>

              {versionsLoading ? (
                <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Loading versions...</p>
              ) : versions.length === 0 ? (
                <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>No historical versions found.</p>
              ) : (
                <table className="table" style={{ fontSize: '0.8rem' }}>
                  <thead>
                    <tr>
                      <th>Ver</th>
                      <th>Status</th>
                      <th>Published By</th>
                      <th>Fingerprint</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {versions.map((v) => (
                      <tr key={v.version}>
                        <td><strong>v{v.version}</strong></td>
                        <td>
                          <span className={`badge badge-${v.status === 'published' ? 'success' : v.status === 'approved' ? 'info' : 'secondary'}`}>
                            {v.status}
                          </span>
                        </td>
                        <td>{v.published_by || v.created_by || '—'}</td>
                        <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.7rem' }}>
                          {v.fingerprint ? `${v.fingerprint.substring(0, 10)}…` : '—'}
                        </td>
                        <td>
                          {v.status === 'archived' && (
                            <button
                              className="btn btn-secondary"
                              style={{ padding: '0.2rem 0.4rem', fontSize: '0.7rem' }}
                              onClick={() => handleRollback(v.version)}
                              disabled={loading}
                            >
                              ⏪ Rollback
                            </button>
                          )}
                          {v.status === 'published' && <span style={{ color: '#10b981' }}>Active ✓</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        )}

        {/* ── TAB 3: JSON Spec Editor ──────────────────────────────────── */}
        {activeTab === 'json' && (
          <div>
            <textarea
              className="form-textarea"
              rows={20}
              value={jsonText}
              onChange={(e) => setJsonText(e.target.value)}
              style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem' }}
            />
            <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.75rem' }}>
              <button className="btn btn-secondary" onClick={handleSaveDraft} disabled={loading}>
                💾 Save as Draft
              </button>
            </div>
          </div>
        )}

        {/* Global Toolbar Bottom */}
        <div style={{ display: 'flex', gap: '0.8rem', marginTop: '1.2rem', borderTop: '1px solid var(--border-color)', paddingTop: '1rem' }}>
          <button className="btn btn-secondary" onClick={handleValidate} disabled={loading}>
            🔍 Run Static Validation
          </button>
          {currentStatus === 'draft' && (
            <button className="btn btn-accent" onClick={handlePublish} disabled={loading}>
              🚀 Validate & Publish
            </button>
          )}
        </div>
      </div>

      {/* ── Right Column: Validation Report & Audit Verification ────── */}
      <div className="card">
        <div className="card-header">
          <h2 className="card-title">
            <span>🛡️</span> Validation & Integrity Report
          </h2>
          {validationResult && (
            <span className={`badge badge-${validationResult.valid ? 'success' : 'danger'}`}>
              {validationResult.valid ? 'PASS' : 'FAIL'}
            </span>
          )}
        </div>

        {/* Audit Chain Cryptographic Status */}
        {auditVerification && (
          <div style={{ background: auditVerification.valid ? 'rgba(16,185,129,0.1)' : 'rgba(239,68,68,0.1)', border: `1px solid ${auditVerification.valid ? 'rgba(16,185,129,0.4)' : 'rgba(239,68,68,0.4)'}`, borderRadius: '8px', padding: '0.65rem 0.85rem', marginBottom: '1rem', fontSize: '0.85rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontWeight: 600, color: auditVerification.valid ? '#10b981' : '#ef4444' }}>
                🔒 Audit Hash Chain: {auditVerification.valid ? 'VERIFIED INTACT ✓' : 'TAMPERING DETECTED ⚠️'}
              </span>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                {auditVerification.total_records || 0} Records
              </span>
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: '0.2rem' }}>
              {auditVerification.message}
            </div>
          </div>
        )}

        {validationResult ? (
          <div>
            <h4 style={{ marginBottom: '0.5rem', fontSize: '0.9rem' }}>Static Check Details:</h4>
            {validationResult.errors?.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {validationResult.errors.map((err, i) => (
                  <div key={i} className="badge badge-danger" style={{ display: 'block', textAlign: 'left', padding: '0.6rem' }}>
                    <strong>[{err.code}]</strong> {err.message}
                    {err.rule_ids?.length > 0 && <span> (Rules: {err.rule_ids.join(', ')})</span>}
                  </div>
                ))}
              </div>
            ) : (
              <div className="badge badge-success" style={{ display: 'block', textAlign: 'left', padding: '0.75rem' }}>
                ✓ Schema structure and SemVer valid <br />
                ✓ No condition overlaps or cyclic dependencies <br />
                ✓ Floor & Ceiling safety bounds declared <br />
                ✓ Safe formula math expressions verified (C1–C7 clean)
              </div>
            )}

            {validationResult.warnings?.length > 0 && (
              <div style={{ marginTop: '1rem' }}>
                <h4 style={{ marginBottom: '0.5rem', color: '#f59e0b', fontSize: '0.9rem' }}>Warnings:</h4>
                {validationResult.warnings.map((w, i) => (
                  <div key={i} className="badge badge-warning" style={{ display: 'block', textAlign: 'left', padding: '0.5rem' }}>
                    {w.message}
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : (
          <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
            Click 'Run Static Validation' to check schema compliance, priority conflicts, range bounds, and guardrail constraints before publishing.
          </p>
        )}
      </div>
    </div>
  );
}
