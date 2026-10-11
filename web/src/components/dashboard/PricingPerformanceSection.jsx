import React from 'react';
import { 
  Zap, 
  ShieldAlert, 
  Activity, 
  TrendingUp, 
  CheckCircle2, 
  Sliders,
  AlertTriangle,
  Info
} from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

export default function PricingPerformanceSection({ performanceData, activeDomain, onNavigateTab }) {
  const evalCount = performanceData?.evaluation_count || 0;
  const priceTrend = performanceData?.price_trend || [];
  const topRules = performanceData?.top_rules || [];
  const constraintHits = performanceData?.constraint_hits || [];

  return (
    <div className="dash-section" id="pricing-performance-section">
      <div className="dash-section-header">
        <div>
          <h2 className="dash-section-title">Pricing Performance</h2>
          <p className="dash-section-subtitle">
            Telemetry from real-time pricing engine evaluations (<code className="dash-code">POST /v1/price</code>). Strictly distinguished from completed sales transactions.
          </p>
        </div>

        <div className="dash-badge-telemetry">
          <Activity size={14} className="dash-live-dot" />
          <span>{evalCount} Price Quotes Evaluated</span>
        </div>
      </div>

      {/* KPI Cards for Pricing Engine */}
      <div className="dash-kpi-grid">
        <div className="dash-kpi-card">
          <div className="dash-kpi-header">
            <span className="dash-kpi-label">Pricing Evaluations</span>
            <span className="dash-kpi-icon-wrap emerald">
              <Zap size={18} />
            </span>
          </div>
          <div className="dash-kpi-value">{evalCount}</div>
          <div className="dash-kpi-meta">Logged in cryptographic audit trail</div>
        </div>

        <div className="dash-kpi-card">
          <div className="dash-kpi-header">
            <span className="dash-kpi-label">Active Rules Fired</span>
            <span className="dash-kpi-icon-wrap blue">
              <Sliders size={18} />
            </span>
          </div>
          <div className="dash-kpi-value">{topRules.length}</div>
          <div className="dash-kpi-meta">Unique rules triggered in traces</div>
        </div>

        <div className="dash-kpi-card">
          <div className="dash-kpi-header">
            <span className="dash-kpi-label">Guardrail Clamps</span>
            <span className="dash-kpi-icon-wrap amber">
              <ShieldAlert size={18} />
            </span>
          </div>
          <div className="dash-kpi-value">
            {constraintHits.reduce((acc, c) => acc + c.count, 0)}
          </div>
          <div className="dash-kpi-meta">Floor / ceiling boundary enforcements</div>
        </div>

        <div className="dash-kpi-card">
          <div className="dash-kpi-header">
            <span className="dash-kpi-label">Execution Determinism</span>
            <span className="dash-kpi-icon-wrap purple">
              <CheckCircle2 size={18} />
            </span>
          </div>
          <div className="dash-kpi-value">100%</div>
          <div className="dash-kpi-meta">Pure mathematical rule evaluation</div>
        </div>
      </div>

      {/* Real Pricing Evaluation Trend Line Chart */}
      <div className="dash-chart-card" style={{ marginBottom: '1.5rem' }}>
        <div className="dash-chart-header">
          <div>
            <h3 className="dash-chart-title">Dynamic Price Quote Trend</h3>
            <p className="dash-chart-subtitle">
              Calculated prices over consecutive requests in domain: <strong>{activeDomain}</strong>
            </p>
          </div>
          <span className="dash-chart-badge">{priceTrend.length} data points</span>
        </div>
        <div className="dash-chart-body" style={{ height: 260 }}>
          {priceTrend.length === 0 ? (
            <div className="dash-empty-state">
              No recent pricing evaluations recorded. Run a calculation in the Simulator or browse the Live Store.
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={priceTrend} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                <XAxis dataKey="timestamp" stroke="#94a3b8" fontSize={11} tickLine={false} />
                <YAxis stroke="#94a3b8" fontSize={11} tickLine={false} />
                <Tooltip
                  contentStyle={{ background: '#fff', borderRadius: '8px', border: '1px solid #e2e8f0' }}
                  formatter={(val) => [`₹${val}`, 'Dynamic Price']}
                />
                <Line
                  type="monotone"
                  dataKey="price"
                  stroke="#0f766e"
                  strokeWidth={2.5}
                  dot={{ r: 3, fill: '#0f766e' }}
                  activeDot={{ r: 6 }}
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Rules Fired & Guardrail Hits Side-by-Side */}
      <div className="dash-two-col-grid">
        {/* Most Triggered Rules */}
        <div className="dash-table-card">
          <div className="dash-chart-header">
            <h3 className="dash-chart-title">Most Frequently Triggered Rules</h3>
            <span className="dash-chart-badge">From Trace Logs</span>
          </div>
          <div className="dash-table-wrap">
            <table className="dash-table">
              <thead>
                <tr>
                  <th>Rule ID</th>
                  <th>Stage</th>
                  <th style={{ textAlign: 'right' }}>Fired Count</th>
                  <th style={{ textAlign: 'right' }}>Trigger Rate</th>
                  {onNavigateTab && <th style={{ textAlign: 'right' }}>Action</th>}
                </tr>
              </thead>
              <tbody>
                {topRules.length === 0 ? (
                  <tr>
                    <td colSpan={onNavigateTab ? 5 : 4} style={{ textAlign: 'center', padding: '1.5rem' }}>
                      No rule triggers recorded yet.
                    </td>
                  </tr>
                ) : (
                  topRules.slice(0, 6).map((r) => (
                    <tr key={r.rule_id}>
                      <td>
                        <span className="dash-rule-code">{r.rule_id}</span>
                        <div className="dash-cell-subtext">{r.description}</div>
                      </td>
                      <td>
                        <span className="dash-stage-tag">{r.stage}</span>
                      </td>
                      <td style={{ textAlign: 'right', fontWeight: 600 }}>{r.count}</td>
                      <td style={{ textAlign: 'right', fontWeight: 700, color: '#0f766e' }}>
                        {r.trigger_pct}%
                      </td>
                      {onNavigateTab && (
                        <td style={{ textAlign: 'right' }}>
                          <button
                            className="dash-action-btn secondary"
                            style={{ padding: '0.2rem 0.5rem', fontSize: '0.72rem' }}
                            onClick={() => onNavigateTab('studio')}
                            title="Edit rule in Rule Studio"
                          >
                            Edit
                          </button>
                        </td>
                      )}
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Floor / Ceiling Constraint Hits */}
        <div className="dash-table-card">
          <div className="dash-chart-header">
            <h3 className="dash-chart-title">Guardrail Constraint Hits</h3>
            <span className="dash-chart-badge">Floor &amp; Ceiling</span>
          </div>
          <div className="dash-table-wrap">
            <table className="dash-table">
              <thead>
                <tr>
                  <th>Constraint</th>
                  <th>Action</th>
                  <th style={{ textAlign: 'right' }}>Hits</th>
                  <th style={{ textAlign: 'right' }}>Clamp Rate</th>
                  {onNavigateTab && <th style={{ textAlign: 'right' }}>Action</th>}
                </tr>
              </thead>
              <tbody>
                {constraintHits.length === 0 ? (
                  <tr>
                    <td colSpan={onNavigateTab ? 5 : 4} style={{ textAlign: 'center', padding: '1.5rem' }}>
                      <div className="dash-clean-guardrails">
                        <CheckCircle2 size={18} color="#059669" />
                        <span>Zero constraint violations. All evaluated prices fell cleanly within bounds.</span>
                      </div>
                    </td>
                  </tr>
                ) : (
                  constraintHits.map((c) => (
                    <tr key={c.constraint_id}>
                      <td>
                        <span className="dash-constraint-code">{c.constraint_id}</span>
                        <div className="dash-cell-subtext">{c.description}</div>
                      </td>
                      <td>
                        <span className="dash-bound-tag">{c.type}</span>
                      </td>
                      <td style={{ textAlign: 'right', fontWeight: 600 }}>{c.count}</td>
                      <td style={{ textAlign: 'right', fontWeight: 700, color: '#d97706' }}>
                        {c.hit_pct}%
                      </td>
                      {onNavigateTab && (
                        <td style={{ textAlign: 'right' }}>
                          <button
                            className="dash-action-btn secondary"
                            style={{ padding: '0.2rem 0.5rem', fontSize: '0.72rem' }}
                            onClick={() => onNavigateTab('validation')}
                            title="Inspect in Guardrails View"
                          >
                            Inspect
                          </button>
                        </td>
                      )}
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
