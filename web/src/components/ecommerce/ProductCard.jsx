/**
 * ProductCard.jsx — Individual product card in the catalogue grid.
 *
 * Displays:
 *   - Product image with category emoji fallback
 *   - Category label, name, star rating
 *   - Live price from RateWeaver backend (loading shimmer / error state)
 *   - MRP and savings badge when price < MRP
 *   - Contextual badge (Hot / Sale / Low Stock / New)
 *   - Add to Cart button
 *
 * Price data comes from the parent via the `priceData` prop.
 * priceData shape: { price, base } | null
 * priceError: string | null
 * priceLoading: boolean
 */
import React, { useState } from 'react';

const CAT_EMOJI = {
  electronics: '📱',
  fashion: '👕',
  grocery: '🛒',
  home_appliances: '🏠',
  beauty: '✨',
};

function StarRating({ rating }) {
  const full  = Math.floor(rating);
  const half  = rating - full >= 0.5 ? 1 : 0;
  const empty = 5 - full - half;
  return (
    <span className="s-card-stars" aria-label={`${rating} out of 5 stars`}>
      {'★'.repeat(full)}{'½'.repeat(half)}{'☆'.repeat(empty)}
    </span>
  );
}

function badgeFor(product) {
  if (product.stock !== undefined && product.stock <= 0) {
    return { cls: 'out-of-stock', label: 'Out of Stock' };
  }
  if (product.stock !== undefined && product.stock <= 5) {
    return { cls: 'scarce', label: `⚡ Only ${product.stock} left!` };
  }
  const { inventory_pct, demand_score, days_since_listed } = product.signals || {};
  if (inventory_pct !== undefined && inventory_pct <= 10) return { cls: 'scarce', label: 'Only a few left' };
  if (demand_score !== undefined && demand_score >= 80) return { cls: 'hot', label: '🔥 Hot' };
  if (days_since_listed !== undefined && days_since_listed <= 30) return { cls: 'new', label: 'New' };
  if ((inventory_pct !== undefined && inventory_pct > 80) || (days_since_listed !== undefined && days_since_listed > 180)) {
    return { cls: 'sale', label: 'Sale' };
  }
  return null;
}

export default function ProductCard({
  product,
  priceData,
  priceLoading,
  priceError,
  onAddToCart,
  onViewDetail,
}) {
  const [imgError, setImgError] = useState(false);
  const [added, setAdded]       = useState(false);

  const badge = badgeFor(product);
  const mrp   = product.signals.mrp;
  const isOutOfStock = product.stock !== undefined && product.stock <= 0;

  // Savings calculation — only show when live price is meaningfully below MRP
  const livePrice = priceData?.price;
  const showSaving = typeof livePrice === 'number' && livePrice < mrp * 0.99;
  const savingPct  = showSaving ? Math.round(((mrp - livePrice) / mrp) * 100) : 0;

  const handleAdd = (e) => {
    e.stopPropagation();
    if (!livePrice || priceLoading || isOutOfStock) return;
    onAddToCart(product, priceData);
    setAdded(true);
    setTimeout(() => setAdded(false), 1500);
  };

  const emoji = CAT_EMOJI[product.signals.category] ?? '📦';

  return (
    <article
      className="s-card"
      onClick={() => onViewDetail(product)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && onViewDetail(product)}
      aria-label={`View ${product.name}`}
      id={`product-card-${product.id}`}
    >
      {/* Image */}
      <div className="s-card-img-wrap">
        {!imgError ? (
          <img
            className="s-card-img"
            src={product.imageUrl}
            alt={product.name}
            onError={() => setImgError(true)}
            loading="lazy"
          />
        ) : (
          <div className="s-card-img-fallback" aria-hidden="true">{emoji}</div>
        )}

        {badge && (
          <span className={`s-card-badge ${badge.cls}`}>{badge.label}</span>
        )}
      </div>

      {/* Body */}
      <div className="s-card-body">
        <div className="s-card-cat">{product.category_label}</div>
        <div className="s-card-name">{product.name}</div>

        <div className="s-card-rating">
          <StarRating rating={product.rating} />
          <span>({product.reviewCount?.toLocaleString()})</span>
        </div>

        {/* Price row */}
        <div className="s-card-price-row">
          {priceLoading ? (
            <span className="s-price-loading" aria-label="Loading price" />
          ) : priceError ? (
            <span className="s-price-error" title={priceError}>Price unavailable</span>
          ) : livePrice !== undefined ? (
            <>
              <span className="s-price-live">
                ₹{livePrice.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
              </span>
              {showSaving && (
                <>
                  <span className="s-price-mrp">
                    ₹{mrp.toLocaleString('en-IN')}
                  </span>
                  <span className="s-price-saving">{savingPct}% off</span>
                </>
              )}
            </>
          ) : (
            <span className="s-price-error">–</span>
          )}
        </div>

        {/* Stock status indicator */}
        <div style={{ fontSize: '0.78rem', marginTop: '0.3rem', minHeight: '1.2rem' }}>
          {isOutOfStock ? (
            <span style={{ color: 'var(--s-danger)', fontWeight: 600 }}>❌ Out of Stock</span>
          ) : product.stock !== undefined && product.stock <= 5 ? (
            <span style={{ color: 'var(--s-warning)', fontWeight: 600 }}>⚡ Low Stock ({product.stock} left)</span>
          ) : product.stock !== undefined ? (
            <span style={{ color: 'var(--s-success)', fontWeight: 500 }}>✓ In Stock ({product.stock})</span>
          ) : null}
        </div>

        {/* Add to Cart */}
        <div className="s-card-add-btn">
          <button
            className={`s-add-btn ${added ? 'added' : ''}`}
            onClick={handleAdd}
            disabled={priceLoading || !!priceError || !livePrice || isOutOfStock}
            id={`add-btn-${product.id}`}
            aria-label={`Add ${product.name} to cart`}
            style={isOutOfStock ? { background: 'var(--s-border)', color: 'var(--s-text-dim)', cursor: 'not-allowed' } : {}}
          >
            {isOutOfStock ? 'Out of Stock' : added ? '✓ Added!' : '+ Add to Cart'}
          </button>
        </div>
      </div>
    </article>
  );
}
