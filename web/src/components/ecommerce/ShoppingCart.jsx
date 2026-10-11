/**
 * ShoppingCart.jsx — Right-side drawer for shopping cart & end-to-end checkout.
 *
 * Features:
 *   - Lists all cart items with image, name, unit price, subtotal
 *   - Live stock warnings when cart quantity exceeds available stock
 *   - Quantity controls (increment / decrement / remove)
 *   - Real backend quote revalidation via fetchStoreQuote
 *   - Price change detection & customer confirmation banner
 *   - Atomic transactional checkout with idempotency key
 *   - Order confirmation receipt with Order ID, itemized totals, and inventory feedback notice
 *   - Demo purchase notice (no real payment charged)
 */
import React, { useState } from 'react';
import { fetchStoreQuote, checkoutStoreOrder } from '../../api.js';

const CAT_EMOJI = {
  electronics: '📱',
  fashion: '👕',
  grocery: '🛒',
  home_appliances: '🏠',
  beauty: '✨',
};

function CartItemRow({ item, onUpdateQty, onRemove }) {
  const { product, priceData, qty } = item;
  const unitPrice = priceData?.price;
  const subtotal  = typeof unitPrice === 'number' ? unitPrice * qty : null;
  const emoji     = CAT_EMOJI[product.signals?.category || product.category] ?? '📦';
  const [imgErr, setImgErr] = useState(false);

  const availableStock = product.stock !== undefined ? product.stock : 99;
  const isOverStock = qty > availableStock;
  const isOutOfStock = availableStock <= 0;

  return (
    <div className="s-cart-item" id={`cart-item-${product.id}`}>
      {/* Image */}
      {!imgErr ? (
        <img
          className="s-cart-item-img"
          src={product.imageUrl || product.image_url}
          alt={product.name}
          onError={() => setImgErr(true)}
        />
      ) : (
        <div className="s-cart-item-img-fb">{emoji}</div>
      )}

      {/* Info */}
      <div className="s-cart-item-info">
        <div className="s-cart-item-name">{product.name}</div>
        <div className="s-cart-item-cat">{product.category_label || product.category}</div>

        <div className="s-cart-item-price-row">
          <span className="s-cart-item-unit-price">
            {typeof unitPrice === 'number'
              ? `₹${unitPrice.toLocaleString('en-IN', { maximumFractionDigits: 0 })} ea.`
              : 'Price unavailable'}
          </span>
          <span className="s-cart-item-sub">
            {subtotal !== null
              ? `₹${subtotal.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`
              : '—'}
          </span>
        </div>

        {/* Stock status indicator */}
        {isOutOfStock ? (
          <div style={{ fontSize: '0.75rem', color: 'var(--s-danger)', fontWeight: 600 }}>
            ❌ Item is out of stock
          </div>
        ) : isOverStock ? (
          <div style={{ fontSize: '0.75rem', color: 'var(--s-warning)', fontWeight: 600 }}>
            ⚠️ Only {availableStock} left in stock (exceeds quantity)
          </div>
        ) : availableStock <= 5 ? (
          <div style={{ fontSize: '0.72rem', color: 'var(--s-warning)' }}>
            ⚡ Low stock: {availableStock} available
          </div>
        ) : null}

        {/* Qty controls + remove */}
        <div className="s-cart-item-actions">
          <div className="s-cart-qty-control">
            <button
              className="s-cart-qty-btn"
              onClick={() => onUpdateQty(product.id, qty - 1)}
              disabled={qty <= 1}
              aria-label={`Decrease quantity of ${product.name}`}
              id={`cart-qty-dec-${product.id}`}
            >−</button>
            <span className="s-cart-qty-val" aria-live="polite">{qty}</span>
            <button
              className="s-cart-qty-btn"
              onClick={() => onUpdateQty(product.id, qty + 1)}
              disabled={qty >= availableStock || qty >= 99}
              aria-label={`Increase quantity of ${product.name}`}
              id={`cart-qty-inc-${product.id}`}
            >+</button>
          </div>
          <button
            className="s-cart-remove"
            onClick={() => onRemove(product.id)}
            aria-label={`Remove ${product.name} from cart`}
            id={`cart-remove-${product.id}`}
          >
            🗑 Remove
          </button>
        </div>
      </div>
    </div>
  );
}

