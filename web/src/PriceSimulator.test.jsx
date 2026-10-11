/**
 * PriceSimulator.test.jsx
 *
 * Component tests for PriceSimulator using React Testing Library + Vitest.
 * API requests are intercepted with vi.mock so no real network calls are made.
 *
 * Contract tested:
 *   Request:  POST /v1/price { domain, signals }
 *   Response: { price, base, pack_id, pack_version, fingerprint, trace[] }
 *   Sweep:    POST /v1/simulate/sweep
 *             returns [{ signal_value, price, fingerprint }]
 */
import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import PriceSimulator from './components/PriceSimulator.jsx';

// ---------------------------------------------------------------------------
// Mock the entire api.js module so no real fetch calls happen
// ---------------------------------------------------------------------------
vi.mock('./api.js', async (importOriginal) => {
  // Re-export the pure helpers as real implementations
  const real = await importOriginal();
  return {
    ...real,
    // Only mock network calls
    fetchPrice: vi.fn(),
    fetchSweep: vi.fn(),
  };
});

import { fetchPrice, fetchSweep } from './api.js';

// ---------------------------------------------------------------------------
// Domain pack fixtures — mirrors actual JSON pack shapes
// ---------------------------------------------------------------------------

const HOSPITALITY_PACK = {
  pack_id: 'hospitality',
  version: '1.0.0',
  description: 'Hotel room night pricing.',
  unit: { kind: 'currency', code: 'INR', decimals: 0 },
  signals: [
    { key: 'room_type', type: 'enum', values: ['standard', 'deluxe', 'suite'], required: true },
    { key: 'occupancy_pct', type: 'number', min: 0, max: 100, required: true },
    { key: 'days_to_stay', type: 'integer', min: 1, max: 365, required: false },
    { key: 'stay_date_dow', type: 'enum', values: ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'], required: false },
    { key: 'loyalty_tier', type: 'enum', values: ['none', 'silver', 'gold'], required: false },
  ],
};

const ECOMMERCE_PACK = {
  pack_id: 'ecommerce',
  version: '1.0.0',
  description: 'E-commerce dynamic product pricing.',
  unit: { kind: 'currency', code: 'INR', decimals: 2 },
  signals: [
    { key: 'category', type: 'enum', values: ['electronics', 'fashion', 'grocery', 'home_appliances', 'beauty'], required: true },
    { key: 'mrp', type: 'number', min: 1, max: 1000000, required: true },
    { key: 'inventory_pct', type: 'number', min: 0, max: 100, required: true },
    { key: 'demand_score', type: 'number', min: 0, max: 100, required: true },
    { key: 'customer_tier', type: 'enum', values: ['guest', 'regular', 'prime', 'elite'], required: false },
    { key: 'quantity', type: 'integer', min: 1, max: 500, required: false },
    { key: 'is_flash_sale', type: 'boolean', required: false },
    { key: 'days_since_listed', type: 'integer', min: 0, max: 3650, required: false },
  ],
};

const BANKING_PACK = {
  pack_id: 'banking',
  version: '1.0.0',
  description: 'Personal loan interest rate pricing.',
  unit: { kind: 'rate', code: 'PCT', decimals: 2 },
  signals: [
    { key: 'loan_type', type: 'enum', values: ['personal', 'home', 'auto', 'education'], required: true },
    { key: 'credit_score', type: 'integer', min: 300, max: 900, required: true },
    { key: 'loan_amount', type: 'number', min: 10000, max: 10000000, required: true },
    { key: 'loan_term_months', type: 'integer', min: 6, max: 360, required: true },
    { key: 'customer_segment', type: 'enum', values: ['new', 'regular', 'premium'], required: false },
    { key: 'risk_tier', type: 'enum', values: ['low', 'medium', 'high', 'very_high'], required: false },
  ],
};

const EV_PACK = {
  pack_id: 'ev_charging',
  version: '1.0.0',
  description: 'EV charging per-kWh pricing.',
  unit: { kind: 'currency', code: 'INR', decimals: 2 },
  signals: [
    { key: 'charger_type', type: 'enum', values: ['slow', 'fast', 'ultra_fast'], required: true },
    { key: 'time_of_day', type: 'enum', values: ['peak', 'off_peak', 'super_off_peak'], required: true },
    { key: 'grid_load', type: 'number', min: 0, max: 100, required: false },
    { key: 'membership', type: 'enum', values: ['none', 'basic', 'premium'], required: false },
    { key: 'session_duration', type: 'number', min: 0.1, max: 24, required: false },
  ],
};

// Canonical success response matching PriceResult.to_dict()
const PRICE_SUCCESS = {
  price: 3520,
  base: 3200,
  pack_id: 'hospitality',
  pack_version: '1.0.0',
  fingerprint: 'abcdef1234567890abcd',
  trace: [
    { step: 'base', rule_id: null, stage: 'base', before: null, after: 3200, action: 'resolve_base', description: 'Base price resolved', fired: true },
    { step: 'R-DEMAND-HIGH', rule_id: 'R-DEMAND-HIGH', stage: 'demand', before: 3200, after: 3520, action: 'multiply', description: 'High occupancy (≥85%) → +30%', fired: true },
    { step: 'R-DEMAND-VERY-HIGH', rule_id: 'R-DEMAND-VERY-HIGH', stage: 'demand', before: 3200, after: 3200, action: 'multiply', description: 'Very high occupancy (≥95%) → +40%', fired: false },
    { step: 'rounding', rule_id: null, stage: 'rounding', before: 3520, after: 3520, action: 'round(nearest, step=10)', description: 'Final rounding applied', fired: true },
  ],
};

// ---------------------------------------------------------------------------
// Helper
// ---------------------------------------------------------------------------
function renderSimulator(pack) {
  return render(<PriceSimulator activeDomainPack={pack} />);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('PriceSimulator — domain rendering', () => {
  beforeEach(() => {
    fetchPrice.mockReset();
    fetchSweep.mockReset();
  });

  it('shows loading state before pack is provided', () => {
    render(<PriceSimulator activeDomainPack={null} />);
    expect(screen.getByText(/loading domain pack details/i)).toBeInTheDocument();
  });

  // --- Signal array rendering ---

  it('renders hospitality signals from the signals array (not as object keys)', () => {
    fetchPrice.mockResolvedValue({ data: PRICE_SUCCESS, error: null });
    renderSimulator(HOSPITALITY_PACK);
    // Signal labels come from sig.key (not array index)
    expect(screen.getByText(/room type/i)).toBeInTheDocument();
    expect(screen.getByText(/occupancy pct/i)).toBeInTheDocument();
    expect(screen.getByText(/loyalty tier/i)).toBeInTheDocument();
  });

  it('renders enum options from signal.values (not allowed_values)', () => {
    fetchPrice.mockResolvedValue({ data: PRICE_SUCCESS, error: null });
    renderSimulator(HOSPITALITY_PACK);
    // The room_type select must show values from signal.values
    const select = screen.getByRole('combobox', { name: /room_type/i });
    const options = within(select).getAllByRole('option');
    expect(options.map(o => o.value)).toEqual(['standard', 'deluxe', 'suite']);
  });

  it('renders ecommerce boolean signal as checkbox', () => {
    fetchPrice.mockResolvedValue({ data: null, error: null });
    renderSimulator(ECOMMERCE_PACK);
    // is_flash_sale is boolean
    const checkbox = screen.getByRole('checkbox', { name: /is_flash_sale/i });
    expect(checkbox).toBeInTheDocument();
    expect(checkbox.checked).toBe(false);
  });

  it('renders banking integer signal as range input', () => {
    fetchPrice.mockResolvedValue({ data: null, error: null });
    renderSimulator(BANKING_PACK);
    const slider = screen.getByRole('slider', { name: /credit_score/i });
    expect(slider).toBeInTheDocument();
    expect(slider.min).toBe('300');
    expect(slider.max).toBe('900');
  });

  it('renders ev_charging signals correctly', () => {
    fetchPrice.mockResolvedValue({ data: null, error: null });
    renderSimulator(EV_PACK);
    expect(screen.getByText(/charger type/i)).toBeInTheDocument();
    expect(screen.getByText(/time of day/i)).toBeInTheDocument();
    const chargerSelect = screen.getByRole('combobox', { name: /charger_type/i });
    const opts = within(chargerSelect).getAllByRole('option');
    expect(opts.map(o => o.value)).toEqual(['slow', 'fast', 'ultra_fast']);
  });

  it('marks required signals with asterisk', () => {
    fetchPrice.mockResolvedValue({ data: null, error: null });
    renderSimulator(HOSPITALITY_PACK);
    // room_type and occupancy_pct are required=true
    // Check the label area contains asterisk markers
    const labels = screen.getAllByText('*');
    expect(labels.length).toBeGreaterThanOrEqual(2);
  });
});

// ---------------------------------------------------------------------------
// Request payload contract
// ---------------------------------------------------------------------------
describe('PriceSimulator — request payload', () => {
  beforeEach(() => {
    fetchPrice.mockReset();
  });

  it('calls fetchPrice with { domain, signals } — not domain_id or context', async () => {
    fetchPrice.mockResolvedValue({ data: PRICE_SUCCESS, error: null });
    renderSimulator(HOSPITALITY_PACK);

    const btn = screen.getByRole('button', { name: /calculate price/i });
    fireEvent.click(btn);

    await waitFor(() => {
      expect(fetchPrice).toHaveBeenCalled();
    });

    const [domainArg, signalsArg] = fetchPrice.mock.calls[0];
    expect(domainArg).toBe('hospitality');
    expect(signalsArg).toBeDefined();
    expect(typeof signalsArg).toBe('object');
    // Must NOT contain domain_id or context
    expect(signalsArg).not.toHaveProperty('domain_id');
    expect(signalsArg).not.toHaveProperty('context');
  });

  it('sends integer signals as actual integers (not floats)', async () => {
    fetchPrice.mockResolvedValue({ data: null, error: null });
    renderSimulator(BANKING_PACK);

    const btn = screen.getByRole('button', { name: /calculate price/i });
    fireEvent.click(btn);

    await waitFor(() => expect(fetchPrice).toHaveBeenCalled());

    const [, signalsArg] = fetchPrice.mock.calls[0];
    expect(Number.isInteger(signalsArg.credit_score)).toBe(true);
    expect(Number.isInteger(signalsArg.loan_term_months)).toBe(true);
  });

  it('sends boolean signals as actual booleans', async () => {
    fetchPrice.mockResolvedValue({ data: null, error: null });
    renderSimulator(ECOMMERCE_PACK);

    const btn = screen.getByRole('button', { name: /calculate price/i });
    fireEvent.click(btn);

    await waitFor(() => expect(fetchPrice).toHaveBeenCalled());

    const [, signalsArg] = fetchPrice.mock.calls[0];
    expect(typeof signalsArg.is_flash_sale).toBe('boolean');
  });

  it('does NOT send previous_price field', async () => {
    fetchPrice.mockResolvedValue({ data: PRICE_SUCCESS, error: null });
    renderSimulator(HOSPITALITY_PACK);

    fireEvent.click(screen.getByRole('button', { name: /calculate price/i }));
    await waitFor(() => expect(fetchPrice).toHaveBeenCalled());

    const [, signalsArg] = fetchPrice.mock.calls[0];
    // previous_price is not a signal key and must not be in signals dict
    expect(signalsArg).not.toHaveProperty('previous_price');
  });
});

// ---------------------------------------------------------------------------
// Response field rendering
// ---------------------------------------------------------------------------
describe('PriceSimulator — response rendering', () => {
  beforeEach(() => {
    fetchPrice.mockReset();
  });

  it('displays result.price (not final_price)', async () => {
    fetchPrice.mockResolvedValue({ data: PRICE_SUCCESS, error: null });
    renderSimulator(HOSPITALITY_PACK);

    fireEvent.click(screen.getByRole('button', { name: /calculate price/i }));

    await waitFor(() => {
      // 3520 in INR format within the main price display
      const priceMain = document.querySelector('.price-main');
      expect(within(priceMain).getByText(/3,520|3520/)).toBeInTheDocument();
    });
  });

  it('displays result.base (not base_price)', async () => {
    fetchPrice.mockResolvedValue({ data: PRICE_SUCCESS, error: null });
    renderSimulator(HOSPITALITY_PACK);

    fireEvent.click(screen.getByRole('button', { name: /calculate price/i }));

    await waitFor(() => {
      expect(screen.getByText(/^Base:/)).toBeInTheDocument();
      expect(screen.getAllByText(/3,200|3200/).length).toBeGreaterThan(0);
    });
  });

  it('displays fingerprint from result.fingerprint', async () => {
    fetchPrice.mockResolvedValue({ data: PRICE_SUCCESS, error: null });
    renderSimulator(HOSPITALITY_PACK);

    fireEvent.click(screen.getByRole('button', { name: /calculate price/i }));

    await waitFor(() => {
      expect(screen.getByText(/Fingerprint:/i)).toBeInTheDocument();
    });
  });

  it('renders trace steps using step.after (not step.price_after)', async () => {
    fetchPrice.mockResolvedValue({ data: PRICE_SUCCESS, error: null });
    renderSimulator(HOSPITALITY_PACK);

    fireEvent.click(screen.getByRole('button', { name: /calculate price/i }));

    await waitFor(() => {
      // First trace step in timeline: base price 3200
      const timeline = document.querySelector('.trace-timeline');
      expect(within(timeline).getAllByText(/3,200|3200/).length).toBeGreaterThan(0);
    });
  });

  it('shows trace step description', async () => {
    fetchPrice.mockResolvedValue({ data: PRICE_SUCCESS, error: null });
    renderSimulator(HOSPITALITY_PACK);

    fireEvent.click(screen.getByRole('button', { name: /calculate price/i }));

    await waitFor(() => {
      expect(screen.getByText(/Base price resolved/i)).toBeInTheDocument();
    });
  });

  it('shows skipped trace steps with (skipped) label', async () => {
    fetchPrice.mockResolvedValue({ data: PRICE_SUCCESS, error: null });
    renderSimulator(HOSPITALITY_PACK);

    fireEvent.click(screen.getByRole('button', { name: /calculate price/i }));

    await waitFor(() => {
      expect(screen.getByText(/skipped/i)).toBeInTheDocument();
    });
  });

  it('handles empty trace array without crashing', async () => {
    fetchPrice.mockResolvedValue({
      data: { ...PRICE_SUCCESS, trace: [] },
      error: null,
    });
    renderSimulator(HOSPITALITY_PACK);

    fireEvent.click(screen.getByRole('button', { name: /calculate price/i }));

    await waitFor(() => {
      expect(screen.getByText(/No trace data returned/i)).toBeInTheDocument();
    });
  });

  it('handles missing trace field without crashing', async () => {
    const { trace: _ignored, ...noTrace } = PRICE_SUCCESS;
    fetchPrice.mockResolvedValue({ data: noTrace, error: null });
    renderSimulator(HOSPITALITY_PACK);

    fireEvent.click(screen.getByRole('button', { name: /calculate price/i }));

    await waitFor(() => {
      expect(screen.getByText(/No trace data returned/i)).toBeInTheDocument();
    });
  });

  it('uses INR symbol for INR domain', async () => {
    fetchPrice.mockResolvedValue({ data: PRICE_SUCCESS, error: null });
    renderSimulator(HOSPITALITY_PACK);

    fireEvent.click(screen.getByRole('button', { name: /calculate price/i }));

    await waitFor(() => {
      expect(screen.getAllByText(/₹/).length).toBeGreaterThan(0);
    });
  });

  it('uses no symbol for PCT (banking rate) domain', async () => {
    const bankResult = {
      price: 8.5,
      base: 10.5,
      pack_id: 'banking',
      pack_version: '1.0.0',
      fingerprint: 'abcdef1234567890',
      trace: [],
    };
    fetchPrice.mockResolvedValue({ data: bankResult, error: null });
    renderSimulator(BANKING_PACK);

    fireEvent.click(screen.getByRole('button', { name: /calculate price/i }));

    await waitFor(() => {
      // PCT symbol is '' — price number should appear without currency symbol prefix
      expect(screen.getByText(/8\.50/)).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// Error handling
// ---------------------------------------------------------------------------
describe('PriceSimulator — error handling', () => {
  beforeEach(() => {
    fetchPrice.mockReset();
  });

  it('shows inline error on HTTP 422 — no alert()', async () => {
    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});
    fetchPrice.mockResolvedValue({ data: null, error: "Missing required signal 'room_type'." });
    renderSimulator(HOSPITALITY_PACK);

    fireEvent.click(screen.getByRole('button', { name: /calculate price/i }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByRole('alert')).toHaveTextContent(/missing required signal/i);
    });

    expect(alertSpy).not.toHaveBeenCalled();
    alertSpy.mockRestore();
  });

  it('shows inline error on network failure', async () => {
    fetchPrice.mockResolvedValue({ data: null, error: 'Network error: Failed to fetch' });
    renderSimulator(HOSPITALITY_PACK);

    fireEvent.click(screen.getByRole('button', { name: /calculate price/i }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/network error/i);
    });
  });

  it('does not crash on malformed response (missing price)', async () => {
    fetchPrice.mockResolvedValue({ data: { pack_id: 'hospitality' }, error: null });
    renderSimulator(HOSPITALITY_PACK);

    fireEvent.click(screen.getByRole('button', { name: /calculate price/i }));

    await waitFor(() => {
      // Should render "—" for missing price, not throw
      expect(screen.getAllByText('—').length).toBeGreaterThan(0);
    });
  });
});

// ---------------------------------------------------------------------------
// Loading state and duplicate submission prevention
// ---------------------------------------------------------------------------
describe('PriceSimulator — loading state', () => {
  beforeEach(() => {
    fetchPrice.mockReset();
  });

  it('shows loading state while request is in flight', async () => {
    let resolvePrice;
    fetchPrice.mockImplementation(
      () => new Promise((res) => { resolvePrice = res; }),
    );
    renderSimulator(HOSPITALITY_PACK);

    const btn = screen.getByRole('button', { name: /calculate price/i });
    fireEvent.click(btn);

    // Button should be disabled / show loading text
    await waitFor(() => {
      expect(btn).toBeDisabled();
    });

    // Resolve to clean up
    resolvePrice({ data: PRICE_SUCCESS, error: null });
    await waitFor(() => {
      expect(btn).not.toBeDisabled();
    });
  });

  it('prevents duplicate submissions — fetchPrice called only once per click burst', async () => {
    let resolvePrice;
    fetchPrice.mockImplementation(
      () => new Promise((res) => { resolvePrice = res; }),
    );
    renderSimulator(HOSPITALITY_PACK);

    const btn = screen.getByRole('button', { name: /calculate price/i });

    // Click multiple times rapidly while in-flight
    fireEvent.click(btn);
    fireEvent.click(btn);
    fireEvent.click(btn);

    expect(fetchPrice).toHaveBeenCalledTimes(1);

    resolvePrice({ data: PRICE_SUCCESS, error: null });
    await waitFor(() => expect(btn).not.toBeDisabled());
  });
});

// ---------------------------------------------------------------------------
// Domain switching
// ---------------------------------------------------------------------------
describe('PriceSimulator — domain switching', () => {
  beforeEach(() => {
    fetchPrice.mockReset();
  });

  it('resets signals and result when domain pack changes', async () => {
    fetchPrice.mockResolvedValue({ data: PRICE_SUCCESS, error: null });
    const { rerender } = renderSimulator(HOSPITALITY_PACK);

    fireEvent.click(screen.getByRole('button', { name: /calculate price/i }));
    await waitFor(() => expect(fetchPrice).toHaveBeenCalled());

    // Switch to ecommerce
    fetchPrice.mockReset();
    fetchPrice.mockResolvedValue({ data: null, error: null });
    rerender(<PriceSimulator activeDomainPack={ECOMMERCE_PACK} />);

    // Ecommerce signals should appear
    await waitFor(() => {
      expect(screen.getAllByText(/mrp/i).length).toBeGreaterThan(0);
    });

    // Hospitality signals should not appear
    expect(screen.queryByText(/room type/i)).not.toBeInTheDocument();
  });

  it('renders all four domain packs without errors', async () => {
    fetchPrice.mockResolvedValue({ data: null, error: null });
    const packs = [HOSPITALITY_PACK, ECOMMERCE_PACK, BANKING_PACK, EV_PACK];
    for (const pack of packs) {
      const { unmount } = renderSimulator(pack);
      expect(screen.getByText(new RegExp(pack.pack_id, 'i'))).toBeInTheDocument();
      unmount();
    }
  });
});

// ---------------------------------------------------------------------------
// Sweep
// ---------------------------------------------------------------------------
describe('PriceSimulator — sweep', () => {
  beforeEach(() => {
    fetchPrice.mockReset();
    fetchSweep.mockReset();
  });

  it('calls fetchSweep with correct arguments on Run Sweep click', async () => {
    fetchPrice.mockResolvedValue({ data: PRICE_SUCCESS, error: null });
    fetchSweep.mockResolvedValue({
      data: [
        { signal_value: 0, price: 2880, fingerprint: 'abc' },
        { signal_value: 50, price: 3200, fingerprint: 'def' },
        { signal_value: 100, price: 4480, fingerprint: 'ghi' },
      ],
      error: null,
    });

    renderSimulator(HOSPITALITY_PACK);

    const sweepBtn = screen.getByRole('button', { name: /run sweep/i });
    fireEvent.click(sweepBtn);

    await waitFor(() => expect(fetchSweep).toHaveBeenCalled());

    const [domain, , sweepSig, sweepVals] = fetchSweep.mock.calls[0];
    expect(domain).toBe('hospitality');
    expect(typeof sweepSig).toBe('string');
    expect(Array.isArray(sweepVals)).toBe(true);
    expect(sweepVals.length).toBeGreaterThan(0);
  });

  it('renders sweep results using signal_value and price fields', async () => {
    fetchPrice.mockResolvedValue({ data: PRICE_SUCCESS, error: null });
    fetchSweep.mockResolvedValue({
      data: [
        { signal_value: 0, price: 2880, fingerprint: 'abc' },
        { signal_value: 100, price: 4480, fingerprint: 'ghi' },
      ],
      error: null,
    });

    renderSimulator(HOSPITALITY_PACK);

    const sweepBtn = screen.getByRole('button', { name: /run sweep/i });
    fireEvent.click(sweepBtn);

    await waitFor(() => {
      expect(screen.getByText(/2,880/)).toBeInTheDocument();
      expect(screen.getByText(/4,480/)).toBeInTheDocument();
    });
  });

  it('shows sweep error inline without alert()', async () => {
    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});
    fetchPrice.mockResolvedValue({ data: PRICE_SUCCESS, error: null });
    fetchSweep.mockResolvedValue({ data: null, error: 'Network error: Failed to fetch' });

    renderSimulator(HOSPITALITY_PACK);

    fireEvent.click(screen.getByRole('button', { name: /run sweep/i }));

    await waitFor(() => {
      expect(screen.getByText(/network error/i)).toBeInTheDocument();
    });

    expect(alertSpy).not.toHaveBeenCalled();
    alertSpy.mockRestore();
  });

  it('handles sweep entries with error field gracefully', async () => {
    fetchPrice.mockResolvedValue({ data: PRICE_SUCCESS, error: null });
    fetchSweep.mockResolvedValue({
      data: [
        { signal_value: 0, price: 2880, fingerprint: 'abc' },
        { signal_value: 50, error: 'Signal out of range' },
      ],
      error: null,
    });

    renderSimulator(HOSPITALITY_PACK);
    fireEvent.click(screen.getByRole('button', { name: /run sweep/i }));

    await waitFor(() => {
      // Error row should show "—" and Error badge
      expect(screen.getByText('Error')).toBeInTheDocument();
    });
  });
});
