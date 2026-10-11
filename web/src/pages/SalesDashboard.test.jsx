import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import SalesDashboard from './SalesDashboard';

// Mock Recharts ResponsiveContainer for jsdom testing
vi.mock('recharts', async () => {
  const original = await vi.importActual('recharts');
  return {
    ...original,
    ResponsiveContainer: ({ children }) => <div className="mock-responsive-container">{children}</div>,
  };
});

describe('SalesDashboard Component', () => {
  beforeEach(() => {
    // Mock global.fetch with verified mock payloads
    global.fetch = vi.fn((url) => {
      if (url.includes('/v1/analytics/overview')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({
            domain: 'ecommerce',
            is_synthetic: true,
            data_source: 'Synthetic Demonstration Dataset',
            kpis: {
              revenue: 8500.5,
              units_sold: 12,
              order_volume: 7,
              average_selling_price: 708.38,
              gross_margin: null,
              gross_margin_note: 'COGS not configured',
              conversion_rate: null,
            },
            sales_trend: [{ date: '2026-10-11', revenue: 2500, units: 3, orders: 2 }],
            top_products: [{ id: 'ec-001', name: 'boAt Earphones', category: 'electronics', units_sold: 5, revenue: 3495 }],
            category_breakdown: [{ category: 'electronics', units_sold: 5, revenue: 3495 }],
          }),
        });
      }

      if (url.includes('/v1/analytics/pricing-performance')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({
            domain: 'ecommerce',
            evaluation_count: 42,
            pricing_source: 'Audit Log',
            price_trend: [{ index: 1, timestamp: '12:00:00', price: 699, domain: 'ecommerce' }],
            top_rules: [{ rule_id: 'R-DEMAND-HIGH', stage: 'demand', description: 'High demand multiplier', count: 18, trigger_pct: 42.9 }],
            constraint_hits: [{ constraint_id: 'C-FLOOR', type: 'floor', description: 'Floor constraint', count: 4, hit_pct: 9.5 }],
          }),
        });
      }

      if (url.includes('/v1/analytics/alerts')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve([
            {
              id: 'alt-1',
              type: 'warning',
              title: 'Floor Guardrail Active',
              fact: 'Floor hit in 4 evaluations',
              recommendation: 'Check discount stacking',
              domain: 'ecommerce',
            },
          ]),
        });
      }

      if (url.includes('/v1/simulate/compare')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({
            before: { price: 1000, base: 1000, trace: [{ fired: true, rule_id: 'R-BASE', step: 'R-BASE' }] },
            after: { price: 1150, base: 1000, trace: [{ fired: true, rule_id: 'R-SURGE', step: 'R-SURGE' }], fingerprint: 'abc123456789' },
            delta: 150,
            delta_pct: 15.0,
          }),
        });
      }

      if (url.includes('/v1/analytics/analyst')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({
            query: 'Which domain had the most sales?',
            can_answer: true,
            answer: 'E-commerce generated the most sales with ₹8,500.50 revenue.',
            evidence: { revenue: 8500.5 },
          }),
        });
      }

      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({}),
      });
    });
  });

  it('renders all 5 dashboard sections on initial load', async () => {
    render(<SalesDashboard activeDomain="ecommerce" />);

    // Header & Titles
    expect(screen.getByText(/Sales & Pricing Telemetry/i)).toBeInTheDocument();

    // Section 1: Sales Overview
    await waitFor(() => {
      expect(screen.getByText('Sales Overview')).toBeInTheDocument();
      expect(screen.getByText('₹8,500.50')).toBeInTheDocument();
      expect(screen.getByText('Avg Selling Price (ASP)')).toBeInTheDocument();
    });

    // Section 2: Pricing Performance
    expect(screen.getByText('Pricing Performance')).toBeInTheDocument();
    expect(screen.getByText(/42 Price Quotes Evaluated/i)).toBeInTheDocument();
    expect(screen.getByText('R-DEMAND-HIGH')).toBeInTheDocument();

    // Section 3: AI Business Analyst
    expect(screen.getByText('AI Business Analyst')).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/Ask a question/i)).toBeInTheDocument();

    // Section 4: What-If Analysis
    expect(screen.getByText('What-If Pricing Analysis')).toBeInTheDocument();

    // Section 5: Alerts & Opportunities
    expect(screen.getByText('Alerts & Opportunities')).toBeInTheDocument();
    expect(screen.getByText('Floor Guardrail Active')).toBeInTheDocument();
  });

  it('filters by subnav tab to show single section', async () => {
    render(<SalesDashboard activeDomain="ecommerce" />);

    await waitFor(() => {
      expect(screen.getByText('Sales Overview')).toBeInTheDocument();
    });

    // Click "3. AI Business Analyst" subnav tab
    const analystTab = screen.getByRole('button', { name: /3\. AI Business Analyst/i });
    fireEvent.click(analystTab);

    // AI Analyst section must be present
    expect(screen.getByText('AI Business Analyst')).toBeInTheDocument();

    // Sales Overview section should now be hidden
    expect(screen.queryByText('Sales Overview')).not.toBeInTheDocument();
  });

  it('allows asking AI Business Analyst a question', async () => {
    render(<SalesDashboard activeDomain="ecommerce" />);

    await waitFor(() => {
      expect(screen.getByText('AI Business Analyst')).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText(/Ask a question/i);
    const askButton = screen.getByRole('button', { name: /Ask/i });

    fireEvent.change(input, { target: { value: 'Which domain had the most sales?' } });
    fireEvent.click(askButton);

    await waitFor(() => {
      expect(screen.getByText(/E-commerce generated the most sales/i)).toBeInTheDocument();
    });
  });
});