export default function ShoppingCart({
  items,          // Array<{ product, priceData, qty }>
  onClose,
  onUpdateQty,    // (productId, newQty) → void
  onRemove,       // (productId) → void
  onClearAll,
  customerTier = 'guest',
  isFlashSale = false,
  onOrderCompleted, // callback to refresh catalogue
}) {
  const [step, setStep] = useState('cart'); // 'cart' | 'review' | 'confirmed'
  const [loading, setLoading] = useState(false);
  const [checkoutError, setCheckoutError] = useState(null);
  const [confirmedOrder, setConfirmedOrder] = useState(null);
  const [priceChanges, setPriceChanges] = useState([]);
  const [quoteData, setQuoteData] = useState(null);

  // Cart total — derived from current items
  const validItems = items.filter((it) => typeof it.priceData?.price === 'number');
  const total = validItems.reduce((sum, it) => sum + it.priceData.price * it.qty, 0);
  const totalItems = items.reduce((s, it) => s + it.qty, 0);

  // Any items over stock
  const hasOverStock = items.some((it) => {
    const stock = it.product.stock !== undefined ? it.product.stock : 99;
    return it.qty > stock || stock <= 0;
  });

  // Start checkout flow: fetch live quote to detect price adjustments
  const handleProceedToReview = async () => {
    setLoading(true);
    setCheckoutError(null);
    setPriceChanges([]);

    const { data, error } = await fetchStoreQuote(items, customerTier, isFlashSale);
    setLoading(false);

    if (error) {
      setCheckoutError(error);
      return;
    }

    setQuoteData(data);

    // Detect if any unit price changed from cart display
    const changes = [];
    if (data?.items) {
      for (const quoted of data.items) {
        const cartItem = items.find((it) => it.product.id === quoted.product_id);
        const cartUnitPrice = cartItem?.priceData?.price;
        if (typeof cartUnitPrice === 'number' && Math.abs(cartUnitPrice - quoted.unit_price) > 0.01) {
          changes.push({
            name: quoted.name,
            oldPrice: cartUnitPrice,
            newPrice: quoted.unit_price,
            delta: Math.round(quoted.unit_price - cartUnitPrice),
          });
        }
      }
    }

    setPriceChanges(changes);
    setStep('review');
  };

  // Execute atomic purchase
  const handleConfirmPurchase = async () => {
    setLoading(true);
    setCheckoutError(null);

    const idempotencyKey = `ord_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;

    const { data, error } = await checkoutStoreOrder({
      idempotencyKey,
      items,
      customerTier,
      isFlashSale,
      confirmPriceChange: true,
    });

    setLoading(false);

    if (error) {
      setCheckoutError(typeof error === 'object' ? error.message || JSON.stringify(error) : error);
      return;
    }

    setConfirmedOrder(data);
    setStep('confirmed');

    if (onOrderCompleted) {
      onOrderCompleted(data);
    }
  };

  const handleFinish = () => {
    onClearAll();
    setStep('cart');
    setConfirmedOrder(null);
    onClose();
  };

  return (
    <>
      {/* Backdrop */}
      <div
        className="s-cart-overlay"
        onClick={step === 'confirmed' ? handleFinish : onClose}
        aria-hidden="true"
      />

      {/* Drawer */}
      <aside
        className="s-cart-drawer"
        aria-label="Shopping cart"
        role="complementary"
        id="shopping-cart-drawer"
      >
        {/* Header */}
        <div className="s-cart-header">
          <div className="s-cart-title">
            {step === 'confirmed' ? '🎉 Order Confirmed!' : step === 'review' ? '📋 Checkout Review' : '🛒 Shopping Cart'}
            {step === 'cart' && totalItems > 0 && <span> ({totalItems} items)</span>}
          </div>
          <button
            className="s-cart-close"
            onClick={step === 'confirmed' ? handleFinish : onClose}
            aria-label="Close cart"
            id="cart-close-btn"
          >✕</button>
        </div>

        {/* Body */}
        <div className="s-cart-body">
          {/* STEP 1: CART LIST */}
          {step === 'cart' && (
            items.length === 0 ? (
              <div className="s-cart-empty">
                <div className="s-cart-empty-icon">🛒</div>
                <div style={{ fontWeight: 600, marginBottom: '0.4rem' }}>Your cart is empty</div>
                <div style={{ fontSize: '0.875rem' }}>Add products from the store to get started.</div>
              </div>
            ) : (
              items.map((item) => (
                <CartItemRow
                  key={item.product.id}
                  item={item}
                  onUpdateQty={onUpdateQty}
                  onRemove={onRemove}
                />
              ))
            )
          )}

          {/* STEP 2: CHECKOUT REVIEW */}
          {step === 'review' && quoteData && (
            <div style={{ padding: '0.5rem 0' }}>
              {priceChanges.length > 0 && (
                <div style={{
                  background: '#fffbeb',
                  border: '1px solid #fde68a',
                  borderRadius: 8,
                  padding: '0.85rem',
                  marginBottom: '1rem',
                  fontSize: '0.82rem',
                  color: '#92400e',
                }}>
                  <div style={{ fontWeight: 700, marginBottom: '0.3rem' }}>
                    ⚡ Live Demand Price Update
                  </div>
                  <div>Prices updated based on real-time engine evaluation:</div>
                  <ul style={{ margin: '0.4rem 0 0 1.2rem', padding: 0 }}>
                    {priceChanges.map((ch, idx) => (
                      <li key={idx}>
                        <strong>{ch.name}</strong>: ₹{ch.oldPrice} → ₹{ch.newPrice} ({ch.delta > 0 ? `+₹${ch.delta}` : `-₹${Math.abs(ch.delta)}`})
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <div style={{ fontSize: '0.88rem', fontWeight: 600, marginBottom: '0.6rem', color: 'var(--s-text)' }}>
                Order Summary ({quoteData.total_items} items)
              </div>

              {quoteData.items.map((it) => (
                <div key={it.product_id} style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '0.5rem 0',
                  borderBottom: '1px solid var(--s-border)',
                  fontSize: '0.85rem',
                }}>
                  <div>
                    <div style={{ fontWeight: 600 }}>{it.name}</div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--s-text-muted)' }}>
                      Qty: {it.quantity} × ₹{it.unit_price}
                    </div>
                  </div>
                  <div style={{ fontWeight: 700 }}>₹{it.subtotal}</div>
                </div>
              ))}

              <div style={{
                background: 'var(--s-surface-2)',
                borderRadius: 8,
                padding: '0.85rem',
                marginTop: '1rem',
                fontSize: '0.82rem',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.3rem' }}>
                  <span>Customer Loyalty Tier:</span>
                  <span style={{ fontWeight: 600, textTransform: 'capitalize' }}>{customerTier}</span>
                </div>
                {isFlashSale && (
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.3rem', color: '#b45309' }}>
                    <span>Flash Sale Discount:</span>
                    <span style={{ fontWeight: 600 }}>Active (15% off)</span>
                  </div>
                )}
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.3rem' }}>
                  <span>Subtotal MRP:</span>
                  <span style={{ textDecoration: 'line-through', color: 'var(--s-text-dim)' }}>
                    ₹{quoteData.subtotal_mrp.toLocaleString('en-IN')}
                  </span>
                </div>
                {quoteData.savings > 0 && (
                  <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--s-success)', fontWeight: 600 }}>
                    <span>Total Savings:</span>
                    <span>-₹{quoteData.savings.toLocaleString('en-IN')}</span>
                  </div>
                )}
              </div>

              {checkoutError && (
                <div style={{
                  background: '#fef2f2',
                  border: '1px solid #fecaca',
                  borderRadius: 8,
                  padding: '0.8rem',
                  marginTop: '1rem',
                  color: 'var(--s-danger)',
                  fontSize: '0.85rem',
                }}>
                  ⚠️ {checkoutError}
                </div>
              )}

              <div style={{
                fontSize: '0.75rem',
                color: 'var(--s-text-dim)',
                marginTop: '1rem',
                textAlign: 'center',
              }}>
                ℹ️ Demo purchase — Real inventory decrement will occur in SQLite backend.
              </div>
            </div>
          )}

          {/* STEP 3: ORDER CONFIRMED */}
          {step === 'confirmed' && confirmedOrder && (
            <div style={{ textAlign: 'center', padding: '1rem 0' }}>
              <div style={{ fontSize: '3.5rem', marginBottom: '0.5rem' }}>✅</div>
              <h3 style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--s-text)', marginBottom: '0.3rem' }}>
                Purchase Successful!
              </h3>
              <div style={{
                fontSize: '0.82rem',
                fontFamily: 'monospace',
                background: 'var(--s-surface-2)',
                padding: '0.4rem 0.8rem',
                borderRadius: 6,
                display: 'inline-block',
                marginBottom: '1.25rem',
                color: 'var(--s-accent)',
                fontWeight: 700,
              }}>
                Order ID: {confirmedOrder.order_id}
              </div>

              <div style={{
                background: '#f0fdf4',
                border: '1px solid #86efac',
                borderRadius: 8,
                padding: '0.85rem',
                fontSize: '0.85rem',
                color: '#15803d',
                textAlign: 'left',
                marginBottom: '1rem',
              }}>
                <div style={{ fontWeight: 700, marginBottom: '0.4rem' }}>
                  ✓ Inventory & Demand Updated Live:
                </div>
                <div style={{ fontSize: '0.8rem', lineHeight: 1.5 }}>
                  Purchased units have been authoritatively deducted from database stock. Subsequent customers will see updated inventory levels and demand-adjusted pricing!
                </div>
              </div>

              {/* Order breakdown */}
              <div style={{ textAlign: 'left', border: '1px solid var(--s-border)', borderRadius: 8, padding: '0.85rem', marginBottom: '1.25rem' }}>
                <div style={{ fontSize: '0.82rem', fontWeight: 700, marginBottom: '0.6rem', color: 'var(--s-text-muted)' }}>
                  ITEMS PURCHASED
                </div>
                {confirmedOrder.items?.map((it) => (
                  <div key={it.product_id} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', marginBottom: '0.3rem' }}>
                    <span>{it.quantity}× {it.name}</span>
                    <span style={{ fontWeight: 600 }}>₹{it.subtotal}</span>
                  </div>
                ))}
                <div style={{ borderTop: '1px solid var(--s-border)', paddingTop: '0.5rem', marginTop: '0.5rem', display: 'flex', justifyContent: 'space-between', fontWeight: 700, fontSize: '0.95rem' }}>
                  <span>Total Amount Paid</span>
                  <span style={{ color: 'var(--s-accent)' }}>₹{confirmedOrder.total_price}</span>
                </div>
              </div>

              <button
                className="s-checkout-btn"
                onClick={handleFinish}
                id="order-continue-shopping-btn"
              >
                🛍️ Continue Shopping
              </button>
            </div>
          )}
        </div>

        {/* Footer */}
        {items.length > 0 && step !== 'confirmed' && (
          <div className="s-cart-footer">
            <div className="s-cart-subtotal-row">
              <span>{totalItems} item{totalItems !== 1 ? 's' : ''}</span>
              <span>₹{(quoteData ? quoteData.total_price : total).toLocaleString('en-IN', { maximumFractionDigits: 0 })}</span>
            </div>
            <div className="s-cart-total-row">
              <span>Total Payable</span>
              <span>₹{(quoteData ? quoteData.total_price : total).toLocaleString('en-IN', { maximumFractionDigits: 0 })}</span>
            </div>

            {hasOverStock && (
              <div style={{ color: 'var(--s-danger)', fontSize: '0.8rem', marginBottom: '0.5rem', fontWeight: 600 }}>
                ⚠️ Please adjust item quantities to available stock before checkout.
              </div>
            )}

            {step === 'cart' ? (
              <button
                className="s-checkout-btn"
                onClick={handleProceedToReview}
                disabled={validItems.length === 0 || hasOverStock || loading}
                id="cart-proceed-checkout-btn"
              >
                {loading ? '🔄 Validating Prices & Stock…' : `Review & Checkout — ₹${total.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`}
              </button>
            ) : (
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <button
                  className="s-btn s-btn-outline"
                  onClick={() => setStep('cart')}
                  disabled={loading}
                  style={{ flex: 1, padding: '0.75rem' }}
                >
                  ← Back to Cart
                </button>
                <button
                  className="s-checkout-btn"
                  onClick={handleConfirmPurchase}
                  disabled={loading}
                  id="confirm-purchase-btn"
                  style={{ flex: 2 }}
                >
                  {loading ? '⏳ Placing Order…' : 'Confirm Purchase →'}
                </button>
              </div>
            )}

            {step === 'cart' && (
              <button
                className="s-clear-cart"
                onClick={onClearAll}
                id="clear-cart-btn"
              >
                Clear cart
              </button>
            )}
          </div>
        )}
      </aside>
    </>
  );
}
