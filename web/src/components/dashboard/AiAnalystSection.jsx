import React, { useState } from 'react';
import { 
  Bot, 
  Send, 
  Sparkles, 
  ShieldCheck, 
  HelpCircle, 
  AlertCircle,
  Database,
  ArrowRight
} from 'lucide-react';
import { queryAnalyticsAnalyst } from '../../api';

const SAMPLE_QUERIES = [
  "Which domain had the most sales?",
  "How did pricing change over this period?",
  "Which pricing rules triggered most frequently?",
  "How often did floor constraints trigger?",
  "What is our gross profit margin?",
];

export default function AiAnalystSection({ activeDomain }) {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState(null);
  const [error, setError] = useState(null);

  const handleAsk = async (queryText) => {
    const textToSubmit = queryText || query;
    if (!textToSubmit.trim()) return;

    setLoading(true);
    setError(null);
    try {
      const res = await queryAnalyticsAnalyst(textToSubmit, activeDomain);
      if (res.error) {
        setError(res.error);
        setResponse(null);
      } else {
        setResponse(res.data);
      }
    } catch (err) {
      setError(err.message || 'Failed to query analyst');
    } finally {
      setLoading(false);
    }
  };

  const handleSampleClick = (sample) => {
    setQuery(sample);
    handleAsk(sample);
  };

  return (
    <div className="dash-section" id="ai-analyst-section">
      <div className="dash-section-header">
        <div>
          <h2 className="dash-section-title">AI Business Analyst</h2>
          <p className="dash-section-subtitle">
            Natural-language question answering grounded in verified system metrics and pricing traces.
          </p>
        </div>

        <div className="dash-analyst-guardrail-badge">
          <ShieldCheck size={14} />
          <span>Read-Only Analyst · Zero Mutation</span>
        </div>
      </div>

      {/* Query Bar */}
      <div className="dash-analyst-box">
        <form
          className="dash-analyst-input-form"
          onSubmit={(e) => {
            e.preventDefault();
            handleAsk();
          }}
        >
          <Bot className="dash-analyst-input-icon" size={20} />
          <input
            type="text"
            className="dash-analyst-input"
            placeholder="Ask a question (e.g. Which domain had the most sales? Which rules fired?)"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <button
            type="submit"
            className="dash-analyst-submit-btn"
            disabled={loading || !query.trim()}
          >
            {loading ? (
              <span>Analyzing...</span>
            ) : (
              <>
                <span>Ask</span>
                <Send size={15} />
              </>
            )}
          </button>
        </form>

        {/* Quick Suggestion Chips */}
        <div className="dash-sample-chips">
          <span className="dash-sample-label">Suggested Questions:</span>
          {SAMPLE_QUERIES.map((sample) => (
            <button
              key={sample}
              type="button"
              className="dash-chip-btn"
              onClick={() => handleSampleClick(sample)}
            >
              <span>{sample}</span>
              <ArrowRight size={12} />
            </button>
          ))}
        </div>

        {/* Error State */}
        {error && (
          <div className="dash-analyst-error">
            <AlertCircle size={16} />
            <span>{error}</span>
          </div>
        )}

        {/* Response Box */}
        {response && (
          <div className="dash-analyst-response-card">
            <div className="dash-analyst-response-header">
              <div className="dash-analyst-avatar">
                <Sparkles size={16} />
              </div>
              <div>
                <div className="dash-analyst-name">RateWeaver Evidence-Based Analyst</div>
                <div className="dash-analyst-status">
                  {response.can_answer ? 'Verified Ground Truth' : 'Data Boundary Reached'}
                </div>
              </div>
            </div>

            <div className="dash-analyst-body">
              <p className="dash-analyst-text">{response.answer}</p>

              {/* Evidence Panel */}
              {response.evidence && Object.keys(response.evidence).length > 0 && (
                <div className="dash-evidence-panel">
                  <div className="dash-evidence-title">
                    <Database size={13} />
                    <span>Authoritative Evidence Cited</span>
                  </div>
                  <pre className="dash-evidence-json">
                    {JSON.stringify(response.evidence, null, 2)}
                  </pre>
                </div>
              )}

              {/* Limitation Notice if data unavailable */}
              {response.limitation_note && (
                <div className="dash-limitation-notice">
                  <HelpCircle size={15} />
                  <span>
                    <strong>Tracking Limitation:</strong> {response.limitation_note}
                  </span>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
