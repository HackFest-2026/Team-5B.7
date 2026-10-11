/**
 * EcommerceStore.jsx — Main storefront page for RateWeaver.
 *
 * Architecture:
 *   - Fetches live catalogue with authoritative inventory & dynamic demand signals.
 *   - Store-level context (customerTier, isFlashSale) dynamically drives the pricing engine.
 *   - useCataloguePricing fetches prices for all products in parallel using POST /v1/price.
 *   - Product cards display real-time stock levels and live engine-computed prices.
 *   - Detail modal features collapsible rule trace explanation ("Why this price?") and recommendations.
 *   - ShoppingCart drawer handles live quote revalidation, price-change confirmation, and atomic checkout.
 *   - A successful purchase atomically decrements backend stock and refreshes catalogue pricing.
 */
import React, { useState, useEffect, useReducer, useCallback, useMemo, useRef } from 'react';
import '../store.css';

import { PRODUCTS, CATEGORY_LABELS } from '../data/products.js';
import { useCataloguePricing } from '../hooks/useEcommercePricing.js';
import { fetchStoreProducts, fetchStoreRecommendations } from '../api.js';

import StoreNavbar    from '../components/ecommerce/StoreNavbar.jsx';
import HeroSection    from '../components/ecommerce/HeroSection.jsx';
import CategoryFilters from '../components/ecommerce/CategoryFilters.jsx';
import ProductGrid    from '../components/ecommerce/ProductGrid.jsx';
import ProductDetail  from '../components/ecommerce/ProductDetail.jsx';
import ShoppingCart   from '../components/ecommerce/ShoppingCart.jsx';

// ── Cart reducer ─────────────────────────────────────────────────────────────
function cartReducer(state, action) {
  switch (action.type) {
    case 'ADD': {
      const { product, priceData, qty = 1 } = action;
      const existing = state.find((it) => it.product.id === product.id);
      if (existing) {
        return state.map((it) =>
          it.product.id === product.id
            ? { ...it, qty: Math.min(product.stock !== undefined ? product.stock : 99, it.qty + qty), priceData }
            : it
        );
      }
      return [...state, { product, priceData, qty }];
    }
    case 'UPDATE_QTY': {
      const { productId, qty } = action;
      if (qty <= 0) return state.filter((it) => it.product.id !== productId);
      return state.map((it) =>
        it.product.id === productId ? { ...it, qty } : it
      );
    }
    case 'REMOVE':
      return state.filter((it) => it.product.id !== action.productId);
    case 'CLEAR':
      return [];
    default:
      return state;
  }
}

// ── Toast hook ────────────────────────────────────────────────────────────────
function useToast() {
  const [toast, setToast] = useState(null);
  const timerRef = useRef(null);

  const show = useCallback((msg) => {
    setToast(msg);
    clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => setToast(null), 3000);
  }, []);

  return { toast, show };
}

