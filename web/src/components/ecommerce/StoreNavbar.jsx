/**
 * StoreNavbar.jsx — Top navigation bar for the RateWeaver Store.
 *
 * Renders:
 *   - Brand logo and name
 *   - Search input (filters products via onSearchChange)
 *   - Tier selector (customer_tier signal: guest/regular/prime/elite)
 *   - Flash sale toggle (is_flash_sale signal)
 *   - Cart button with live item count badge
 */
import React from 'react';

const TIERS = [
  { value: 'guest',   label: '👤 Guest' },
  { value: 'regular', label: '🌟 Regular' },
  { value: 'prime',   label: '💎 Prime' },
  { value: 'elite',   label: '👑 Elite' },
];

export default function StoreNavbar({
  search,
  onSearchChange,
  cartCount,
  onCartOpen,
  customerTier,
  onTierChange,
  isFlashSale,
  onFlashToggle,
  onScrollToShop,
  onBackToDashboard,
}) {
  return (
    <nav className="s-navbar">
      <div className="s-navbar-inner">
        {/* Brand */}
        <a className="s-brand" onClick={onScrollToShop} style={{ cursor: 'pointer' }}>
          <div className="s-brand-icon">R</div>
          <span className="s-brand-name">
            Rate<span>Weaver</span> Store
          </span>
        </a>

        {/* Nav links */}
        <ul className="s-nav-links">
          <li><a className="active" onClick={onScrollToShop}>Shop</a></li>
          <li><a onClick={onScrollToShop}>Offers</a></li>
        </ul>

        {/* Search */}
        <div className="s-search-bar">
          <svg className="s-search-icon" width="15" height="15" viewBox="0 0 24 24"
            fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
            <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
          </svg>
          <input
            type="text"
            placeholder="Search products…"
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            aria-label="Search products"
            id="store-search-input"
          />
        </div>

        {/* Actions */}
        <div className="s-navbar-actions">
          {/* Customer tier */}
          <select
            className="s-tier-select"
            value={customerTier}
            onChange={(e) => onTierChange(e.target.value)}
            aria-label="Customer tier"
            title="Your membership tier affects your price"
            id="store-tier-select"
          >
            {TIERS.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>

          {/* Flash sale toggle */}
          <button
            className={`s-flash-toggle ${isFlashSale ? 'active' : ''}`}
            onClick={onFlashToggle}
            aria-pressed={isFlashSale}
            id="store-flash-toggle"
            title="Toggle flash sale (extra 15% off)"
          >
            ⚡ <span>Flash Sale</span>
          </button>

          {/* Cart */}
          <button
            className="s-cart-btn"
            onClick={onCartOpen}
            aria-label={`Open cart, ${cartCount} items`}
            id="store-cart-button"
          >
            🛒
            {cartCount > 0 && (
              <span className="s-cart-badge" aria-live="polite">{cartCount}</span>
            )}
          </button>

          {/* Back to Dashboard */}
          {onBackToDashboard && (
            <button
              className="s-flash-toggle"
              onClick={onBackToDashboard}
              title="Return to Sales & Telemetry Dashboard"
              id="store-back-to-admin"
              style={{ fontWeight: 600, color: 'var(--s-accent)' }}
            >
              📈 <span>Dashboard</span>
            </button>
          )}
        </div>
      </div>
    </nav>
  );
}
