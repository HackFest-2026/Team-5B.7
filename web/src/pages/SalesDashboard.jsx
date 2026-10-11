import React, { useState, useEffect } from 'react';
import { 
  TrendingUp, 
  BarChart3, 
  Bot, 
  GitCompare, 
  Bell, 
  RefreshCw, 
  ExternalLink,
  ShoppingBag,
  Sparkles,
  Zap,
  PlusCircle,
  CheckCircle2
} from 'lucide-react';
import SalesOverviewSection from '../components/dashboard/SalesOverviewSection';
import PricingPerformanceSection from '../components/dashboard/PricingPerformanceSection';
import AiAnalystSection from '../components/dashboard/AiAnalystSection';
import WhatIfSection from '../components/dashboard/WhatIfSection';
import AlertsSection from '../components/dashboard/AlertsSection';
import { 
  fetchAnalyticsOverview, 
  fetchPricingPerformance, 
  fetchAnalyticsAlerts,
  checkoutStoreOrder
} from '../api';
import '../dashboard.css';

export default function SalesDashboard({ 
  activeDomain = 'ecommerce', 
  activeDomainPack, 
  onNavigateTab 
}) {
  const [subTab, setSubTab] = useState('all');
  const [timeRange, setTimeRange] = useState('7d');
  const [loading, setLoading] = useState(false);
  const [salesData, setSalesData] = useState(null);
  const [performanceData, setPerformanceData] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [placingOrder, setPlacingOrder] = useState(false);
  const [orderNotice, setOrderNotice] = useState(null);

  const loadAllAnalytics = async () => {
    setLoading(true);
    try {
      const [salesRes, perfRes, alertRes] = await Promise.all([
        fetchAnalyticsOverview(activeDomain, timeRange),
        fetchPricingPerformance(activeDomain, 50),
        fetchAnalyticsAlerts(activeDomain),
      ]);

      if (!salesRes.error) setSalesData(salesRes.data);
      if (!perfRes.error) setPerformanceData(perfRes.data);
      if (!alertRes.error) setAlerts(alertRes.data);
    } catch (e) {
      console.error('Failed to load dashboard data:', e);
    } finally {
      setLoading(false);
    }
  };

  const handleSingleClickOrder = async () => {
    setPlacingOrder(true);
    try {
      const key = 'dash_demo_' + Date.now() + '_' + Math.random().toString(36).slice(2, 7);
      const res = await checkoutStoreOrder({
        idempotencyKey: key,
        items: [{ product_id: 'ec-001', qty: 1 }],
        customerTier: 'prime',
        isFlashSale: false,
        confirmPriceChange: true,
      });
      if (!res.error) {
        setOrderNotice(`✓ 1-Click order simulated (${res.data?.id || 'Confirmed'})! Telemetry updated.`);
        setTimeout(() => setOrderNotice(null), 4000);
        await loadAllAnalytics();
      } else {
        setOrderNotice(`Order error: ${res.error}`);
      }
    } catch (err) {
      setOrderNotice(`Error: ${err.message}`);
    } finally {
      setPlacingOrder(false);
    }
  };

  useEffect(() => {
    loadAllAnalytics();
  }, [activeDomain, timeRange]);

  return (
    <div className="dash-container" id="rate-weaver-sales-dashboard">
      {/* Dashboard Top Banner */}
      <div className="dash-top-bar">
        <div>
          <div className="dash-breadcrumb">
            <span>RateWeaver Engine</span>
            <span>/</span>
            <span className="active">Sales &amp; Pricing Dashboard</span>
          </div>
          <h1 className="dash-main-title">Sales &amp; Pricing Telemetry</h1>
          <p className="dash-main-subtitle">
            Authoritative purchase records, dynamic pricing traces, scenario what-if analysis, and evidence-grounded AI analytics.
          </p>
        </div>

        <div className="dash-top-actions">
          <button
            className="dash-action-btn success"
            onClick={handleSingleClickOrder}
            disabled={placingOrder}
            id="single-click-order-btn"
            title="Single-click simulate an authorized store purchase"
          >
            <Zap size={14} />
            <span>{placingOrder ? 'Processing...' : '+ 1-Click Test Order'}</span>
          </button>

          {onNavigateTab && (
            <button
              className="dash-action-btn secondary"
              onClick={() => onNavigateTab('studio')}
              id="single-click-add-rule-btn"
              title="Add a dynamic pricing rule in Rule Studio"
            >
              <PlusCircle size={14} />
              <span>+ Add Rule</span>
            </button>
          )}

          <button
            className="dash-refresh-btn"
            onClick={loadAllAnalytics}
            disabled={loading}
            title="Refresh telemetry"
          >
            <RefreshCw size={15} className={loading ? 'dash-spin' : ''} />
            <span>{loading ? 'Refreshing...' : 'Refresh'}</span>
          </button>

          {onNavigateTab && (
            <button
              className="dash-store-btn"
              onClick={() => onNavigateTab('store')}
            >
              <ShoppingBag size={15} />
              <span>Go to Live Store</span>
            </button>
          )}
        </div>
      </div>

      {orderNotice && (
        <div style={{
          background: '#ecfdf5',
          border: '1px solid #10b981',
          color: '#065f46',
          borderRadius: '8px',
          padding: '0.6rem 1rem',
          margin: '0.5rem 0 1.25rem 0',
          fontSize: '0.86rem',
          fontWeight: 600,
          display: 'flex',
          alignItems: 'center',
          gap: '0.5rem'
        }}>
          <CheckCircle2 size={16} />
          <span>{orderNotice}</span>
        </div>
      )}

      {/* Sub-navigation tabs for direct section jumping */}
      <div className="dash-subnav">
        {[
          { id: 'all', label: 'All Sections', icon: BarChart3 },
          { id: 'sales', label: '1. Sales Overview', icon: TrendingUp },
          { id: 'pricing', label: '2. Pricing Performance', icon: BarChart3 },
          { id: 'analyst', label: '3. AI Business Analyst', icon: Bot },
          { id: 'whatif', label: '4. What-If Analysis', icon: GitCompare },
          { id: 'alerts', label: '5. Alerts & Opportunities', icon: Bell },
        ].map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              className={`dash-subnav-btn ${subTab === tab.id ? 'active' : ''}`}
              onClick={() => setSubTab(tab.id)}
            >
              <Icon size={15} />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* Main Dashboard Sections Container */}
      <div className="dash-content-area">
        {(subTab === 'all' || subTab === 'sales') && (
          <SalesOverviewSection
            salesData={salesData}
            timeRange={timeRange}
            setTimeRange={setTimeRange}
            loading={loading}
          />
        )}

        {(subTab === 'all' || subTab === 'pricing') && (
          <PricingPerformanceSection
            performanceData={performanceData}
            activeDomain={activeDomain}
            onNavigateTab={onNavigateTab}
          />
        )}

        {(subTab === 'all' || subTab === 'analyst') && (
          <AiAnalystSection
            activeDomain={activeDomain}
            onNavigateTab={onNavigateTab}
          />
        )}

        {(subTab === 'all' || subTab === 'whatif') && (
          <WhatIfSection
            activeDomain={activeDomain}
            activeDomainPack={activeDomainPack}
            onNavigateTab={onNavigateTab}
          />
        )}

        {(subTab === 'all' || subTab === 'alerts') && (
          <AlertsSection
            alerts={alerts}
            loading={loading}
            onNavigateTab={onNavigateTab}
          />
        )}
      </div>
    </div>
  );
}
