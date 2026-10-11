/**
 * api.js — Centralized API client for Monetize360.
 *
 * Contract source of truth:
 *   Request:  api/models.py  PriceRequest { domain: str, signals: dict }
 *   Response: engine/runtime.py  PriceResult.to_dict()
 *             { price, base, pack_id, pack_version, fingerprint, trace[] }
 *   Trace step: engine/trace/models.py  TraceStep.to_dict()
 *             { step, rule_id, stage, before, after, action, description, fired }
 *
 * All requests go through /v1/* which is proxied to http://localhost:8000
 * in development (see vite.config.js).
 */

/** Base path — Vite proxy handles /v1 → http://localhost:8000 */
const BASE = '';

/**
 * Parse an API response body safely.
 * Returns { data, error } where error is a human-readable string on failure.
 */
async function parseResponse(res) {
  let body;
  try {
    body = await res.json();
  } catch {
    return { data: null, error: `Server returned non-JSON response (HTTP ${res.status})` };
  }

  if (!res.ok) {
    // FastAPI validation errors are a list: { detail: [{loc, msg, type}, ...] }
    // Engine PricingError is a string: { detail: "..." }
    const detail = body?.detail;
    if (Array.isArray(detail)) {
      const msgs = detail.map((e) => e.msg || JSON.stringify(e)).join('; ');
      return { data: null, error: `Validation error: ${msgs}` };
    }
    if (typeof detail === 'string') {
      return { data: null, error: detail };
    }
    if (detail && typeof detail === 'object') {
      return { data: null, error: detail.message || JSON.stringify(detail) };
    }
    return { data: null, error: `HTTP ${res.status}` };
  }

  return { data: body, error: null };
}

/**
 * POST /v1/price
 *
 * @param {string} domain   - pack_id of the domain (e.g. "ecommerce")
 * @param {object} signals  - flat key→value signal dict
 * @returns {{ data: PriceResult|null, error: string|null }}
 */
export async function fetchPrice(domain, signals) {
  try {
    const res = await fetch(`${BASE}/v1/price`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ domain, signals }),
    });
    return parseResponse(res);
  } catch (err) {
    return { data: null, error: `Network error: ${err.message}` };
  }
}

/**
 * POST /v1/price/batch
 *
 * Compute prices for multiple products in a single round-trip.
 *
 * @param {string} domain
 * @param {Array<{ id: string, signals: object }>} items
 * @returns {{ data: { items: Array, errors: object }|null, error: string|null }}
 */
