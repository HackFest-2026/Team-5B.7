/**
 * CategoryFilters.jsx — Horizontal scrollable category chip filters.
 *
 * Renders an "All" chip plus one chip per ecommerce category.
 * Selecting a chip calls onSelect(categoryKey | null).
 */
import React from 'react';
import { CATEGORY_LABELS } from '../../data/products.js';

const CATEGORY_ICONS = {
  electronics:     '📱',
  fashion:         '👕',
  grocery:         '🛒',
  home_appliances: '🏠',
  beauty:          '✨',
};

export default function CategoryFilters({ selected, onSelect }) {
  return (
    <div className="s-category-bar" role="group" aria-label="Filter by category">
      <button
        className={`s-cat-chip ${selected === null ? 'active' : ''}`}
        onClick={() => onSelect(null)}
        id="cat-chip-all"
      >
        🛍️ All
      </button>

      {Object.entries(CATEGORY_LABELS).map(([key, label]) => (
        <button
          key={key}
          className={`s-cat-chip ${selected === key ? 'active' : ''}`}
          onClick={() => onSelect(key)}
          id={`cat-chip-${key}`}
          aria-pressed={selected === key}
        >
          {CATEGORY_ICONS[key]} {label}
        </button>
      ))}
    </div>
  );
}
