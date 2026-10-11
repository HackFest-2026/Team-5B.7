import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import DomainStudio from './components/DomainStudio.jsx';
import ScorecardView from './components/ScorecardView.jsx';

// Mock api.js
vi.mock('./api.js', async (importOriginal) => {
  const real = await importOriginal();
  return {
    ...real,
    fetchDomainVersions: vi.fn(),
    fetchAuditVerification: vi.fn(),
    validatePack: vi.fn(),
    saveDraft: vi.fn(),
    submitLifecycle: vi.fn(),
    approveLifecycle: vi.fn(),
    publishPack: vi.fn(),
    rollbackPack: vi.fn(),
    bumpDomainVersion: vi.fn(),
    fetchScorecard: vi.fn(),
    fetchAuditLog: vi.fn(),
  };
});

import {
  fetchDomainVersions,
  fetchAuditVerification,
  validatePack,
  saveDraft,
  submitLifecycle,
  approveLifecycle,
  publishPack,
  fetchScorecard,
  fetchAuditLog,
} from './api.js';

const AIRLINE_PACK = {
  pack_id: 'airline',
  version: '1.0.0',
  status: 'published',
  description: 'Synthetic airline fare pricing.',
  unit: { kind: 'currency', code: 'USD', decimals: 2 },
  signals: [
    { key: 'cabin_class', type: 'enum', values: ['economy', 'premium', 'business'], required: true },
    { key: 'base_fare', type: 'number', min: 20, max: 1000, required: true },
    { key: 'distance_km', type: 'number', min: 100, max: 10000, required: true },
  ],
  base: { type: 'formula', expr: 'base_fare + distance_km * 0.08' },
  stages: [
    { id: 'demand', stacking: 'first', description: 'Demand stage multiplier' },
  ],
  rules: [
    {
      id: 'R-DEMAND-CRITICAL',
      stage: 'demand',
      priority: 100,
      description: 'High demand multiplier',
      when: { all: [{ signal: 'demand_index', op: 'gte', value: 85 }] },
      then: { op: 'multiply', value: 2.4 },
    },
  ],
  constraints: [
    { id: 'C-MINIMUM-FARE', type: 'floor', expr: '50' },
    { id: 'C-FARE-CAP', type: 'ceiling', expr: 'base * 2.5' },
  ],
  rounding: { mode: 'nearest', step: 5 },
};

const HOSPITALITY_PACK = {
  pack_id: 'hospitality',
  version: '1.0.0',
  status: 'draft',
  description: 'Hotel room night pricing.',
  unit: { kind: 'currency', code: 'INR', decimals: 0 },
  signals: [
    { key: 'room_type', type: 'enum', values: ['standard', 'deluxe'], required: true },
  ],
  base: {
    type: 'table',
    by: 'room_type',
    values: { standard: 3200, deluxe: 4500 },
  },
  stages: [
    { id: 'demand', stacking: 'first', description: 'Demand tier' },
  ],
  rules: [
    {
      id: 'R-DEMAND-HIGH',
      stage: 'demand',
      priority: 20,
      description: 'High occupancy',
      when: { all: [{ signal: 'occupancy_pct', op: 'gte', value: 85 }] },
      then: { op: 'multiply', value: 1.3 },
    },
  ],
  constraints: [
    { id: 'C-FLOOR', type: 'floor', expr: 'base * 0.70' },
  ],
  rounding: { mode: 'nearest', step: 10 },
};

describe('DomainStudio — Task 1: Schema Rendering', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fetchDomainVersions.mockResolvedValue({ data: [] });
    fetchAuditVerification.mockResolvedValue({ data: { valid: true, total_records: 5, message: 'Chain intact' } });
  });

  it('renders formula base and actual rules and constraints for airline', () => {
    render(<DomainStudio activeDomainPack={AIRLINE_PACK} />);

    // Base formula
    expect(screen.getByText(/base_fare \+ distance_km \* 0\.08/)).toBeInTheDocument();
    expect(screen.getByText('formula')).toBeInTheDocument();

    // Rule rendering
    expect(screen.getByText('R-DEMAND-CRITICAL')).toBeInTheDocument();
    expect(screen.getByText(/Priority 100/)).toBeInTheDocument();

    // Constraint rendering
    expect(screen.getByText('C-MINIMUM-FARE')).toBeInTheDocument();
    expect(screen.getByText('C-FARE-CAP')).toBeInTheDocument();
  });

  it('renders lookup table base for hospitality', () => {
    render(<DomainStudio activeDomainPack={HOSPITALITY_PACK} />);

    expect(screen.getByText('table')).toBeInTheDocument();
    expect(screen.getByText('room_type')).toBeInTheDocument();
    expect(screen.getByText('R-DEMAND-HIGH')).toBeInTheDocument();
    expect(screen.getByText('C-FLOOR')).toBeInTheDocument();
  });
});

