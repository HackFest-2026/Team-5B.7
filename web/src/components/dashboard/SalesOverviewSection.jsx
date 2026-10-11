import React from 'react';
import { 
  TrendingUp, 
  ShoppingBag, 
  DollarSign, 
  Hash, 
  Calendar, 
  AlertCircle,
  Database,
  ArrowUpRight,
  Info
} from 'lucide-react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
} from 'recharts';

export default function SalesOverviewSection({
  salesData,
  timeRange,
  setTimeRange,
  selectedCategory,
  setSelectedCategory,
  loading,
}) {
  const kpis = salesData?.kpis || {};
  const isSynthetic = salesData?.is_synthetic;
  const trend = salesData?.sales_trend || [];
  const topProducts = salesData?.top_products || [];
  const categories = salesData?.category_breakdown || [];

  return (
    <div className="dash-section" id="sales-overview-section">
      <div className="dash-section-header">
        <div>
          <h2 className="dash-section-title">Sales Overview</h2>
          <p className="dash-section-subtitle">
            Revenue and volume calculated exclusively from completed order transactions.
          </p>
        </div>

        {/* Filters */}
        <div className="dash-filter-row">
          <div className="dash-badge-source" title={salesData?.data_source}>
            <Database size={13} />
            <span>{isSynthetic ? 'Demo Dataset (No live orders yet)' : 'Authoritative Store Orders'}</span>
          </div>

          <div className="dash-time-filters">
            {['today', '7d', '30d', 'all'].map((r) => (
              <button
                key={r}
                className={`dash-pill-btn ${timeRange === r ? 'active' : ''}`}
                onClick={() => setTimeRange(r)}
              >
                {r === 'today' ? 'Today' : r === '7d' ? '7 Days' : r === '30d' ? '30 Days' : 'All Time'}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="dash-kpi-grid">
        <div className="dash-kpi-card">
          <div className="dash-kpi-header">
            <span className="dash-kpi-label">Total Revenue</span>
            <span className="dash-kpi-icon-wrap emerald">
              <DollarSign size={18} />
            </span>
          </div>
          <div className="dash-kpi-value">
            ₹{Number(kpis.revenue || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
          </div>
          <div className="dash-kpi-meta">
            From {kpis.order_volume || 0} completed orders
          </div>
        </div>

        <div className="dash-kpi-card">
          <div className="dash-kpi-header">
            <span className="dash-kpi-label">Units Sold</span>
            <span className="dash-kpi-icon-wrap blue">
              <ShoppingBag size={18} />
            </span>
          </div>
          <div className="dash-kpi-value">{kpis.units_sold || 0}</div>
          <div className="dash-kpi-meta">Items purchased</div>
        </div>

        <div className="dash-kpi-card">
          <div className="dash-kpi-header">
            <span className="dash-kpi-label">Order Volume</span>
            <span className="dash-kpi-icon-wrap purple">
              <Hash size={18} />
            </span>
          </div>
          <div className="dash-kpi-value">{kpis.order_volume || 0}</div>
          <div className="dash-kpi-meta">Confirmed checkout checkouts</div>
        </div>

        <div className="dash-kpi-card">
          <div className="dash-kpi-header">
            <span className="dash-kpi-label">Avg Selling Price (ASP)</span>
            <span className="dash-kpi-icon-wrap amber">
              <TrendingUp size={18} />
            </span>
          </div>
          <div className="dash-kpi-value">
            ₹{Number(kpis.average_selling_price || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
          </div>
          <div className="dash-kpi-meta">Formula: Revenue / Units Sold</div>
        </div>
      </div>

      {/* Missing Metric Disclosures (Gross Margin & Conversion Rate) */}
      <div className="dash-notice-bar">
        <Info size={16} className="dash-notice-icon" />
        <div className="dash-notice-content">
          <span>
            <strong>Gross Margin & Conversion Rate:</strong>{' '}
            {kpis.gross_margin_note} User impression sessions are not tracked, so conversion rate is uncomputed rather than estimated.
          </span>
        </div>
      </div>

      {/* Charts Grid */}
      <div className="dash-charts-grid">
        {/* Revenue Trend Area Chart */}
        <div className="dash-chart-card">
          <div className="dash-chart-header">
            <h3 className="dash-chart-title">Revenue Trend</h3>
            <span className="dash-chart-badge">₹ Daily Gross</span>
          </div>
          <div className="dash-chart-body" style={{ height: 260 }}>
            {trend.length === 0 ? (
              <div className="dash-empty-state">No trend data available for this range.</div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={trend} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                  <defs>
                    <linearGradient id="revenueGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#0f766e" stopOpacity={0.4} />
                      <stop offset="95%" stopColor="#0f766e" stopOpacity={0.0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                  <XAxis dataKey="date" stroke="#94a3b8" fontSize={11} tickLine={false} />
                  <YAxis stroke="#94a3b8" fontSize={11} tickLine={false} />
                  <Tooltip
                    contentStyle={{ background: '#fff', borderRadius: '8px', border: '1px solid #e2e8f0', boxShadow: '0 4px 12px rgba(0,0,0,0.06)' }}
                    formatter={(val) => [`₹${val.toLocaleString()}`, 'Revenue']}
                  />
                  <Area
                    type="monotone"
                    dataKey="revenue"
                    stroke="#0f766e"
                    strokeWidth={2.5}
                    fillOpacity={1}
                    fill="url(#revenueGrad)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* Units Sold Bar Chart */}
        <div className="dash-chart-card">
          <div className="dash-chart-header">
            <h3 className="dash-chart-title">Units Sold by Date</h3>
            <span className="dash-chart-badge">Volume</span>
          </div>
          <div className="dash-chart-body" style={{ height: 260 }}>
            {trend.length === 0 ? (
              <div className="dash-empty-state">No volume data available.</div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={trend} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                  <XAxis dataKey="date" stroke="#94a3b8" fontSize={11} tickLine={false} />
                  <YAxis stroke="#94a3b8" fontSize={11} tickLine={false} allowDecimals={false} />
                  <Tooltip
                    contentStyle={{ background: '#fff', borderRadius: '8px', border: '1px solid #e2e8f0' }}
                    formatter={(val) => [val, 'Units']}
                  />
                  <Bar dataKey="units" fill="#0284c7" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      </div>

      {/* Top Products Table */}
      <div className="dash-table-card">
        <div className="dash-chart-header">
          <h3 className="dash-chart-title">Top Selling Products</h3>
          <span className="dash-chart-badge">{topProducts.length} items ranked</span>
        </div>
        <div className="dash-table-wrap">
          <table className="dash-table">
            <thead>
              <tr>
                <th>Product Name</th>
                <th>Category</th>
                <th style={{ textAlign: 'right' }}>Units Sold</th>
                <th style={{ textAlign: 'right' }}>Total Revenue</th>
              </tr>
            </thead>
            <tbody>
              {topProducts.length === 0 ? (
                <tr>
                  <td colSpan={4} style={{ textAlign: 'center', padding: '2rem' }}>
                    No products sold yet in this time frame.
                  </td>
                </tr>
              ) : (
                topProducts.map((p) => (
                  <tr key={p.id}>
                    <td className="dash-table-strong">{p.name}</td>
                    <td>
                      <span className="dash-cat-tag">{p.category}</span>
                    </td>
                    <td style={{ textAlign: 'right', fontWeight: 600 }}>{p.units_sold}</td>
                    <td style={{ textAlign: 'right', fontWeight: 700, color: '#0f766e' }}>
                      ₹{p.revenue.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