export async function fetchBatchPrices(domain, items) {
  try {
    const res = await fetch(`${BASE}/v1/price/batch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ domain, items }),
    });
    return parseResponse(res);
  } catch (err) {
    return { data: null, error: `Network error: ${err.message}` };
  }
}


/**
 * POST /v1/simulate/sweep
 *
 * @param {string}   domain       - pack_id
 * @param {object}   baseSignals  - base signal dict
 * @param {string}   sweepSignal  - signal key to sweep
 * @param {Array}    sweepValues  - list of values for the sweep signal
 * @returns {{ data: Array|null, error: string|null }}
 */
export async function fetchSweep(domain, baseSignals, sweepSignal, sweepValues) {
  try {
    const res = await fetch(`${BASE}/v1/simulate/sweep`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        domain,
        base_signals: baseSignals,
        sweep_signal: sweepSignal,
        sweep_values: sweepValues,
      }),
    });
    return parseResponse(res);
  } catch (err) {
    return { data: null, error: `Network error: ${err.message}` };
  }
}

/**
 * GET /v1/domains
 * @returns {{ data: Array|null, error: string|null }}
 */
export async function fetchDomains() {
  try {
    const res = await fetch(`${BASE}/v1/domains`);
    return parseResponse(res);
  } catch (err) {
    return { data: null, error: `Network error: ${err.message}` };
  }
}

/**
 * GET /v1/domains/:domainId
 * @returns {{ data: object|null, error: string|null }}
 */
export async function fetchDomainPack(domainId) {
  try {
    const res = await fetch(`${BASE}/v1/domains/${encodeURIComponent(domainId)}`);
    return parseResponse(res);
  } catch (err) {
    return { data: null, error: `Network error: ${err.message}` };
  }
}

/**
 * Convert a raw form value to the type the backend expects for a given signal.
 *
 * Backend strict rules (engine/runtime.py _validate_signals):
 *   number  → float  (bool excluded)
 *   integer → Python int (type(v) is int); parseFloat would fail
 *   boolean → bool   (type(v) is bool)
 *   enum    → string matching signal.values
 *   string  → str
 *
 * @param {*}      rawValue  - value from form state
 * @param {object} signal    - Signal metadata { type, values, min, max, ... }
 * @returns {*} converted value
 */
export function castSignalValue(rawValue, signal) {
  if (rawValue === null || rawValue === undefined) return rawValue;
  switch (signal.type) {
    case 'integer':
      return parseInt(rawValue, 10);
    case 'number':
      return parseFloat(rawValue);
    case 'boolean':
      return Boolean(rawValue);
    default:
      // enum, string — pass through as-is
      return rawValue;
  }
}

/**
 * Build the default initial value for a signal.
 * @param {object} signal  - Signal metadata
 * @returns {*} default value
 */
export function defaultSignalValue(signal) {
  switch (signal.type) {
    case 'enum':
      return signal.values?.[0] ?? '';
    case 'number':
      return signal.min !== undefined ? signal.min : 0;
    case 'integer':
      return signal.min !== undefined ? Math.ceil(signal.min) : 0;
    case 'boolean':
      return false;
    case 'string':
      return '';
    default:
      return '';
  }
}

/**
 * Build initial signal state from a domain pack's signals array.
 * signals is List[Signal] — array of { key, type, values, min, max, required }
 *
 * @param {Array} signals  - pack.signals array
 * @returns {object}       - { [key]: defaultValue }
 */
export function buildInitialSignals(signals) {
  if (!Array.isArray(signals)) return {};
  const initial = {};
  for (const sig of signals) {
    initial[sig.key] = defaultSignalValue(sig);
  }
  return initial;
}

/**
 * Cast all signal values in a signals dict using the pack's signal metadata.
 *
 * @param {object} signalValues - { [key]: rawValue }
 * @param {Array}  signalsMeta  - pack.signals array
 * @returns {object}            - { [key]: castValue }
 */
export function castAllSignals(signalValues, signalsMeta) {
  if (!Array.isArray(signalsMeta)) return signalValues;
  const metaByKey = Object.fromEntries(signalsMeta.map((s) => [s.key, s]));
  const result = {};
  for (const [key, val] of Object.entries(signalValues)) {
    const meta = metaByKey[key];
    result[key] = meta ? castSignalValue(val, meta) : val;
  }
  return result;
}

/**
 * Validate that all required signals have non-null, non-empty values.
 * Returns an array of missing signal keys.
 *
 * @param {object} signalValues - current form values
 * @param {Array}  signalsMeta  - pack.signals array
 * @returns {string[]}          - keys of missing required signals
 */
export function getMissingRequiredSignals(signalValues, signalsMeta) {
  if (!Array.isArray(signalsMeta)) return [];
  return signalsMeta
    .filter((s) => s.required)
    .filter((s) => {
      const v = signalValues[s.key];
      return v === null || v === undefined || v === '';
    })
    .map((s) => s.key);
}

/**
 * Get the currency symbol from a domain pack's unit metadata.
 * Falls back to the currency code string if no symbol mapping is known.
 *
 * @param {object|null} pack - the full domain pack object
 * @returns {string}
 */
export function getCurrencySymbol(pack) {
  const code = pack?.unit?.code;
  const symbols = { INR: '₹', USD: '$', EUR: '€', GBP: '£', PCT: '' };
  return code ? (symbols[code] ?? code) : '';
}

/**
 * GET /v1/store/products
 * Fetches all products with authoritative inventory and dynamic demand signals.
 */
export async function fetchStoreProducts() {
  try {
    const res = await fetch(`${BASE}/v1/store/products`);
    return parseResponse(res);
  } catch (err) {
    return { data: null, error: `Network error: ${err.message}` };
  }
}

/**
 * GET /v1/store/products/:productId
 */
export async function fetchStoreProduct(productId) {
  try {
    const res = await fetch(`${BASE}/v1/store/products/${encodeURIComponent(productId)}`);
    return parseResponse(res);
  } catch (err) {
    return { data: null, error: `Network error: ${err.message}` };
  }
}

/**
 * POST /v1/store/quote
 * Revalidates prices and stock for a set of items in the cart.
 */
export async function fetchStoreQuote(items, customerTier = 'guest', isFlashSale = false) {
  try {
    const res = await fetch(`${BASE}/v1/store/quote`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        items: items.map((it) => ({
          product_id: it.product?.id || it.product_id,
          quantity: it.qty || it.quantity,
          expected_unit_price: it.priceData?.price ?? it.unit_price,
        })),
        customer_tier: customerTier,
        is_flash_sale: isFlashSale,
      }),
    });
    return parseResponse(res);
  } catch (err) {
    return { data: null, error: `Network error: ${err.message}` };
  }
}

/**
 * POST /v1/store/checkout
 * Executes transactional purchase with atomic inventory decrement.
 */
export async function checkoutStoreOrder({
  idempotencyKey,
  items,
  customerTier = 'guest',
  isFlashSale = false,
  confirmPriceChange = false,
}) {
  try {
    const res = await fetch(`${BASE}/v1/store/checkout`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Idempotency-Key': idempotencyKey,
      },
      body: JSON.stringify({
        idempotency_key: idempotencyKey,
        items: items.map((it) => ({
          product_id: it.product?.id || it.product_id,
          quantity: it.qty || it.quantity,
          expected_unit_price: it.priceData?.price ?? it.unit_price,
        })),
        customer_tier: customerTier,
        is_flash_sale: isFlashSale,
        confirm_price_change: confirmPriceChange,
      }),
    });
    return parseResponse(res);
  } catch (err) {
    return { data: null, error: `Network error: ${err.message}` };
  }
}

/**
 * GET /v1/store/orders/:orderId
 */
export async function fetchStoreOrder(orderId) {
  try {
    const res = await fetch(`${BASE}/v1/store/orders/${encodeURIComponent(orderId)}`);
    return parseResponse(res);
  } catch (err) {
    return { data: null, error: `Network error: ${err.message}` };
  }
}

/**
 * GET /v1/store/recommendations
 */
export async function fetchStoreRecommendations(productId = null, limit = 4) {
  try {
    const url = productId
      ? `${BASE}/v1/store/recommendations?product_id=${encodeURIComponent(productId)}&limit=${limit}`
      : `${BASE}/v1/store/recommendations?limit=${limit}`;
    const res = await fetch(url);
    return parseResponse(res);
  } catch (err) {
    return { data: null, error: `Network error: ${err.message}` };
  }
}

/**
 * GET /v1/analytics/overview
 */
export async function fetchAnalyticsOverview(domain = 'ecommerce', range = '7d') {
  try {
    const url = `${BASE}/v1/analytics/overview?domain=${encodeURIComponent(domain)}&range=${encodeURIComponent(range)}`;
    const res = await fetch(url);
    return parseResponse(res);
  } catch (err) {
    return { data: null, error: `Network error: ${err.message}` };
  }
}

/**
 * GET /v1/analytics/pricing-performance
 */
export async function fetchPricingPerformance(domain = 'ecommerce', limit = 50) {
  try {
    const url = `${BASE}/v1/analytics/pricing-performance?domain=${encodeURIComponent(domain)}&limit=${limit}`;
    const res = await fetch(url);
    return parseResponse(res);
  } catch (err) {
    return { data: null, error: `Network error: ${err.message}` };
  }
}

/**
 * GET /v1/analytics/alerts
 */
export async function fetchAnalyticsAlerts(domain = 'ecommerce') {
  try {
    const url = `${BASE}/v1/analytics/alerts?domain=${encodeURIComponent(domain)}`;
    const res = await fetch(url);
    return parseResponse(res);
  } catch (err) {
    return { data: null, error: `Network error: ${err.message}` };
  }
}

/**
 * POST /v1/analytics/analyst
 */
export async function queryAnalyticsAnalyst(query, domain = 'ecommerce') {
  try {
    const res = await fetch(`${BASE}/v1/analytics/analyst`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, domain }),
    });
    return parseResponse(res);
  } catch (err) {
    return { data: null, error: `Network error: ${err.message}` };
  }
}

/**
 * POST /v1/simulate/compare
 */
export async function fetchSimulateCompare(domain, signalsBefore, signalsAfter) {
  try {
    const res = await fetch(`${BASE}/v1/simulate/compare`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        domain,
        signals_before: signalsBefore,
        signals_after: signalsAfter,
      }),
    });
    return parseResponse(res);
  } catch (err) {
    return { data: null, error: `Network error: ${err.message}` };
  }
}

/**
 * GET /v1/context/:domain
 */
export async function fetchContext(domain) {
  try {
    const res = await fetch(`${BASE}/v1/context/${encodeURIComponent(domain)}`);
    return parseResponse(res);
  } catch (err) {
    return { data: null, error: `Network error: ${err.message}` };
  }
}

/**
 * PUT /v1/context/:domain
 */
export async function updateContext(domain, signals, ttlSeconds = 300) {
  try {
    const res = await fetch(`${BASE}/v1/context/${encodeURIComponent(domain)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ signals, ttl_seconds: ttlSeconds }),
    });
    return parseResponse(res);
  } catch (err) {
    return { data: null, error: `Network error: ${err.message}` };
  }
}

