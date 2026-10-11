/**
 * HeroSection.jsx — Landing hero for the RateWeaver Store.
 *
 * Attractive, vibrant light-theme hero with dynamic pricing animations,
 * micro-interactions, stats cards, and real-time engine telemetry badges.
 */
import React from 'react';
import { 
  Sparkles, 
  ArrowRight, 
  Zap, 
  TrendingUp, 
  ShoppingBag, 
  ShieldCheck, 
  Percent,
  Activity
} from 'lucide-react';

export default function HeroSection({ onShopNow, productCount }) {
  return (
    <section className="s-hero" id="store-hero">
      {/* Background ambient lighting orbs for rich light-theme aesthetic */}
      <div className="s-hero-glow s-glow-1" aria-hidden="true" />
      <div className="s-hero-glow s-glow-2" aria-hidden="true" />
      <div className="s-hero-glow s-glow-3" aria-hidden="true" />
      <div className="s-hero-glow s-glow-4" aria-hidden="true" />

      {/* SVG Background Geometric Concentric Rings & Grid */}
      <div className="s-hero-grid-bg" aria-hidden="true">
        <svg className="s-hero-svg-rings" viewBox="0 0 1400 700" fill="none" xmlns="http://www.w3.org/2000/svg">
          <circle cx="700" cy="220" r="180" stroke="rgba(13, 148, 136, 0.12)" strokeWidth="1.5" strokeDasharray="4 6" />
          <circle cx="700" cy="220" r="300" stroke="rgba(2, 132, 199, 0.1)" strokeWidth="1.5" />
          <circle cx="700" cy="220" r="440" stroke="rgba(99, 102, 241, 0.08)" strokeWidth="1.5" strokeDasharray="8 8" />
          <circle cx="700" cy="220" r="580" stroke="rgba(16, 185, 129, 0.06)" strokeWidth="1.5" />
          <circle cx="700" cy="220" r="720" stroke="rgba(15, 118, 110, 0.04)" strokeWidth="1.5" strokeDasharray="6 8" />
        </svg>
      </div>

      <div className="s-hero-inner">
        {/* Animated Live Status Badge */}
        <div className="s-hero-badge" id="hero-engine-badge">
          <span className="s-live-pulse">
            <span className="s-pulse-dot" />
            <span className="s-pulse-ring" />
          </span>
          <span className="s-badge-text">⚡ RateWeaver Engine Active</span>
          <span className="s-badge-divider">·</span>
          <span className="s-badge-sub">Live Dynamic Pricing</span>
        </div>

        {/* Hero Title with Shimmer & Gradient Typography */}
        <h1 className="s-hero-title">
          <span className="s-title-line-1">Smart Prices,</span>
          <span className="s-title-line-2">
            Everyday <span className="s-gradient-text">Essentials.</span>
          </span>
        </h1>

        <p className="s-hero-desc">
          Real-time dynamic pricing for everyday essentials.
        </p>

        {/* CTA Buttons with Hover Micro-animations */}
        <div className="s-hero-actions">
          <button
            className="s-btn s-btn-primary s-btn-glow"
            onClick={onShopNow}
            id="hero-shop-now-btn"
          >
            <span>Explore Catalogue</span>
            <ArrowRight size={18} className="s-btn-icon-slide" />
          </button>
          <button
            className="s-btn s-btn-outline"
            onClick={onShopNow}
            id="hero-explore-offers-btn"
          >
            <Zap size={17} className="s-flash-deal-icon" />
            <span>Flash Deals</span>
          </button>
        </div>

        {/* Live Dynamic Pricing Signal Chips */}
        <div className="s-hero-signals-strip">
          <div className="s-signal-chip">
            <TrendingUp size={14} className="s-chip-icon s-chip-demand" />
            <span>Demand-Driven</span>
          </div>
          <div className="s-signal-chip">
            <Percent size={14} className="s-chip-icon s-chip-stock" />
            <span>Overstock Deals</span>
          </div>
          <div className="s-signal-chip">
            <Activity size={14} className="s-chip-icon s-chip-speed" />
            <span>&lt; 50ms Recalc</span>
          </div>
          <div className="s-signal-chip">
            <ShieldCheck size={14} className="s-chip-icon s-chip-audit" />
            <span>Deterministic</span>
          </div>
        </div>

        {/* Premium Glassmorphic Quick Stats */}
        <div className="s-hero-stats">
          <div className="s-stat-card">
            <div className="s-stat-icon-wrapper s-stat-icon-emerald">
              <ShoppingBag size={20} />
            </div>
            <div className="s-stat-content">
              <div className="s-stat-number">{productCount || 14}+</div>
              <div className="s-stat-label">Verified Products</div>
            </div>
          </div>

          <div className="s-stat-card">
            <div className="s-stat-icon-wrapper s-stat-icon-blue">
              <Sparkles size={20} />
            </div>
            <div className="s-stat-content">
              <div className="s-stat-number">5</div>
              <div className="s-stat-label">Daily Categories</div>
            </div>
          </div>

          <div className="s-stat-card">
            <div className="s-stat-icon-wrapper s-stat-icon-purple">
              <Zap size={20} />
            </div>
            <div className="s-stat-content">
              <div className="s-stat-number">Live</div>
              <div className="s-stat-label">Dynamic Quotes</div>
            </div>
          </div>

          <div className="s-stat-card">
            <div className="s-stat-icon-wrapper s-stat-icon-amber">
              <ShieldCheck size={20} />
            </div>
            <div className="s-stat-content">
              <div className="s-stat-number">₹ Best</div>
              <div className="s-stat-label">Real-Time Savings</div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

