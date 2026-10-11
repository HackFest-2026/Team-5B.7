# Monetize360 — Track 2 Evaluation Correctness Report

> Generated: 2026-10-11T05:22:27.274380+00:00 (Runner Mode: `api`)

---

## 🎯 Executive KPI Summary

| Metric | Target | Measured Result | Status |
| :--- | :--- | :--- | :--- |
| **Total Evaluation Cases** | $\ge 100$ | **140** cases across 4 domains | measured pass |
| **Expected Price Match Rate** | $100\%$ | **100.0%** (90 valid cases) | measured pass |
| **Invalid Input Rejection Rate** | $100\%$ | **100.0%** (50 invalid cases) | measured pass |
| **Overall Dataset Accuracy** | $100\%$ | **100.0%** | measured pass |
| **Determinism (5x repeats)** | $100\%$ | **100.0%** (identical SHA-256 fingerprints) | measured pass |
| **Explainability / Trace Completeness** | $100\%$ | **100.0%** (auditable timeline steps) | measured pass |
| **Constraint Violations** | $0$ | **0** violations | measured pass |
| **Rule-Conflict Precision** | $>95\%$ | **95.58%** | measured pass |
| **Rule-Conflict Recall** | $>95\%$ | **100.0%** | measured pass |
| **Rule-Conflict F1 Score** | $>95\%$ | **97.74%** | measured pass |

---

## 🔬 Dataset Case Breakdown

- **Total Cases Evaluated:** 140
  - Valid Pricing Cases: 90
  - Boundary & Constraint Cases: 35
  - Priority & Stacking Conflict Cases: 20
  - Invalid Input & Guardrail Rejection Cases: 50
- **Domains Covered:**
  - 🏨 Hospitality (Hotel Room Nights)
  - 🛒 E-Commerce (Retail Product Listings)
  - 🏦 Banking (Personal, Auto, Home & Education Loans)
  - ⚡ EV Charging (Time-of-Use & Capacity Tariffs)

---

## 🛡️ Constraint & Discrepancy Investigation

### Banking Floor Guardrail Enforcement
In banking, interest rate discounts (credit tier $-2.5\%$, large loan $-0.5\%$, premium customer $-1.0\%$) can sum to rates below the statutory minimum. The evaluation verified that the hard constraint `C-REGULATORY-FLOOR` ($6.50\%$) is strictly enforced by the engine without leaking sub-floor rates.

### E-Commerce Post-Rounding MRP Ceiling
In retail pricing, step rounding to the nearest ₹1 after demand surges can theoretically elevate a price above the product's Maximum Retail Price (MRP). The evaluation verified that post-rounding constraint checks re-clamp prices to $price \le MRP$, preventing statutory consumer overcharges.

---

## 📋 Mismatches & Discrepancies Found

**Total Mismatches:** 0

✅ **Zero mismatches found.** All 140 synthetic cases matched expected prices, rule firing sequences, error handling, and guardrail constraints.
