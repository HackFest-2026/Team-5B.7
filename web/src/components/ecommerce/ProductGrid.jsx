/**
 * ProductGrid.jsx — Responsive product grid with toolbar (sort + results count).
 *
 * Renders the sorted/filtered product list, the sort selector, and empty states.
 */
import React from 'react';
import ProductCard from './ProductCard.jsx';

const SORT_OPTIONS = [
  { value: 'default',    label: 'Featured' },
  { value: 'price_asc',  label: 'Price: Low → High' },
  { value: 'price_desc', label: 'Price: High → Low' },
  { value: 'rating',     label: 'Top Rated' },
  { value: 'name',       label: 'Name A–Z' },
];

function sortProducts(products, prices, sortKey) {
  const arr = [...products];
  switch (sortKey) {
    case 'price_asc':
      return arr.sort((a, b) => {
        const pa = prices[a.id]?.price ?? Infinity;
        const pb = prices[b.id]?.price ?? Infinity;
        return pa - pb;
      });
    case 'price_desc':
      return arr.sort((a, b) => {
        const pa = prices[a.id]?.price ?? -Infinity;
        const pb = prices[b.id]?.price ?? -Infinity;
        return pb - pa;
      });
    case 'rating':
      return arr.sort((a, b) => b.rating - a.rating);
    case 'name':
      return arr.sort((a, b) => a.name.localeCompare(b.name));
    default:
      return arr; // preserve catalogue order
  }
}

export default function ProductGrid({
  products,
  prices,
  priceLoading,
  priceErrors,
  onAddToCart,
  onViewDetail,
  sortKey,
  onSortChange,
}) {
  const sorted = sortProducts(products, prices, sortKey);

  return (
    <div id="shop-section">
      {/* Toolbar */}
      <div className="s-toolbar">
        <span className="s-results-count">
          {sorted.length === 0
            ? 'No products found'
            : `${sorted.length} product${sorted.length !== 1 ? 's' : ''}`}
        </span>

        <select
          className="s-sort-select"
          value={sortKey}
          onChange={(e) => onSortChange(e.target.value)}
          aria-label="Sort products"
          id="store-sort-select"
        >
          {SORT_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </div>

      {/* Grid */}
      <div className="s-product-grid">
        {sorted.length === 0 ? (
          <div className="s-empty-state">
            <div className="s-empty-icon">🔍</div>
            <div className="s-empty-title">No products found</div>
            <div className="s-empty-sub">Try a different search term or category.</div>
          </div>
        ) : (
          sorted.map((product) => (
            <ProductCard
              key={product.id}
              product={product}
              priceData={prices[product.id] ?? null}
              priceLoading={priceLoading && !prices[product.id] && !priceErrors[product.id]}
              priceError={priceErrors[product.id] ?? null}
              onAddToCart={onAddToCart}
              onViewDetail={onViewDetail}
            />
          ))
        )}
      </div>
    </div>
  );
}
