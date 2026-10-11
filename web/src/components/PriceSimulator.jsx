import React, { useState, useEffect, useRef } from 'react';
import {
  fetchPrice,
  fetchSweep,
  fetchContext,
  updateContext,
  deleteContext,
  buildInitialSignals,
  castAllSignals,
  getMissingRequiredSignals,
  getCurrencySymbol,
} from '../api.js';

/**
 * PriceSimulator — Sends real pricing requests to POST /v1/price using the
 * backend contract: { domain, signals } request, { price, base,
 * fingerprint, trace[] } response.
 *
 * Exposes live Operational Context (GET/PUT/DELETE /v1/context/:domain)
 * with airline presets, expiry detection, and request-over-context precedence.
 */
export default function PriceSimulator({ activeDomainPack }) {
  const [signals, setSignals] = useState({});
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [fieldErrors, setFieldErrors] = useState({});

  // Operational Context State
  const [contextSnapshot, setContextSnapshot] = useState(null);
  const [contextStatus, setContextStatus] = useState('none'); // 'none', 'active', 'stale'
  const [contextLoading, setContextLoading] = useState(false);
  const [contextMsg, setContextMsg] = useState(null);
  const [contextSignalsInput, setContextSignalsInput] = useState('');
  const [contextMaxAge, setContextMaxAge] = useState(300);

  // Sweep state
  const [sweepSignal, setSweepSignal] = useState('');
  const [sweepResults, setSweepResults] = useState([]);
  const [sweepLoading, setSweepLoading] = useState(false);
  const [sweepError, setSweepError] = useState(null);

  const inFlight = useRef(false);

  // --------------------------------------------------------------------------
  // Load operational context snapshot
  // --------------------------------------------------------------------------
  const loadContext = async (domainId) => {
    if (!domainId) return;
    setContextLoading(true);
    const { data, error: ctxErr } = await fetchContext(domainId);
    setContextLoading(false);

    if (ctxErr) {
      if (ctxErr.toLowerCase().includes('stale') || ctxErr.toLowerCase().includes('expired')) {
        setContextStatus('stale');
        setContextSnapshot(null);
      } else {
        setContextStatus('none');
        setContextSnapshot(null);
      }
    } else if (data && data.signals) {
      const isExpired = new Date(data.expires_at) < new Date();
      setContextStatus(isExpired ? 'stale' : 'active');
      setContextSnapshot(data);
      setContextSignalsInput(JSON.stringify(data.signals, null, 2));
    } else {
      setContextStatus('none');
      setContextSnapshot(null);
    }
  };

  // --------------------------------------------------------------------------
  // Submit price request
  // --------------------------------------------------------------------------
  const handlePriceCalculate = async () => {
    if (!activeDomainPack || inFlight.current) return;

    const sigArray = Array.isArray(activeDomainPack.signals) ? activeDomainPack.signals : [];

    // Check missing required signals (satisfied if provided in request OR active in context)
    const missing = sigArray
      .filter((s) => s.required)
      .filter((s) => {
        const reqVal = signals[s.key];
        const hasReq = reqVal !== undefined && reqVal !== null && reqVal !== '';
        const hasCtx =
          contextStatus === 'active' &&
          contextSnapshot?.signals?.[s.key] !== undefined &&
          contextSnapshot?.signals?.[s.key] !== null;
        return !hasReq && !hasCtx;
      })
      .map((s) => s.key);

    if (missing.length > 0) {
      const errs = {};
      missing.forEach((k) => {
        errs[k] = 'Required';
      });
      setFieldErrors(errs);
      setError(`Missing required signal(s): ${missing.join(', ')}`);
      return;
    }
    setFieldErrors({});

    // Filter out signals that are intentionally omitted so context snapshot fills them
    const filteredSignals = {};
    for (const [k, v] of Object.entries(signals)) {
      if (v !== '' && v !== null && v !== undefined) {
        filteredSignals[k] = v;
      }
    }

    const castedSignals = castAllSignals(filteredSignals, sigArray);

    inFlight.current = true;
    setLoading(true);
    setError(null);

    const { data, error: apiError } = await fetchPrice(activeDomainPack.pack_id, castedSignals);

    inFlight.current = false;
    setLoading(false);

    if (apiError) {
      setError(apiError);
      setResult(null);
    } else {
      setResult(data);
    }
  };

  // --------------------------------------------------------------------------
  // Reset domain pack signals
  // --------------------------------------------------------------------------
  useEffect(() => {
    if (!activeDomainPack) return;

    const sigArray = Array.isArray(activeDomainPack.signals) ? activeDomainPack.signals : [];

    setSignals(buildInitialSignals(sigArray));
    setResult(null);
    setError(null);
    setFieldErrors({});
    setSweepResults([]);
    setSweepError(null);
    setContextMsg(null);

    const numSig = sigArray.find((s) => s.type === 'number' || s.type === 'integer');
    setSweepSignal(numSig ? numSig.key : '');

    loadContext(activeDomainPack.pack_id);
  }, [activeDomainPack]);

  const handleSignalChange = (key, value) => {
    setSignals((prev) => ({ ...prev, [key]: value }));
    if (fieldErrors[key]) {
      setFieldErrors((prev) => {
        const n = { ...prev };
        delete n[key];
        return n;
      });
    }
  };

  // --------------------------------------------------------------------------
  // Context Actions
  // --------------------------------------------------------------------------
  const applyContextPreset = async (presetSignals, presetName) => {
    if (!activeDomainPack) return;
    setContextLoading(true);
    setContextMsg(null);
    const { data, error: err } = await updateContext(
      activeDomainPack.pack_id,
      presetSignals,
      new Date().toISOString(),
      contextMaxAge,
      presetName
    );
    setContextLoading(false);

    if (err) {
      setContextMsg({ type: 'danger', text: `Failed to set context: ${err}` });
    } else {
      setContextMsg({ type: 'success', text: `Applied ${presetName} context!` });
      loadContext(activeDomainPack.pack_id);
    }
  };

  const handleClearContext = async () => {
    if (!activeDomainPack) return;
    setContextLoading(true);
    const { error: err } = await deleteContext(activeDomainPack.pack_id);
    setContextLoading(false);
    if (err) {
      setContextMsg({ type: 'danger', text: `Clear failed: ${err}` });
    } else {
      setContextMsg({ type: 'info', text: 'Context snapshot cleared. Using direct request signals.' });
      setContextSnapshot(null);
      setContextStatus('none');
    }
  };

  const handleCustomContextSave = async () => {
    if (!activeDomainPack) return;
    try {
      const parsed = JSON.parse(contextSignalsInput);
      setContextLoading(true);
      const { error: err } = await updateContext(
        activeDomainPack.pack_id,
        parsed,
        new Date().toISOString(),
        contextMaxAge,
        'custom_ui'
      );
      setContextLoading(false);
      if (err) {
        setContextMsg({ type: 'danger', text: `Failed: ${err}` });
      } else {
        setContextMsg({ type: 'success', text: 'Custom context snapshot saved!' });
        loadContext(activeDomainPack.pack_id);
      }
    } catch (e) {
      setContextMsg({ type: 'danger', text: 'Invalid JSON for context signals: ' + e.message });
    }
  };

  // --------------------------------------------------------------------------
  // Sweep
  // --------------------------------------------------------------------------
  const runSweep = async () => {
    if (!sweepSignal || !activeDomainPack || sweepLoading) return;

    const sigArray = Array.isArray(activeDomainPack.signals) ? activeDomainPack.signals : [];
    const spec = sigArray.find((s) => s.key === sweepSignal);
    if (!spec) return;

    const min = spec.min !== undefined ? spec.min : 0;
    const max = spec.max !== undefined ? spec.max : 100;
    const steps = 6;
    const sweepValues = Array.from({ length: steps }, (_, i) => {
      const raw = min + ((max - min) / (steps - 1)) * i;
      return spec.type === 'integer' ? Math.round(raw) : Math.round(raw * 100) / 100;
    });

    const castedBase = castAllSignals(signals, sigArray);
    setSweepLoading(true);
    setSweepError(null);

    const { data, error: swErr } = await fetchSweep(
      activeDomainPack.pack_id,
      castedBase,
      sweepSignal,
      sweepValues
    );

    setSweepLoading(false);
    if (swErr) {
      setSweepError(swErr);
      setSweepResults([]);
    } else {
      setSweepResults(data || []);
    }
  };

  const currencySymbol = getCurrencySymbol(activeDomainPack);
  const sigArray = Array.isArray(activeDomainPack?.signals) ? activeDomainPack.signals : [];

  if (!activeDomainPack) {
    return <div className="card">Loading domain pack details...</div>;
  }

  // --------------------------------------------------------------------------
  // Signal input renderer
  // --------------------------------------------------------------------------
  const renderSignalInput = (sig) => {
    const val = signals[sig.key];
    const hasErr = !!fieldErrors[sig.key];
    const ctxVal = contextSnapshot?.signals?.[sig.key];
    const isUsingContext = (val === '' || val === undefined) && ctxVal !== undefined;

    if (sig.type === 'number' || sig.type === 'integer') {
      const min = sig.min !== undefined ? sig.min : 0;
      const max = sig.max !== undefined ? sig.max : 1000;
      const displayVal = val !== undefined && val !== '' ? val : min;

      return (
        <div>
          <div className="slider-group">
            <input
              type="range"
              className="slider-input"
              min={min}
              max={max}
              step={sig.type === 'integer' ? 1 : (max - min) / 100}
              value={displayVal}
              onChange={(e) =>
                handleSignalChange(
                  sig.key,
                  sig.type === 'integer' ? parseInt(e.target.value, 10) : parseFloat(e.target.value)
                )
              }
              aria-label={sig.key}
            />
            <span className="slider-val">{displayVal}</span>
          </div>
          {ctxVal !== undefined && (
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '0.2rem', fontSize: '0.72rem' }}>
              <span style={{ color: isUsingContext ? '#38bdf8' : '#a5b4fc' }}>
                📡 Context Snapshot: <strong>{ctxVal}</strong>
              </span>
              <button
                type="button"
                className="btn btn-secondary"
                style={{ padding: '0.1rem 0.4rem', fontSize: '0.68rem' }}
                onClick={() => handleSignalChange(sig.key, ctxVal)}
                title="Populate input with snapshot value"
              >
                Reset to Context
              </button>
            </div>
          )}
        </div>
      );
    }

    if (sig.type === 'enum') {
      const options = Array.isArray(sig.values) ? sig.values : [];
      return (
        <select
          className={`form-select${hasErr ? ' form-error' : ''}`}
          value={val ?? ''}
          onChange={(e) => handleSignalChange(sig.key, e.target.value)}
          aria-label={sig.key}
        >
          {options.map((opt) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </select>
      );
    }

    if (sig.type === 'boolean') {
      return (
        <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={!!val}
            onChange={(e) => handleSignalChange(sig.key, e.target.checked)}
            aria-label={sig.key}
          />
          <span style={{ fontSize: '0.9rem' }}>Enable {sig.key}</span>
        </label>
      );
    }

    return (
      <input
        type="text"
        className={`form-input${hasErr ? ' form-error' : ''}`}
        value={val ?? ''}
        onChange={(e) => handleSignalChange(sig.key, e.target.value)}
        aria-label={sig.key}
      />
    );
  };

  return (
    <div className="grid-2">
      {/* ── Left Column: Operational Context & Request Signals ───────────── */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        {/* Operational Context Card */}
        <div className="card" style={{ borderLeft: '3px solid #38bdf8' }}>
          <div className="card-header">
            <h2 className="card-title" style={{ fontSize: '0.95rem' }}>
              <span>📡</span> Live Operational Context
            </h2>
            <span
              className={`badge ${
                contextStatus === 'active'
                  ? 'badge-success'
                  : contextStatus === 'stale'
                  ? 'badge-danger'
                  : 'badge-secondary'
              }`}
            >
              {contextStatus === 'active'
                ? 'Active Snapshot ✓'
                : contextStatus === 'stale'
                ? 'Expired / Stale ⚠️'
                : 'No Context'}
            </span>
          </div>

          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.6rem' }}>
            Time-expiring operational environment signals merged into evaluations. Request signals take precedence.
          </p>

          {contextMsg && (
            <div
              className={`badge badge-${contextMsg.type}`}
              style={{ display: 'block', padding: '0.4rem 0.6rem', marginBottom: '0.6rem', textAlign: 'left', fontSize: '0.75rem' }}
            >
              {contextMsg.text}
            </div>
          )}

          {/* Active Context Details */}
          {contextSnapshot && (
            <div style={{ background: 'rgba(0,0,0,0.3)', padding: '0.5rem 0.75rem', borderRadius: '6px', fontSize: '0.78rem', marginBottom: '0.75rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.2rem' }}>
                <span><strong>Source:</strong> {contextSnapshot.source}</span>
                <span style={{ color: contextStatus === 'active' ? '#10b981' : '#ef4444' }}>
                  Expires: {new Date(contextSnapshot.expires_at).toLocaleTimeString()}
                </span>
              </div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: '#38bdf8' }}>
                Signals: {JSON.stringify(contextSnapshot.signals)}
              </div>
            </div>
          )}

          {/* Airline Presets Bar */}
          {activeDomainPack.pack_id === 'airline' && (
            <div style={{ marginBottom: '0.75rem' }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.3rem' }}>
                Airline Context Presets (One-Click Scenario Simulation):
              </div>
              <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }}
                  onClick={() => applyContextPreset({ demand_index: 50, available_seats: 200 }, 'normal_flight')}
                  disabled={contextLoading}
                >
                  🛫 Normal (Demand: 50, Seats: 200)
                </button>
                <button
                  type="button"
                  className="btn btn-primary"
                  style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }}
                  onClick={() => applyContextPreset({ demand_index: 95, available_seats: 5 }, 'critical_surge')}
                  disabled={contextLoading}
                >
                  🔥 Surge (Demand: 95, Seats: 5)
                </button>
                {contextSnapshot && (
                  <button
                    type="button"
                    className="btn btn-secondary"
                    style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem', color: '#fca5a5' }}
                    onClick={handleClearContext}
                    disabled={contextLoading}
                  >
                    🧹 Clear
                  </button>
                )}
              </div>
            </div>
          )}

          {/* Manual Snapshot Form Toggle/Section */}
          <details style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
            <summary style={{ cursor: 'pointer', marginBottom: '0.4rem' }}>
              ⚙️ Custom Context Signals & TTL Configuration
            </summary>
            <div style={{ marginTop: '0.4rem' }}>
              <textarea
                className="form-textarea"
                rows={3}
                placeholder='{"signal_key": value}'
                value={contextSignalsInput}
                onChange={(e) => setContextSignalsInput(e.target.value)}
                style={{ fontSize: '0.75rem', fontFamily: 'var(--font-mono)' }}
              />
              <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.4rem', alignItems: 'center' }}>
                <span>TTL (sec):</span>
                <input
                  type="number"
                  value={contextMaxAge}
                  onChange={(e) => setContextMaxAge(parseInt(e.target.value, 10) || 300)}
                  style={{ width: '70px', padding: '0.2rem', background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border-color)', color: '#fff', fontSize: '0.75rem' }}
                />
                <button
                  type="button"
                  className="btn btn-secondary"
                  style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }}
                  onClick={handleCustomContextSave}
                  disabled={contextLoading}
                >
                  Update Snapshot
                </button>
              </div>
            </div>
          </details>
        </div>

        {/* Request Signals Input Card */}
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">
              <span>⚡</span> Request Signals ({activeDomainPack.pack_id})
            </h2>
            <span className="badge badge-info">v{activeDomainPack.version}</span>
          </div>

          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '1.2rem' }}>
            {activeDomainPack.description}
          </p>

          {sigArray.map((sig) => (
            <div className="form-group" key={sig.key}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.3rem' }}>
                <label className="form-label" style={{ fontWeight: 600, textTransform: 'capitalize' }}>
                  {sig.key.replace(/_/g, ' ')}
                  {sig.required && <span style={{ color: 'var(--danger)', marginLeft: '0.25rem' }}>*</span>}
                </label>
                <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
                  {contextSnapshot?.signals?.[sig.key] !== undefined && (
                    <span className="badge badge-info" style={{ fontSize: '0.65rem' }}>
                      Context: {contextSnapshot.signals[sig.key]}
                    </span>
                  )}
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>{sig.type}</span>
                </div>
              </div>

              {renderSignalInput(sig)}

              {fieldErrors[sig.key] && (
                <div style={{ fontSize: '0.75rem', color: 'var(--danger)', marginTop: '0.25rem' }}>
                  {fieldErrors[sig.key]}
                </div>
              )}
            </div>
          ))}

          {error && (
            <div
              role="alert"
              style={{
                marginTop: '1rem',
                padding: '0.75rem 1rem',
                borderRadius: '8px',
                background: 'rgba(239,68,68,0.12)',
                border: '1px solid rgba(239,68,68,0.4)',
                color: '#fca5a5',
                fontSize: '0.85rem',
              }}
            >
              ⚠️ {error}
            </div>
          )}

          <button
            className="btn btn-primary"
            style={{ marginTop: '1.25rem', width: '100%' }}
            onClick={handlePriceCalculate}
            disabled={loading}
            aria-busy={loading}
          >
            {loading ? '⏳ Calculating…' : '🔮 Calculate Price'}
          </button>
        </div>
      </div>

      {/* ── Right Column: Result + Sweep ─────────────────────────────────── */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
        {/* Engine Evaluation Card */}
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">
              <span>💎</span> Engine Evaluation
            </h2>
            <span className="badge badge-success">Deterministic ✓</span>
          </div>

          {loading && <p style={{ color: 'var(--text-muted)' }}>⏳ Calculating price…</p>}

          {!loading && error && !result && (
            <p style={{ color: 'var(--text-muted)' }}>Enter valid signal values to see a price.</p>
          )}

          {!loading && result && (
            <div>
              <div className="price-display-box">
                <div className="price-sub">
                  Calculated Price
                  {activeDomainPack.unit?.code ? ` (${activeDomainPack.unit.code})` : ''}
                </div>
                <div className="price-main">
                  {typeof result.price === 'number'
                    ? `${currencySymbol}${result.price.toLocaleString(undefined, {
                        minimumFractionDigits: activeDomainPack.unit?.decimals ?? 2,
                        maximumFractionDigits: activeDomainPack.unit?.decimals ?? 2,
                      })}`
                    : '—'}
                </div>
                <div className="price-sub" style={{ marginTop: '0.4rem' }}>
                  Base:{' '}
                  {typeof result.base === 'number'
                    ? `${currencySymbol}${result.base.toLocaleString(undefined, {
                        minimumFractionDigits: activeDomainPack.unit?.decimals ?? 2,
                        maximumFractionDigits: activeDomainPack.unit?.decimals ?? 2,
                      })}`
                    : '—'}
                  {' | '}
                  Fired rules:{' '}
                  {Array.isArray(result.trace)
                    ? result.trace.filter(
                        (s) =>
                          s.fired &&
                          s.stage !== 'base' &&
                          s.stage !== 'rounding' &&
                          s.stage !== 'constraints'
                      ).length
                    : 0}
                </div>
                {result.fingerprint && (
                  <div className="fingerprint-tag">
                    Fingerprint: {result.fingerprint.substring(0, 16)}…
                  </div>
                )}
                {contextStatus === 'active' && contextSnapshot && (
                  <div style={{ marginTop: '0.4rem', fontSize: '0.72rem', color: '#38bdf8' }}>
                    📡 Context Merged: {contextSnapshot.source} (fp: {contextSnapshot.fingerprint.substring(0, 8)}…)
                  </div>
                )}
              </div>

              {/* Trace Timeline */}
              <h4 style={{ margin: '1.2rem 0 0.6rem 0', fontSize: '0.95rem' }}>
                📜 Audit Trace Timeline
              </h4>

              {Array.isArray(result.trace) && result.trace.length > 0 ? (
                <div className="trace-timeline">
                  {result.trace.map((step, idx) => (
                    <div
                      key={idx}
                      className={`trace-step ${step.stage || 'rule'}`}
                      style={{ opacity: step.fired ? 1 : 0.45 }}
                    >
                      <div className="step-num">#{idx + 1}</div>
                      <div className="step-content">
                        <div className="step-title">
                          {step.stage?.toUpperCase()}: {step.rule_id || step.step}
                        </div>
                        <div className="step-desc">
                          {step.description || step.action}
                          {!step.fired && (
                            <span style={{ color: 'var(--text-dim)', marginLeft: '0.4rem' }}>
                              (skipped)
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="step-price">
                        {step.after !== undefined && step.after !== null
                          ? `${currencySymbol}${step.after.toLocaleString(undefined, {
                              minimumFractionDigits: activeDomainPack.unit?.decimals ?? 2,
                              maximumFractionDigits: activeDomainPack.unit?.decimals ?? 2,
                            })}`
                          : '—'}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>No trace data returned.</p>
              )}
            </div>
          )}
        </div>

        {/* Sweep Card */}
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">
              <span>📈</span> Price Sensitivity Sweep
            </h2>
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <select
                className="form-select"
                style={{ width: 'auto', padding: '0.3rem 0.6rem', fontSize: '0.8rem' }}
                value={sweepSignal}
                onChange={(e) => setSweepSignal(e.target.value)}
                aria-label="Sweep signal selector"
              >
                {sigArray
                  .filter((s) => s.type === 'number' || s.type === 'integer')
                  .map((s) => (
                    <option key={s.key} value={s.key}>
                      {s.key}
                    </option>
                  ))}
              </select>
              <button
                className="btn btn-secondary"
                style={{ padding: '0.3rem 0.7rem', fontSize: '0.8rem' }}
                onClick={runSweep}
                disabled={sweepLoading}
                aria-busy={sweepLoading}
              >
                {sweepLoading ? '⏳ Running…' : 'Run Sweep'}
              </button>
            </div>
          </div>

          {sweepError && (
            <div
              role="alert"
              style={{
                padding: '0.6rem 0.8rem',
                marginBottom: '0.75rem',
                borderRadius: '8px',
                background: 'rgba(239,68,68,0.12)',
                border: '1px solid rgba(239,68,68,0.4)',
                color: '#fca5a5',
                fontSize: '0.82rem',
              }}
            >
              ⚠️ {sweepError}
            </div>
          )}

          {sweepResults.length > 0 ? (
            <table className="table" style={{ marginTop: '0.5rem' }}>
              <thead>
                <tr>
                  <th>{sweepSignal}</th>
                  <th>Resulting Price</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {sweepResults.map((pt, i) => (
                  <tr key={i}>
                    <td>{pt.signal_value}</td>
                    <td style={{ fontWeight: 600, color: pt.error ? 'var(--danger)' : '#10b981' }}>
                      {pt.error
                        ? '—'
                        : `${currencySymbol}${
                            typeof pt.price === 'number'
                              ? pt.price.toLocaleString(undefined, {
                                  minimumFractionDigits: activeDomainPack.unit?.decimals ?? 2,
                                  maximumFractionDigits: activeDomainPack.unit?.decimals ?? 2,
                                })
                              : pt.price
                          }`}
                    </td>
                    <td>
                      {pt.error ? (
                        <span className="badge badge-danger" title={pt.error}>
                          Error
                        </span>
                      ) : (
                        <span className="badge badge-success">OK</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
              Select a numeric signal and click 'Run Sweep' to analyze price sensitivity across its full range.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
