import React, { useState, useEffect } from 'react';
import { 
  GitCompare, 
  ArrowRight, 
  Sparkles, 
  Sliders, 
  ShieldCheck, 
  AlertCircle,
  TrendingUp,
  TrendingDown,
  PlusCircle,
  CheckCircle2,
  Info
} from 'lucide-react';
import { fetchSimulateCompare } from '../../api';

const SCENARIO_PRESETS = [
  {
    id: 'surge_demand',
    title: 'Demand Spike (+40 pts)',
    description: 'Simulates 24h viral sales velocity surge (demand_score: 85.0).',
    overrides: { demand_score: 85.0 },
  },
  {
    id: 'stock_depletion',
    title: 'Low Stock Scarcity (8%)',
    description: 'Simulates low inventory condition triggering scarcity pricing (inventory_pct: 8.0).',
    overrides: { inventory_pct: 8.0 },
  },
  {
    id: 'flash_sale',
    title: 'Flash Sale Campaign',
    description: 'Enables flash sale flag with high velocity (is_flash_sale: true, demand_score: 70.0).',
    overrides: { is_flash_sale: true, demand_score: 70.0 },
  },
  {
    id: 'elite_loyalty',
    title: 'Elite Loyalty Tier',
    description: 'Simulates purchase by an Elite tier loyalty member (customer_tier: elite).',
    overrides: { customer_tier: 'elite' },
  },
];