/**
 * DELETE /v1/context/:domain
 */
export async function deleteContext(domain) {
  try {
    const res = await fetch(`${BASE}/v1/context/${encodeURIComponent(domain)}`, {
      method: 'DELETE',
    });
    return parseResponse(res);
  } catch (err) {
    return { data: null, error: `Network error: ${err.message}` };
  }
}

/**
 * GET /v1/scorecard
 */
export async function fetchScorecard() {
  try {
    const res = await fetch(`${BASE}/v1/scorecard`);
    return parseResponse(res);
  } catch (err) {
    return { data: null, error: `Network error: ${err.message}` };
  }
}

/**
 * GET /v1/audit/log
 */
export async function fetchAuditLog(domain = null, limit = 50) {
  try {
    const url = domain
      ? `${BASE}/v1/audit/log?pack_id=${encodeURIComponent(domain)}&limit=${limit}`
      : `${BASE}/v1/audit/log?limit=${limit}`;
    const res = await fetch(url);
    return parseResponse(res);
  } catch (err) {
    return { data: null, error: `Network error: ${err.message}` };
  }
}

/**
 * GET /v1/audit/verify
 */
export async function fetchAuditVerification(domain = null) {
  try {
    const url = domain
      ? `${BASE}/v1/audit/verify?pack_id=${encodeURIComponent(domain)}`
      : `${BASE}/v1/audit/verify`;
    const res = await fetch(url);
    return parseResponse(res);
  } catch (err) {
    return { data: null, error: `Network error: ${err.message}` };
  }
}

