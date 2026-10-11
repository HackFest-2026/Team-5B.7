/**
 * api.test.js — Unit tests for the api.js helper functions.
 *
 * Tests cover:
 *  - castSignalValue: correct type coercion per signal type
 *  - buildInitialSignals: default values from signals array
 *  - castAllSignals: batch casting
 *  - getMissingRequiredSignals: required field validation
 *  - getCurrencySymbol: symbol mapping
 */
import { describe, it, expect } from 'vitest';
import {
  castSignalValue,
  buildInitialSignals,
  castAllSignals,
  getMissingRequiredSignals,
  getCurrencySymbol,
  defaultSignalValue,
} from './api.js';

// ---------------------------------------------------------------------------
// castSignalValue
// ---------------------------------------------------------------------------
describe('castSignalValue', () => {
  it('casts integer signal to int', () => {
    const sig = { key: 'credit_score', type: 'integer' };
    expect(castSignalValue('820', sig)).toBe(820);
    expect(castSignalValue(820.9, sig)).toBe(820);
  });

  it('casts number signal to float', () => {
    const sig = { key: 'occupancy_pct', type: 'number' };
    expect(castSignalValue('75', sig)).toBe(75);
    expect(castSignalValue('75.5', sig)).toBe(75.5);
  });

  it('casts boolean signal', () => {
    const sig = { key: 'is_flash_sale', type: 'boolean' };
    expect(castSignalValue(true, sig)).toBe(true);
    expect(castSignalValue(false, sig)).toBe(false);
  });

  it('passes enum value through as-is', () => {
    const sig = { key: 'room_type', type: 'enum', values: ['standard', 'deluxe'] };
    expect(castSignalValue('deluxe', sig)).toBe('deluxe');
  });

  it('passes string value through as-is', () => {
    const sig = { key: 'name', type: 'string' };
    expect(castSignalValue('hello', sig)).toBe('hello');
  });

  it('returns null/undefined unchanged', () => {
    const sig = { key: 'x', type: 'number' };
    expect(castSignalValue(null, sig)).toBeNull();
    expect(castSignalValue(undefined, sig)).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// defaultSignalValue
// ---------------------------------------------------------------------------
describe('defaultSignalValue', () => {
  it('returns first enum value', () => {
    const sig = { type: 'enum', values: ['standard', 'deluxe'] };
    expect(defaultSignalValue(sig)).toBe('standard');
  });

  it('returns empty string for enum with no values', () => {
    const sig = { type: 'enum', values: [] };
    expect(defaultSignalValue(sig)).toBe('');
  });

  it('returns min for number signal with min', () => {
    const sig = { type: 'number', min: 10, max: 100 };
    expect(defaultSignalValue(sig)).toBe(10);
  });

  it('returns 0 for number signal without min', () => {
    const sig = { type: 'number' };
    expect(defaultSignalValue(sig)).toBe(0);
  });

  it('returns ceil(min) for integer', () => {
    const sig = { type: 'integer', min: 300 };
    expect(defaultSignalValue(sig)).toBe(300);
  });

  it('returns false for boolean', () => {
    const sig = { type: 'boolean' };
    expect(defaultSignalValue(sig)).toBe(false);
  });

  it('returns empty string for string', () => {
    const sig = { type: 'string' };
    expect(defaultSignalValue(sig)).toBe('');
  });
});

// ---------------------------------------------------------------------------
// buildInitialSignals
// ---------------------------------------------------------------------------
describe('buildInitialSignals', () => {
  it('builds initial values from a signals array', () => {
    const signals = [
      { key: 'room_type', type: 'enum', values: ['standard', 'deluxe'] },
      { key: 'occupancy_pct', type: 'number', min: 0, max: 100 },
      { key: 'days_to_stay', type: 'integer', min: 1, max: 365 },
      { key: 'is_flash_sale', type: 'boolean' },
    ];
    const init = buildInitialSignals(signals);
    expect(init).toEqual({
      room_type: 'standard',
      occupancy_pct: 0,
      days_to_stay: 1,
      is_flash_sale: false,
    });
  });

  it('returns empty object for non-array input', () => {
    expect(buildInitialSignals(null)).toEqual({});
    expect(buildInitialSignals({})).toEqual({});
    expect(buildInitialSignals(undefined)).toEqual({});
  });

  it('handles all four domain pack signal shapes without error', () => {
    // hospitality signals
    const hospitalitySignals = [
      { key: 'room_type', type: 'enum', values: ['standard', 'deluxe', 'suite'], required: true },
      { key: 'occupancy_pct', type: 'number', min: 0, max: 100, required: true },
      { key: 'days_to_stay', type: 'integer', min: 1, max: 365, required: false },
      { key: 'stay_date_dow', type: 'enum', values: ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'], required: false },
      { key: 'loyalty_tier', type: 'enum', values: ['none', 'silver', 'gold'], required: false },
    ];
    const h = buildInitialSignals(hospitalitySignals);
    expect(h.room_type).toBe('standard');
    expect(h.occupancy_pct).toBe(0);
    expect(h.days_to_stay).toBe(1);
    expect(h.stay_date_dow).toBe('mon');
    expect(h.loyalty_tier).toBe('none');

    // banking signals
    const bankingSignals = [
      { key: 'loan_type', type: 'enum', values: ['personal', 'home', 'auto', 'education'], required: true },
      { key: 'credit_score', type: 'integer', min: 300, max: 900, required: true },
      { key: 'loan_amount', type: 'number', min: 10000, max: 10000000, required: true },
      { key: 'loan_term_months', type: 'integer', min: 6, max: 360, required: true },
      { key: 'customer_segment', type: 'enum', values: ['new', 'regular', 'premium'], required: false },
      { key: 'risk_tier', type: 'enum', values: ['low', 'medium', 'high', 'very_high'], required: false },
    ];
    const b = buildInitialSignals(bankingSignals);
    expect(b.loan_type).toBe('personal');
    expect(b.credit_score).toBe(300);
    expect(b.loan_amount).toBe(10000);
    expect(b.loan_term_months).toBe(6);
    expect(b.customer_segment).toBe('new');
    expect(b.risk_tier).toBe('low');

    // ecommerce signals
    const ecomSignals = [
      { key: 'category', type: 'enum', values: ['electronics', 'fashion', 'grocery', 'home_appliances', 'beauty'], required: true },
      { key: 'mrp', type: 'number', min: 1, max: 1000000, required: true },
      { key: 'inventory_pct', type: 'number', min: 0, max: 100, required: true },
      { key: 'demand_score', type: 'number', min: 0, max: 100, required: true },
      { key: 'customer_tier', type: 'enum', values: ['guest', 'regular', 'prime', 'elite'], required: false },
      { key: 'quantity', type: 'integer', min: 1, max: 500, required: false },
      { key: 'is_flash_sale', type: 'boolean', required: false },
      { key: 'days_since_listed', type: 'integer', min: 0, max: 3650, required: false },
    ];
    const e = buildInitialSignals(ecomSignals);
    expect(e.category).toBe('electronics');
    expect(e.mrp).toBe(1);
    expect(e.is_flash_sale).toBe(false);
    expect(e.quantity).toBe(1);

    // ev_charging signals
    const evSignals = [
      { key: 'charger_type', type: 'enum', values: ['slow', 'fast', 'ultra_fast'], required: true },
      { key: 'time_of_day', type: 'enum', values: ['peak', 'off_peak', 'super_off_peak'], required: true },
      { key: 'grid_load', type: 'number', min: 0, max: 100, required: false },
      { key: 'membership', type: 'enum', values: ['none', 'basic', 'premium'], required: false },
      { key: 'session_duration', type: 'number', min: 0.1, max: 24, required: false },
    ];
    const ev = buildInitialSignals(evSignals);
    expect(ev.charger_type).toBe('slow');
    expect(ev.time_of_day).toBe('peak');
    expect(ev.grid_load).toBe(0);
    expect(ev.membership).toBe('none');
    expect(ev.session_duration).toBe(0.1);
  });
});

// ---------------------------------------------------------------------------
// castAllSignals
// ---------------------------------------------------------------------------
describe('castAllSignals', () => {
  const signalsMeta = [
    { key: 'credit_score', type: 'integer' },
    { key: 'loan_amount', type: 'number' },
    { key: 'loan_type', type: 'enum', values: ['personal', 'home'] },
    { key: 'is_active', type: 'boolean' },
  ];

  it('casts integer fields to int', () => {
    const result = castAllSignals({ credit_score: '820', loan_amount: '100000', loan_type: 'home', is_active: true }, signalsMeta);
    expect(result.credit_score).toBe(820);
    expect(typeof result.credit_score).toBe('number');
    expect(Number.isInteger(result.credit_score)).toBe(true);
  });

  it('casts number fields to float', () => {
    const result = castAllSignals({ credit_score: 820, loan_amount: '150000.5', loan_type: 'personal', is_active: false }, signalsMeta);
    expect(result.loan_amount).toBe(150000.5);
  });

  it('passes unknown keys through unchanged', () => {
    const result = castAllSignals({ credit_score: 820, unknown_field: 'foo' }, signalsMeta);
    expect(result.unknown_field).toBe('foo');
  });

  it('handles non-array signalsMeta gracefully', () => {
    const vals = { credit_score: '820' };
    expect(castAllSignals(vals, null)).toEqual(vals);
    expect(castAllSignals(vals, {})).toEqual(vals);
  });
});

// ---------------------------------------------------------------------------
// getMissingRequiredSignals
// ---------------------------------------------------------------------------
describe('getMissingRequiredSignals', () => {
  const signalsMeta = [
    { key: 'loan_type', type: 'enum', required: true, values: ['personal', 'home'] },
    { key: 'credit_score', type: 'integer', required: true },
    { key: 'customer_segment', type: 'enum', required: false, values: ['new', 'premium'] },
  ];

  it('returns empty array when all required signals are present', () => {
    const values = { loan_type: 'personal', credit_score: 820, customer_segment: 'new' };
    expect(getMissingRequiredSignals(values, signalsMeta)).toEqual([]);
  });

  it('returns missing required signal keys', () => {
    const values = { loan_type: 'personal' };
    const missing = getMissingRequiredSignals(values, signalsMeta);
    expect(missing).toContain('credit_score');
    expect(missing).not.toContain('customer_segment'); // not required
  });

  it('treats empty string as missing', () => {
    const values = { loan_type: '', credit_score: 820 };
    const missing = getMissingRequiredSignals(values, signalsMeta);
    expect(missing).toContain('loan_type');
  });

  it('treats null as missing', () => {
    const values = { loan_type: null, credit_score: 820 };
    const missing = getMissingRequiredSignals(values, signalsMeta);
    expect(missing).toContain('loan_type');
  });

  it('ignores optional signals', () => {
    const values = { loan_type: 'home', credit_score: 700 };
    const missing = getMissingRequiredSignals(values, signalsMeta);
    expect(missing).not.toContain('customer_segment');
  });

  it('handles non-array signalsMeta', () => {
    expect(getMissingRequiredSignals({}, null)).toEqual([]);
    expect(getMissingRequiredSignals({}, undefined)).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// getCurrencySymbol
// ---------------------------------------------------------------------------
describe('getCurrencySymbol', () => {
  it('returns ₹ for INR', () => {
    expect(getCurrencySymbol({ unit: { code: 'INR' } })).toBe('₹');
  });

  it('returns $ for USD', () => {
    expect(getCurrencySymbol({ unit: { code: 'USD' } })).toBe('$');
  });

  it('returns empty string for PCT (rate)', () => {
    expect(getCurrencySymbol({ unit: { code: 'PCT' } })).toBe('');
  });

  it('returns the code itself for unknown codes', () => {
    expect(getCurrencySymbol({ unit: { code: 'JPY' } })).toBe('JPY');
  });

  it('returns empty string for null pack', () => {
    expect(getCurrencySymbol(null)).toBe('');
    expect(getCurrencySymbol(undefined)).toBe('');
  });

  it('returns empty string for pack without unit', () => {
    expect(getCurrencySymbol({ pack_id: 'test' })).toBe('');
  });
});
