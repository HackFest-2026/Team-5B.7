/**
 * ProductDetail.jsx — Modal overlay showing full product detail.
 *
 * Features:
 *   - Product image (with fallback emoji)
 *   - Full name, category, description, star rating
 *   - Live price fetched via useProductPricing (quantity-aware)
 *   - MRP and savings display
 *   - Collapsible pricing trace from backend response
 *   - Quantity selector (1–99)
 *   - Add to Cart action
 *
 * The backend trace shows which pricing rules fired and why the price changed.
 * This is shown as a customer-friendly "Why this price?" panel.
 */
import React, { useState, useEffect } from 'react';
import { useProductPricing } from '../../hooks/useEcommercePricing.js';
import { fetchStoreRecommendations } from '../../api.js';

const CAT_EMOJI = {
  electronics: '📱',
  fashion: '👕',
  grocery: '🛒',
  home_appliances: '🏠',
  beauty: '✨',
};

function StarsFull({ rating }) {
  const full  = Math.floor(rating);
  const half  = rating - full >= 0.5;
  return (
    <span style={{ color: '#f59e0b', letterSpacing: '1px' }}>
      {'★'.repeat(full)}{half ? '½' : ''}
      {'☆'.repeat(5 - full - (half ? 1 : 0))}
    </span>
  );
}

/**
 * Build customer-friendly trace explanations.
 * Only shows fired rules with meaningful price changes.
 */
function buildTraceExplanations(trace) {
  if (!Array.isArray(trace) || trace.length === 0) return [];

  const rows = [];
  for (const step of trace) {
    if (step.stage === 'rounding') continue;
    if (step.before === null || step.before === undefined) {
      // Base price step
      rows.push({
        label: 'Base price (MRP)',
        amount: step.after,
        fired: true,
        isBold: true,
      });
      continue;
    }

    if (!step.fired) continue; // skip non-fired rules

    const delta = (step.after ?? 0) - (step.before ?? 0);
    if (Math.abs(delta) < 0.01) continue; // skip no-ops

    rows.push({
      label: step.description || step.rule_id || step.step,
      amount: step.after,
      delta,
      fired: true,
    });
  }
  return rows;
}