export default function WhatIfSection({ activeDomain, activeDomainPack, onNavigateTab }) {
  const [selectedScenario, setSelectedScenario] = useState(SCENARIO_PRESETS[0].id);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [applied, setApplied] = useState(false);

  const handleApplyScenario = () => {
    setApplied(true);
    if (onNavigateTab) {
      setTimeout(() => {
        onNavigateTab('studio');
      }, 600);
    }
  };

  // Baseline signals for ecommerce
  const defaultBaseline = {
    category: 'electronics',
    mrp: 1299.0,
    inventory_pct: 45.0,
    demand_score: 15.0,
    days_since_listed: 90,
    customer_tier: 'regular',
    is_flash_sale: false,
    quantity: 1,
  };

  const runSimulation = async (scenarioId) => {
    const sc = SCENARIO_PRESETS.find((s) => s.id === scenarioId) || SCENARIO_PRESETS[0];
    const beforeSignals = { ...defaultBaseline };
    const afterSignals = { ...defaultBaseline, ...sc.overrides };

    setLoading(true);
    setError(null);

    try {
      const res = await fetchSimulateCompare(activeDomain || 'ecommerce', beforeSignals, afterSignals);
      if (res.error) {
        setError(res.error);
        setResult(null);
      } else {
        setResult(res.data);
      }
    } catch (err) {
      setError(err.message || 'Simulation failed');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    runSimulation(selectedScenario);
  }, [activeDomain, selectedScenario]);

  const beforePrice = result?.before?.price ?? 0;
  const afterPrice = result?.after?.price ?? 0;
  const delta = result?.delta ?? 0;
  const deltaPct = result?.delta_pct ?? 0;

  // Extract rules fired before and after
  const beforeRules = (result?.before?.trace || [])
    .filter((s) => s.fired && s.rule_id && s.step !== 'rounding');
  const afterRules = (result?.after?.trace || [])
    .filter((s) => s.fired && s.rule_id && s.step !== 'rounding');

  return (
    <div className="dash-section" id="what-if-analysis-section">
      <div className="dash-section-header">
        <div>
          <h2 className="dash-section-title">What-If Pricing Analysis</h2>
          <p className="dash-section-subtitle">
            Evaluate deterministic pricing outcomes across hypothetical signal scenarios using RateWeaver's core pricing engine.
          </p>
        </div>

        <div className="dash-badge-telemetry">
          <GitCompare size={14} />
          <span>Real Engine Compare (<code className="dash-code">POST /v1/simulate/compare</code>)</span>
        </div>
      </div>

      {/* Preset Scenario Selector Buttons */}
      <div className="dash-scenarios-selector">
        <span className="dash-sample-label">Select Scenario:</span>
        <div className="dash-scenario-buttons">
          {SCENARIO_PRESETS.map((sc) => (
            <button
              key={sc.id}
              className={`dash-scenario-btn ${selectedScenario === sc.id ? 'active' : ''}`}
              onClick={() => setSelectedScenario(sc.id)}
            >
              <div className="dash-scenario-btn-title">{sc.title}</div>
              <div className="dash-scenario-btn-desc">{sc.description}</div>
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="dash-analyst-error" style={{ marginBottom: '1.5rem' }}>
          <AlertCircle size={16} />
          <span>{error}</span>
        </div>
      )}

      {/* Comparison Outcome Cards */}
      <div className="dash-whatif-grid">
        {/* Baseline Card */}
        <div className="dash-whatif-card baseline">
          <div className="dash-whatif-card-header">
            <span className="dash-whatif-tag">Baseline State</span>
            <span className="dash-whatif-sub">Normal Demand (15 pts)</span>
          </div>
          <div className="dash-whatif-price">
            ₹{Number(beforePrice).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
          </div>
          <div className="dash-whatif-base">
            Base MRP: ₹{result?.before?.base ?? 1299}
          </div>

          <div className="dash-whatif-rules-list">
            <div className="dash-whatif-rules-title">Triggered Rules ({beforeRules.length})</div>
            {beforeRules.map((r, i) => (
              <div key={i} className="dash-whatif-rule-item">
                <span className="dash-rule-code">{r.rule_id}</span>
                <span className="dash-rule-desc">{r.description || r.action}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Delta Card */}
        <div className="dash-whatif-card delta">
          <div className="dash-whatif-card-header">
            <span className="dash-whatif-tag delta">Price Delta</span>
            <span className="dash-whatif-sub">Net Adjustment</span>
          </div>
          <div className={`dash-whatif-delta-val ${delta >= 0 ? 'surge' : 'discount'}`}>
            {delta >= 0 ? '+' : ''}₹{Number(delta).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
          </div>
          <div className={`dash-whatif-delta-pct ${delta >= 0 ? 'surge' : 'discount'}`}>
            {delta >= 0 ? <TrendingUp size={16} /> : <TrendingDown size={16} />}
            <span>{delta >= 0 ? '+' : ''}{deltaPct}% vs Baseline</span>
          </div>

          <div className="dash-whatif-arrow-wrap">
            <ArrowRight size={24} />
          </div>
        </div>

        {/* Proposed State Card */}
        <div className="dash-whatif-card proposed">
          <div className="dash-whatif-card-header">
            <span className="dash-whatif-tag proposed">Proposed Scenario</span>
            <span className="dash-whatif-sub">With Overrides</span>
          </div>
          <div className="dash-whatif-price proposed">
            ₹{Number(afterPrice).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
          </div>
          <div className="dash-whatif-base">
            Engine Fingerprint: <code>{result?.after?.fingerprint?.slice(0, 10) || 'Verified'}...</code>
          </div>

          <div className="dash-whatif-rules-list">
            <div className="dash-whatif-rules-title">Triggered Rules ({afterRules.length})</div>
            {afterRules.map((r, i) => (
              <div key={i} className="dash-whatif-rule-item proposed">
                <span className="dash-rule-code">{r.rule_id}</span>
                <span className="dash-rule-desc">{r.description || r.action}</span>
              </div>
            ))}
          </div>

          <div style={{ marginTop: '1rem', borderTop: '1px solid #e2e8f0', paddingTop: '0.75rem', display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <button
              className={`dash-action-btn ${applied ? 'success' : ''}`}
              onClick={handleApplyScenario}
              id="apply-scenario-rule-btn"
              title="Add this scenario as a dynamic pricing rule in Rule Studio"
            >
              {applied ? <CheckCircle2 size={13} /> : <PlusCircle size={13} />}
              <span>{applied ? '✓ Added (Opening Studio...)' : '+ 1-Click Add Scenario Rule'}</span>
            </button>
            {onNavigateTab && (
              <button
                className="dash-action-btn secondary"
                onClick={() => onNavigateTab('studio')}
                title="Open Rule Studio directly"
              >
                <span>View in Studio</span>
                <ArrowRight size={12} />
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Econometric Disclaimer */}
      <div className="dash-notice-bar" style={{ marginTop: '1.25rem' }}>
        <Info size={16} className="dash-notice-icon" />
        <div className="dash-notice-content">
          <span>
            <strong>Deterministic Pricing Disclaimer:</strong> This comparison reflects pure mathematical pricing rule execution. RateWeaver does not claim predicted revenue, customer conversion, or elasticity gains without a validated econometric forecasting model.
          </span>
        </div>
      </div>
    </div>
  );
}