/**
 * GET /v1/domains/:domainId/versions
 */
export async function fetchDomainVersions(domainId) {
  try {
    const res = await fetch(`${BASE}/v1/domains/${encodeURIComponent(domainId)}/versions`);
    return parseResponse(res);
  } catch (err) {
    return { data: null, error: `Network error: ${err.message}` };
  }
}

/**
 * POST /v1/validate
 */
export async function validatePack(pack, actor = 'alice') {
  try {
    const res = await fetch(`${BASE}/v1/validate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pack, actor }),
    });
    return parseResponse(res);
  } catch (err) {
    return { data: null, error: `Network error: ${err.message}` };
  }
}

/**
 * POST /v1/draft
 */
export async function saveDraft(pack, actor = 'alice') {
  try {
    const res = await fetch(`${BASE}/v1/draft`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pack, actor }),
    });
    return parseResponse(res);
  } catch (err) {
    return { data: null, error: `Network error: ${err.message}` };
  }
}

/**
 * POST /v1/lifecycle/submit
 */
export async function submitLifecycle(packId, version, actor = 'alice') {
  try {
    const res = await fetch(`${BASE}/v1/lifecycle/submit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pack_id: packId, version, actor }),
    });
    return parseResponse(res);
  } catch (err) {
    return { data: null, error: `Network error: ${err.message}` };
  }
}

/**
 * POST /v1/lifecycle/approve
 */
export async function approveLifecycle(packId, version, actor = 'bob') {
  try {
    const res = await fetch(`${BASE}/v1/lifecycle/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pack_id: packId, version, actor }),
    });
    return parseResponse(res);
  } catch (err) {
    return { data: null, error: `Network error: ${err.message}` };
  }
}

/**
 * POST /v1/lifecycle/reject
 */
export async function rejectLifecycle(packId, version, actor = 'bob', reason = '') {
  try {
    const res = await fetch(`${BASE}/v1/lifecycle/reject`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pack_id: packId, version, actor, reason }),
    });
    return parseResponse(res);
  } catch (err) {
    return { data: null, error: `Network error: ${err.message}` };
  }
}

/**
 * POST /v1/publish
 */
export async function publishPack(packId, version, actor = 'bob', enforceRoleSeparation = true) {
  try {
    const res = await fetch(`${BASE}/v1/publish`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        pack_id: packId,
        version,
        actor,
        enforce_role_separation: enforceRoleSeparation,
      }),
    });
    return parseResponse(res);
  } catch (err) {
    return { data: null, error: `Network error: ${err.message}` };
  }
}

/**
 * POST /v1/rollback
 */
export async function rollbackPack(packId, targetVersion, actor = 'admin') {
  try {
    const res = await fetch(`${BASE}/v1/rollback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pack_id: packId, target_version: targetVersion, actor }),
    });
    return parseResponse(res);
  } catch (err) {
    return { data: null, error: `Network error: ${err.message}` };
  }
}

/**
 * POST /v1/domains/:domainId/bump
 */
export async function bumpDomainVersion(domainId, bumpType = 'minor', actor = 'alice') {
  try {
    const res = await fetch(`${BASE}/v1/domains/${encodeURIComponent(domainId)}/bump`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ bump_type: bumpType, actor }),
    });
    return parseResponse(res);
  } catch (err) {
    return { data: null, error: `Network error: ${err.message}` };
  }
}