export default function ProductDetail({
  product,
  storeContext,
  onAddToCart,
  onClose,
  onSelectProduct,
}) {
  const [qty, setQty]                         = useState(1);
  const [imgError, setImgError]               = useState(false);
  const [showTrace, setShowTrace]             = useState(false);
  const [added, setAdded]                     = useState(false);
  const [recommendations, setRecommendations] = useState([]);

  const isOutOfStock = product?.stock !== undefined && product.stock <= 0;
  const maxStock = product?.stock !== undefined ? Math.max(1, product.stock) : 99;

  useEffect(() => {
    if (product?.id) {
      fetchStoreRecommendations(product.id, 3).then(({ data }) => {
        if (data) setRecommendations(data);
      });
    }
  }, [product?.id]);

  const { priceResult, loading, error } = useProductPricing(product, storeContext, qty);

  if (!product) return null;

  const mrp       = product.signals?.mrp || product.mrp;
  const livePrice = priceResult?.price;
  const showSave  = typeof livePrice === 'number' && livePrice < mrp * 0.99;
  const savePct   = showSave ? Math.round(((mrp - livePrice) / mrp) * 100) : 0;
  const saveAmt   = showSave ? (mrp - livePrice) : 0;

  const emoji = CAT_EMOJI[product.signals?.category || product.category] ?? '📦';

  const handleAdd = () => {
    if (!livePrice || loading || isOutOfStock) return;
    onAddToCart(product, priceResult, qty);
    setAdded(true);
    setTimeout(() => {
      setAdded(false);
      onClose();
    }, 1200);
  };

  const traceRows = buildTraceExplanations(priceResult?.trace ?? []);

  return (
    <div
      className="s-modal-overlay"
      onClick={(e) => e.target === e.currentTarget && onClose()}
      role="dialog"
      aria-modal="true"
      aria-label={`Product detail: ${product.name}`}
      id="product-detail-modal"
    >
      <div className="s-modal">
        {/* Image pane */}
        <div className="s-modal-img-pane">
          <button
            className="s-modal-close"
            onClick={onClose}
            aria-label="Close product detail"
            id="product-detail-close"
          >
            ✕
          </button>
          {!imgError ? (
            <img
              src={product.imageUrl}
              alt={product.name}
              onError={() => setImgError(true)}
            />
          ) : (
            <div className="s-modal-img-fallback">{emoji}</div>
          )}
        </div>

        {/* Info pane */}
        <div className="s-modal-body">
          <div className="s-modal-cat">{product.category_label}</div>
          <h2 className="s-modal-name">{product.name}</h2>

          <div className="s-modal-rating">
            <StarsFull rating={product.rating} />
            <span style={{ color: 'var(--s-text-muted)', fontSize: '0.85rem' }}>
              {product.rating} · {product.reviewCount?.toLocaleString()} reviews
            </span>
          </div>

          <p className="s-modal-desc">{product.shortDesc}</p>

          {/* Price box */}
          <div className="s-modal-price-box">
            {loading ? (
              <div>
                <span className="s-price-loading" style={{ width: 120, height: 24, display: 'inline-block' }} />
                <div style={{ fontSize: '0.8rem', color: 'var(--s-text-dim)', marginTop: '0.4rem' }}>
                  Calculating best price…
                </div>
              </div>
            ) : error ? (
              <div style={{ color: 'var(--s-danger)', fontSize: '0.9rem' }}>
                ⚠️ Price unavailable
                <div style={{ fontSize: '0.78rem', color: 'var(--s-text-muted)', marginTop: '0.25rem' }}>
                  MRP: ₹{mrp.toLocaleString('en-IN')}
                </div>
              </div>
            ) : livePrice !== undefined ? (
              <>
                <div className="s-modal-price-live">
                  ₹{livePrice.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                </div>
                <div className="s-modal-price-row">
                  {showSave && (
                    <>
                      <span className="s-modal-mrp">MRP ₹{mrp.toLocaleString('en-IN')}</span>
                      <span className="s-modal-saving">
                        Save ₹{saveAmt.toLocaleString('en-IN', { maximumFractionDigits: 0 })} ({savePct}% off)
                      </span>
                    </>
                  )}
                </div>
                {traceRows.length > 0 && (
                  <button
                    className="s-modal-trace-btn"
                    onClick={() => setShowTrace((p) => !p)}
                    id="trace-toggle-btn"
                  >
                    {showTrace ? '▲ Hide' : '▼ Why this price?'}
                  </button>
                )}
              </>
            ) : null}
          </div>

          {/* Pricing trace */}
          {showTrace && traceRows.length > 0 && (
            <div className="s-trace-panel">
              <h4>🔍 Pricing breakdown</h4>
              {traceRows.map((row, i) => (
                <div key={i} className={`s-trace-row ${!row.fired ? 's-trace-skipped' : ''}`}>
                  <span className="s-trace-desc">{row.label}</span>
                  <span className="s-trace-amount">
                    {row.delta !== undefined && row.delta !== 0 && (
                      <span style={{ color: row.delta < 0 ? 'var(--s-success)' : 'var(--s-danger)', marginRight: 4 }}>
                        {row.delta < 0 ? '▼' : '▲'} ₹{Math.abs(row.delta).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                      </span>
                    )}
                    ₹{(row.amount ?? 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* Live stock indicator */}
          <div style={{ fontSize: '0.85rem', fontWeight: 600 }}>
            {isOutOfStock ? (
              <span style={{ color: 'var(--s-danger)' }}>❌ Currently Out of Stock</span>
            ) : product.stock !== undefined && product.stock <= 5 ? (
              <span style={{ color: 'var(--s-warning)' }}>⚡ Only {product.stock} units remaining in stock</span>
            ) : product.stock !== undefined ? (
              <span style={{ color: 'var(--s-success)' }}>✓ In Stock ({product.stock} units available)</span>
            ) : null}
          </div>

          {/* Quantity + Add to Cart */}
          {!isOutOfStock && (
            <div className="s-qty-row">
              <label style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--s-text-muted)' }}>
                Qty:
              </label>
              <div className="s-qty-control">
                <button
                  className="s-qty-btn"
                  onClick={() => setQty((q) => Math.max(1, q - 1))}
                  disabled={qty <= 1}
                  aria-label="Decrease quantity"
                  id="detail-qty-dec"
                >−</button>
                <span className="s-qty-val" aria-live="polite">{qty}</span>
                <button
                  className="s-qty-btn"
                  onClick={() => setQty((q) => Math.min(maxStock, q + 1))}
                  disabled={qty >= maxStock}
                  aria-label="Increase quantity"
                  id="detail-qty-inc"
                >+</button>
              </div>
              {qty > 1 && livePrice && (
                <span style={{ fontSize: '0.85rem', color: 'var(--s-text-muted)' }}>
                  Total: ₹{(livePrice * qty).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                </span>
              )}
            </div>
          )}

          <button
            className="s-modal-add-btn"
            onClick={handleAdd}
            disabled={loading || !!error || !livePrice || added || isOutOfStock}
            id="detail-add-to-cart-btn"
            style={isOutOfStock ? { background: 'var(--s-border)', color: 'var(--s-text-dim)', cursor: 'not-allowed' } : {}}
          >
            {isOutOfStock ? 'Out of Stock' : added ? '✓ Added to Cart!' : `🛒 Add ${qty > 1 ? `${qty}×` : ''} to Cart`}
          </button>

          {/* Fingerprint (demo context) */}
          {priceResult?.fingerprint && (
            <div style={{
              fontSize: '0.7rem',
              color: 'var(--s-text-dim)',
              background: 'var(--s-surface-2)',
              borderRadius: 6,
              padding: '0.4rem 0.6rem',
              fontFamily: 'monospace',
              wordBreak: 'break-all',
            }}>
              🔑 {priceResult.fingerprint.substring(0, 24)}…
            </div>
          )}

          {/* Recommendations: "You May Also Like" */}
          {recommendations.length > 0 && (
            <div style={{ marginTop: '1.25rem', paddingTop: '1.25rem', borderTop: '1px solid var(--s-border)' }}>
              <div style={{ fontSize: '0.9rem', fontWeight: 700, marginBottom: '0.75rem', color: 'var(--s-text)' }}>
                ✨ You May Also Like
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(130px, 1fr))', gap: '0.6rem' }}>
                {recommendations.map((rec) => (
                  <div
                    key={rec.id}
                    onClick={() => onSelectProduct && onSelectProduct(rec)}
                    style={{
                      background: 'var(--s-surface-2)',
                      border: '1px solid var(--s-border)',
                      borderRadius: 8,
                      padding: '0.5rem',
                      cursor: onSelectProduct ? 'pointer' : 'default',
                      textAlign: 'center',
                    }}
                  >
                    <img
                      src={rec.image_url}
                      alt={rec.name}
                      style={{ width: '100%', height: 70, objectFit: 'cover', borderRadius: 6, marginBottom: '0.3rem' }}
                      onError={(e) => { e.currentTarget.style.display = 'none'; }}
                    />
                    <div style={{ fontSize: '0.75rem', fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {rec.name}
                    </div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--s-accent)', fontWeight: 700 }}>
                      ₹{rec.mrp}
                    </div>
                    <div style={{ fontSize: '0.68rem', color: rec.stock <= 5 ? 'var(--s-warning)' : 'var(--s-text-muted)' }}>
                      {rec.stock <= 5 ? `⚡ ${rec.stock} left` : `Stock: ${rec.stock}`}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
