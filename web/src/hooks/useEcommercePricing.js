/**
 * useEcommercePricing.js
 *
 * Custom hook for fetching RateWeaver-calculated prices for storefront products.
 *
 * Backend contract (POST /v1/price):
 *   Request:  { domain: "ecommerce", signals: { category, mrp, inventory_pct,
 *               demand_score, [customer_tier], [quantity], [is_flash_sale], [days_since_listed] } }
 *   Response: { price, base, pack_id, pack_version, fingerprint, trace[] }
 *
 * Design decisions:
 *   - Prices are keyed by product id + pricing context hash to avoid redundant fetches.
 *   - Store-level context (customer_tier, is_flash_sale) triggers a refresh for all products.
 *   - Per-product quantity is included only in detail/cart requests, not batch catalogue calls.
 *   - API errors surface as { error } entries — never as fabricated prices.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { fetchPrice, fetchBatchPrices, castSignalValue } from '../api.js';

const DOMAIN = 'ecommerce';

/**
 * Cast ecommerce signals to their backend-required types.
 * This mirrors castAllSignals() but with the pack structure inlined
 * since we know the ecommerce schema exactly.
 */
function castEcommerceSignals(rawSignals) {
  const schema = {
    category:          { type: 'enum' },
    mrp:               { type: 'number' },
    inventory_pct:     { type: 'number' },
    demand_score:      { type: 'number' },
    customer_tier:     { type: 'enum' },
    quantity:          { type: 'integer' },
    is_flash_sale:     { type: 'boolean' },
    days_since_listed: { type: 'integer' },
  };

  const result = {};
  for (const [key, val] of Object.entries(rawSignals)) {
    if (val === null || val === undefined) continue;
    const meta = schema[key];
    result[key] = meta ? castSignalValue(val, meta) : val;
  }
  return result;
}

/**
 * Build a stable cache key for a signal set.
 */
function signalKey(productId, contextSignals) {
  return `${productId}::${JSON.stringify(contextSignals, Object.keys(contextSignals).sort())}`;
}

/**
 * useCataloguePricing
 *
 * Fetches prices for an array of products in parallel, with the given store context.
 * Re-fetches when products array or storeContext changes.
 *
 * @param {Array}  products      - array of product objects from products.js
 * @param {object} storeContext  - { customer_tier, is_flash_sale } store-level signals
 * @returns {{ prices, loading, errors, refresh }}
 *   prices  — { [productId]: { price, base, fingerprint, trace } }
 *   loading — boolean
 *   errors  — { [productId]: string }
 */