describe('DomainStudio — Task 4: Governance Lifecycle', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fetchDomainVersions.mockResolvedValue({
      data: [
        { version: '1.0.0', status: 'published', published_by: 'bob', fingerprint: 'abcdef123456' },
      ],
    });
    fetchAuditVerification.mockResolvedValue({ data: { valid: true, total_records: 12, message: 'Hash chain valid' } });
  });

  it('switches between author and approver actor identity', () => {
    render(<DomainStudio activeDomainPack={AIRLINE_PACK} />);

    const actorInput = screen.getByDisplayValue('alice');
    expect(actorInput).toBeInTheDocument();

    const switchBtn = screen.getByText(/Switch to Bob/i);
    fireEvent.click(switchBtn);

    expect(screen.getByDisplayValue('bob')).toBeInTheDocument();
  });

  it('displays cryptographic audit verification badge', async () => {
    render(<DomainStudio activeDomainPack={AIRLINE_PACK} />);

    await waitFor(() => {
      expect(screen.getByText(/Audit Hash Chain: VERIFIED INTACT/i)).toBeInTheDocument();
    });
  });
});

describe('ScorecardView — Task 2: Real Evidence Integration', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fetchScorecard.mockResolvedValue({
      data: {
        engine_benchmark: [
          { domain: 'hospitality', rps: 4261.0, p95_ms: 0.35 },
          { domain: 'airline', rps: 3778.5, p95_ms: 0.43 },
        ],
        api_benchmark: {
          results: [
            { domain: 'hospitality', rps: 50.5, p95_ms: 108.7 },
            { domain: 'airline', rps: 53.1, p95_ms: 106.2 },
          ],
        },
        correctness: {
          determinism_rate_pct: 100.0,
          price_match_rate_pct: 100.0,
          valid_cases: 90,
          constraint_violations_count: 0,
        },
        domains: [
          { pack_id: 'hospitality', name: 'Hospitality', base_description: 'Table', signals_count: 5, rules_count: 5, status: 'published' },
          { pack_id: 'ecommerce', name: 'E-commerce', base_description: 'Formula', signals_count: 8, rules_count: 9, status: 'published' },
          { pack_id: 'banking', name: 'Banking', base_description: 'Table', signals_count: 6, rules_count: 6, status: 'published' },
          { pack_id: 'ev_charging', name: 'EV Charging', base_description: 'Fixed', signals_count: 5, rules_count: 6, status: 'published' },
          { pack_id: 'airline', name: 'Airline', base_description: 'Formula', signals_count: 9, rules_count: 7, status: 'published' },
        ],
      },
    });

    fetchAuditLog.mockResolvedValue({
      data: [
        { id: 1, event: 'published', pack_id: 'airline', version: '1.0.0', actor: 'seed', entry_hash: 'abc12345' },
      ],
    });

    fetchAuditVerification.mockResolvedValue({
      data: { valid: true, total_records: 1, message: 'Verified' },
    });
  });

  it('renders measured evidence and all 5 domains', async () => {
    render(<ScorecardView />);

    await waitFor(() => {
      // Evidence metrics
      expect(screen.getByText(/4,261 req\/s/)).toBeInTheDocument();
      expect(screen.getByText('100% (90/90)')).toBeInTheDocument();
      expect(screen.getByText('0 breaches')).toBeInTheDocument();
      expect(screen.getByText('Not Measured in CI')).toBeInTheDocument();

      // All 5 domains present in table/dropdown
      expect(screen.getAllByText('Hospitality').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('E-commerce').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('Banking').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('EV Charging').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('Airline').length).toBeGreaterThanOrEqual(1);
    });
  });
});
