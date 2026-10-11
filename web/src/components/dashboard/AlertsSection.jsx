import React, { useState } from 'react';
import { 
  AlertTriangle, 
  Sparkles, 
  CheckCircle, 
  ShieldAlert, 
  Lightbulb, 
  ArrowRight,
  PlusCircle,
  CheckCircle2,
  Info
} from 'lucide-react';

export default function AlertsSection({ alerts, loading, onNavigateTab }) {
  const alertList = alerts || [];
  const [appliedAlerts, setAppliedAlerts] = useState({});

  const handleApplyAlert = (alt) => {
    setAppliedAlerts((prev) => ({ ...prev, [alt.id]: true }));
    if (onNavigateTab) {
      setTimeout(() => {
        onNavigateTab('studio');
      }, 600);
    }
  };

  return (
    <div className="dash-section" id="alerts-opportunities-section">
      <div className="dash-section-header">
        <div>
          <h2 className="dash-section-title">Alerts &amp; Opportunities</h2>
          <p className="dash-section-subtitle">
            Explainable notifications driven by simple threshold logic. Observed facts are strictly separated from recommendations.
          </p>
        </div>

        <div className="dash-badge-telemetry">
          <AlertTriangle size={14} />
          <span>{alertList.length} Active Notice{alertList.length === 1 ? '' : 's'}</span>
        </div>
      </div>

      {alertList.length === 0 ? (
        <div className="dash-empty-alerts-card">
          <CheckCircle size={32} color="#059669" />
          <div className="dash-empty-alerts-title">All Engine Metrics Nominal</div>
          <p className="dash-empty-alerts-desc">
            No threshold triggers detected. Floor/ceiling guardrails, price spreads, and inventory limits are currently operating within expected standard ranges.
          </p>
        </div>
      ) : (
        <div className="dash-alerts-grid">
          {alertList.map((alt) => {
            const isWarning = alt.type === 'warning';
            const isApplied = !!appliedAlerts[alt.id];

            return (
              <div key={alt.id} className={`dash-alert-card ${isWarning ? 'warning' : 'opportunity'}`}>
                <div className="dash-alert-header">
                  <div className="dash-alert-title-wrap">
                    <span className={`dash-alert-icon-box ${isWarning ? 'warning' : 'opportunity'}`}>
                      {isWarning ? <ShieldAlert size={18} /> : <Lightbulb size={18} />}
                    </span>
                    <div>
                      <h4 className="dash-alert-title">{alt.title}</h4>
                      <span className="dash-alert-badge">{isWarning ? 'Rule Threshold Warning' : 'Margin Opportunity'}</span>
                    </div>
                  </div>
                  <span className="dash-alert-domain">{alt.domain || 'ecommerce'}</span>
                </div>

                <div className="dash-alert-body">
                  <div className="dash-fact-box">
                    <div className="dash-box-label">
                      <span className="dash-dot-fact" />
                      <strong>Observed Fact (Telemetry):</strong>
                    </div>
                    <p className="dash-fact-text">{alt.fact}</p>
                  </div>

                  <div className="dash-rec-box">
                    <div className="dash-box-label">
                      <span className="dash-dot-rec" />
                      <strong>Recommended Action:</strong>
                    </div>
                    <p className="dash-rec-text">{alt.recommendation}</p>
                  </div>

                  {/* Single-click Action Buttons */}
                  <div style={{ marginTop: '0.85rem', display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                    <button
                      className={`dash-action-btn ${isApplied ? 'success' : ''}`}
                      onClick={() => handleApplyAlert(alt)}
                      id={`apply-alert-${alt.id}`}
                      title="Apply recommendation in Rule Studio"
                    >
                      {isApplied ? <CheckCircle2 size={13} /> : <PlusCircle size={13} />}
                      <span>{isApplied ? '✓ Applied (Opening Studio...)' : '+ 1-Click Apply to Studio'}</span>
                    </button>

                    {onNavigateTab && (
                      <button
                        className="dash-action-btn secondary"
                        onClick={() => onNavigateTab('studio')}
                        title="Open Rule Studio directly"
                      >
                        <span>Open Studio</span>
                        <ArrowRight size={12} />
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