export function useCataloguePricing(products, storeContext) {
  const [prices, setPrices]   = useState({});
  const [loading, setLoading] = useState(false);
  const [errors, setErrors]   = useState({});

  // Track in-flight abort to prevent stale updates
  const abortRef = useRef(null);
  const lastKeyRef = useRef('');

  const fetchAll = useCallback(async (overrideProducts = null) => {
    const prodsToPrice = overrideProducts || products;
    if (!prodsToPrice || prodsToPrice.length === 0) return;

    // Check if signals have actually changed unless explicitly overridden
    const currentKey = `${storeContext?.customer_tier}:${storeContext?.is_flash_sale}:${prodsToPrice.map((p) => `${p.id}:${p.stock}:${p.demand_score}`).join('|')}`;
    if (!overrideProducts && lastKeyRef.current === currentKey) {
      return;
    }

    // Cancel previous run
    if (abortRef.current) abortRef.current.cancelled = true;
    const abortFlag = { cancelled: false };
    abortRef.current = abortFlag;

    setLoading(true);

    const batchItems = prodsToPrice.map((product) => ({
      id: product.id,
      signals: castEcommerceSignals({
        ...product.signals,
        ...storeContext,
      }),
    }));

    // ── Instantaneous Batch Request (1 single HTTP round-trip) ─────────
    const batchRes = await fetchBatchPrices(DOMAIN, batchItems);

    if (abortFlag.cancelled) return;

    if (batchRes?.data?.items && Array.isArray(batchRes.data.items)) {
      const newPrices = {};
      const newErrors = batchRes.data.errors || {};

      for (const item of batchRes.data.items) {
        newPrices[item.id] = {
          price:       item.price,
          base:        item.base,
          fingerprint: item.fingerprint,
          trace:       item.trace ?? [],
        };
      }

      lastKeyRef.current = currentKey;
      setPrices(newPrices);
      setErrors(newErrors);
      setLoading(false);
      return;
    }

    // ── Fallback: Parallel single fetchPrice requests ───────────────────
    const settled = await Promise.allSettled(
      prodsToPrice.map(async (product) => {
        const signals = castEcommerceSignals({
          ...product.signals,
          ...storeContext,
        });

        const { data, error } = await fetchPrice(DOMAIN, signals);
        return { id: product.id, data, error, signals };
      })
    );

    if (abortFlag.cancelled) return;

    const newPrices = {};
    const newErrors = {};

    for (const result of settled) {
      if (result.status === 'fulfilled') {
        const { id, data, error } = result.value;
        if (error) {
          newErrors[id] = error;
        } else if (data && typeof data.price === 'number') {
          newPrices[id] = {
            price:       data.price,
            base:        data.base,
            fingerprint: data.fingerprint,
            trace:       data.trace ?? [],
          };
        } else {
          newErrors[id] = 'Unexpected response from pricing engine.';
        }
      }
    }

    if (!abortFlag.cancelled) {
      lastKeyRef.current = currentKey;
      setPrices(newPrices);
      setErrors(newErrors);
      setLoading(false);
    }
  }, [products, storeContext]);

  useEffect(() => {
    fetchAll();
    return () => {
      if (abortRef.current) abortRef.current.cancelled = true;
    };
  }, [fetchAll]);

  return { prices, loading, errors, refresh: fetchAll };
}


/**
 * useProductPricing
 *
 * Fetches a single product price with a specific quantity.
 * Used in the product detail modal and cart.
 *
 * @param {object|null} product      - product from products.js, or null
 * @param {object}      storeContext - { customer_tier, is_flash_sale }
 * @param {number}      quantity     - integer quantity
 * @returns {{ priceResult, loading, error, refetch }}
 */
export function useProductPricing(product, storeContext, quantity = 1) {
  const [priceResult, setPriceResult] = useState(null);
  const [loading, setLoading]         = useState(false);
  const [error, setError]             = useState(null);
  const inFlight = useRef(false);

  const refetch = useCallback(async () => {
    if (!product || inFlight.current) return;
    inFlight.current = true;
    setLoading(true);
    setError(null);

    const signals = castEcommerceSignals({
      ...product.signals,
      ...storeContext,
      quantity,
    });

    const { data, error: apiError } = await fetchPrice(DOMAIN, signals);

    inFlight.current = false;
    setLoading(false);

    if (apiError) {
      setError(apiError);
      setPriceResult(null);
    } else if (data && typeof data.price === 'number') {
      setPriceResult(data);
    } else {
      setError('Unexpected response from pricing engine.');
      setPriceResult(null);
    }
  }, [product, storeContext, quantity]);

  // Cache key tracks what we need to refetch for (includes dynamic demand and inventory signals)
  const cacheKey = product
    ? signalKey(product.id, {
        category: product.signals?.category || product.category,
        mrp: product.signals?.mrp || product.mrp,
        inventory_pct: product.signals?.inventory_pct,
        demand_score: product.signals?.demand_score,
        days_since_listed: product.signals?.days_since_listed,
        ...storeContext,
        quantity,
      })
    : null;

  const prevKeyRef = useRef(null);
  useEffect(() => {
    if (!product) return;
    if (cacheKey === prevKeyRef.current) return;
    prevKeyRef.current = cacheKey;
    refetch();
  }, [cacheKey, refetch, product]);

  return { priceResult, loading, error, refetch };
}