// ── Main component ────────────────────────────────────────────────────────────
export default function EcommerceStore({ onBackToDashboard }) {
  // ── Authoritative product catalogue ──────────────────────────────────────────
  const [productList, setProductList] = useState(PRODUCTS);
  const [recommendations, setRecommendations] = useState([]);

  const loadProducts = useCallback(async () => {
    const { data } = await fetchStoreProducts();
    if (data && Array.isArray(data) && data.length > 0) {
      // Map API fields ensuring compatibility with frontend display
      const normalized = data.map((p) => ({
        ...p,
        imageUrl: p.image_url || p.imageUrl,
        shortDesc: p.short_desc || p.shortDesc,
        category_label: CATEGORY_LABELS[p.category] || p.category,
        reviewCount: p.review_count || p.reviewCount || 0,
      }));
      setProductList((prev) => {
        const prevKey = prev.map((p) => `${p.id}:${p.stock}:${p.demand_score}`).join(',');
        const nextKey = normalized.map((p) => `${p.id}:${p.stock}:${p.demand_score}`).join(',');
        return prevKey === nextKey ? prev : normalized;
      });
      return normalized;
    }
    return null;
  }, []);

  const loadRecommendations = useCallback(async () => {
    const { data } = await fetchStoreRecommendations(null, 4);
    if (data && Array.isArray(data)) {
      setRecommendations(data);
    }
  }, []);

  // ── Store context (used as pricing signals) ──────────────────────────────
  const [customerTier, setCustomerTier] = useState('guest');
  const [isFlashSale, setIsFlashSale]   = useState(false);

  const storeContext = useMemo(() => ({
    customer_tier:  customerTier,
    is_flash_sale:  isFlashSale,
  }), [customerTier, isFlashSale]);

  // ── Pricing ──────────────────────────────────────────────────────────────
  const { prices, loading: priceLoading, errors: priceErrors, refresh: refreshPrices } =
    useCataloguePricing(productList, storeContext);

  const refreshPricesRef = useRef(refreshPrices);
  refreshPricesRef.current = refreshPrices;

  // ── Auto-sync catalogue & prices for cross-customer consistency ──────────
  useEffect(() => {
    loadProducts();
    loadRecommendations();

    const handleFocus = async () => {
      const fresh = await loadProducts();
      if (fresh) refreshPricesRef.current(fresh);
      loadRecommendations();
    };

    window.addEventListener('focus', handleFocus);
    // Calm periodic background polling every 20s
    const intervalId = setInterval(async () => {
      const fresh = await loadProducts();
      if (fresh) refreshPricesRef.current(fresh);
    }, 20000);

    return () => {
      window.removeEventListener('focus', handleFocus);
      clearInterval(intervalId);
    };
  }, [loadProducts, loadRecommendations]);

  // ── Filters ──────────────────────────────────────────────────────────────
  const [search,   setSearch]   = useState('');
  const [category, setCategory] = useState(null);   // null = All
  const [sortKey,  setSortKey]  = useState('default');

  const filteredProducts = productList.filter((p) => {
    const matchesCat    = !category || (p.signals?.category || p.category) === category;
    const matchesSearch = !search   || p.name.toLowerCase().includes(search.toLowerCase());
    return matchesCat && matchesSearch;
  });

  // ── Cart ─────────────────────────────────────────────────────────────────
  const [cartItems, dispatchCart] = useReducer(cartReducer, []);
  const [cartOpen, setCartOpen]   = useState(false);

  const cartCount = cartItems.reduce((s, it) => s + it.qty, 0);

  const handleAddToCart = useCallback((product, priceData, qty = 1) => {
    dispatchCart({ type: 'ADD', product, priceData, qty });
    showToast(`✓ "${product.name}" added to cart`);
  }, []);

  // ── Detail modal ─────────────────────────────────────────────────────────
  const [detailProduct, setDetailProduct] = useState(null);

  // ── Toast ─────────────────────────────────────────────────────────────────
  const { toast, show: showToast } = useToast();

  // ── Scroll to shop ────────────────────────────────────────────────────────
  const shopRef = useRef(null);
  const scrollToShop = () =>
    shopRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });

  // Handle order completion: refresh live catalogue stock & demand
  const handleOrderCompleted = useCallback(async (order) => {
    console.log('[StoreRefresh] Post-purchase refresh triggered for order:', order.order_id);
    const updatedProducts = await loadProducts();
    loadRecommendations();
    if (updatedProducts) {
      await refreshPrices(updatedProducts);
    } else {
      await refreshPrices();
    }
    showToast(`🎉 Order #${order.order_id} confirmed! Live stock & demand recalculated.`);
  }, [loadProducts, loadRecommendations, refreshPrices, showToast]);

  return (
    <div className="store-root">
      {/* ── Navbar ──────────────────────────────────────────────────── */}
      <StoreNavbar
        search={search}
        onSearchChange={setSearch}
        cartCount={cartCount}
        onCartOpen={() => setCartOpen(true)}
        customerTier={customerTier}
        onTierChange={(tier) => setCustomerTier(tier)}
        isFlashSale={isFlashSale}
        onFlashToggle={() => setIsFlashSale((f) => !f)}
        onScrollToShop={scrollToShop}
        onBackToDashboard={onBackToDashboard}
      />

      {/* ── Pricing context info bar ─────────────────────────────────── */}
      <div className="s-context-bar">
        <div className="s-context-bar-inner">
          <span>⚡ Live pricing context:</span>
          <span className="s-context-pill">
            👤 {TIERS_MAP[customerTier] ?? customerTier}
          </span>
          {isFlashSale && (
            <span className="s-context-pill">🔥 Flash Sale Active (15% off)</span>
          )}
          <span style={{ marginLeft: 'auto', color: 'var(--s-accent)', opacity: 0.8, fontSize: '0.82rem' }}>
            {priceLoading
              ? '🔄 Recalculating prices…'
              : `✅ Live Engine: POST /v1/price (ecommerce pack)`}
          </span>
        </div>
      </div>

      {/* ── Hero ─────────────────────────────────────────────────────── */}
      <HeroSection onShopNow={scrollToShop} productCount={productList.length} />

      {/* ── Trending & Recommended Section ───────────────────────────── */}
      {recommendations.length > 0 && (
        <section style={{ maxWidth: 1280, margin: '2rem auto 0', padding: '0 1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
            <div>
              <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--s-text)', margin: 0 }}>
                🔥 Popular & Trending Now
              </h2>
              <p style={{ fontSize: '0.82rem', color: 'var(--s-text-muted)', margin: '0.2rem 0 0' }}>
                Dynamically recommended based on recent purchase volume and demand
              </p>
            </div>
            <span style={{ fontSize: '0.8rem', color: 'var(--s-accent)', fontWeight: 600 }}>
              Live Recommendations
            </span>
          </div>

          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))',
            gap: '1rem',
          }}>
            {recommendations.map((rec) => {
              const liveP = prices[rec.id]?.price ?? rec.mrp;
              return (
                <div
                  key={rec.id}
                  onClick={() => {
                    const fullProd = productList.find((p) => p.id === rec.id) || rec;
                    setDetailProduct(fullProd);
                  }}
                  style={{
                    background: 'var(--s-surface)',
                    border: '1px solid var(--s-border)',
                    borderRadius: 10,
                    padding: '0.85rem',
                    cursor: 'pointer',
                    display: 'flex',
                    gap: '0.75rem',
                    alignItems: 'center',
                    boxShadow: 'var(--s-shadow-sm)',
                    transition: 'transform 0.15s ease',
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.transform = 'translateY(-2px)'; }}
                  onMouseLeave={(e) => { e.currentTarget.style.transform = 'translateY(0)'; }}
                >
                  <img
                    src={rec.image_url}
                    alt={rec.name}
                    style={{ width: 64, height: 64, objectFit: 'cover', borderRadius: 8, background: 'var(--s-surface-2)' }}
                    onError={(e) => { e.currentTarget.style.display = 'none'; }}
                  />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: '0.72rem', textTransform: 'uppercase', color: 'var(--s-accent)', fontWeight: 700 }}>
                      {CATEGORY_LABELS[rec.category] || rec.category}
                    </div>
                    <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--s-text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {rec.name}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.4rem', marginTop: '0.2rem' }}>
                      <span style={{ fontWeight: 700, fontSize: '0.95rem' }}>₹{liveP}</span>
                      <span style={{ fontSize: '0.75rem', color: 'var(--s-text-dim)', textDecoration: 'line-through' }}>₹{rec.mrp}</span>
                    </div>
                    <div style={{ fontSize: '0.72rem', color: rec.stock <= 5 ? 'var(--s-warning)' : 'var(--s-success)', fontWeight: 500 }}>
                      {rec.stock <= 5 ? `⚡ Only ${rec.stock} left` : `In Stock (${rec.stock})`}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* ── Catalogue ────────────────────────────────────────────────── */}
      <section className="s-catalogue" ref={shopRef} id="catalogue-section">
        <CategoryFilters selected={category} onSelect={setCategory} />

        <ProductGrid
          products={filteredProducts}
          prices={prices}
          priceLoading={priceLoading}
          priceErrors={priceErrors}
          onAddToCart={handleAddToCart}
          onViewDetail={setDetailProduct}
          sortKey={sortKey}
          onSortChange={setSortKey}
        />
      </section>

      {/* ── Product Detail Modal ──────────────────────────────────────── */}
      {detailProduct && (
        <ProductDetail
          product={detailProduct}
          storeContext={storeContext}
          onAddToCart={(product, priceData, qty) => {
            handleAddToCart(product, priceData, qty);
            setDetailProduct(null);
          }}
          onClose={() => setDetailProduct(null)}
          onSelectProduct={(rec) => {
            const found = productList.find((p) => p.id === rec.id) || rec;
            setDetailProduct(found);
          }}
        />
      )}

      {/* ── Shopping Cart Drawer & Checkout ───────────────────────────── */}
      {cartOpen && (
        <ShoppingCart
          items={cartItems}
          onClose={() => setCartOpen(false)}
          onUpdateQty={(id, qty) => dispatchCart({ type: 'UPDATE_QTY', productId: id, qty })}
          onRemove={(id) => dispatchCart({ type: 'REMOVE', productId: id })}
          onClearAll={() => dispatchCart({ type: 'CLEAR' })}
          customerTier={customerTier}
          isFlashSale={isFlashSale}
          onOrderCompleted={handleOrderCompleted}
        />
      )}

      {/* ── Toast ────────────────────────────────────────────────────── */}
      {toast && (
        <div className="s-toast" role="status" aria-live="polite">
          {toast}
        </div>
      )}

      {/* ── Footer ───────────────────────────────────────────────────── */}
      <footer style={{
        borderTop: '1px solid var(--s-border)',
        padding: '1.5rem 1.25rem',
        textAlign: 'center',
        color: 'var(--s-text-dim)',
        fontSize: '0.8rem',
        background: 'var(--s-surface)',
      }}>
        RateWeaver Store — Prices dynamically computed by the Monetize360 engine ·&nbsp;
        <span style={{ color: 'var(--s-accent)' }}>ecommerce</span> domain pack v1.0.0
      </footer>
    </div>
  );
}

// Tier display map (mirrors TIERS in StoreNavbar)
const TIERS_MAP = {
  guest:   'Guest',
  regular: 'Regular',
  prime:   'Prime',
  elite:   'Elite',
};
