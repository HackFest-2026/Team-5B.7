# Monetize360 / RateWeaver — Audited KPI Scorecard

> **Audit Timestamp:** 2026-10-11 07:13 UTC  
> **Evaluation Mode:** Track 2 — Evidence, Correctness & Benchmarks  
> **Status Taxonomy:** `measured pass` | `measured fail` | `partial` | `not measured` | `blocked`

---

## 🏛️ Executive KPI Evidence Matrix

Every KPI status is backed by automated reproducible measurements. Per audit constraints, unmeasured capabilities are strictly forbidden from being labelled as passed.

| KPI Dimension | Target / Specification | Measured Evidence | Audited Status |
| :--- | :--- | :--- | :--- |
| **Domain-Agnostic Engine** | Zero core code modification across 4 domains | 4 domains loaded (`packs/*.json`); `git diff engine/` is clean | **measured pass** |
| **Pricing Correctness** | 100% match on golden test cases & synthetic corpus | 320 pytest tests pass; 140 synthetic cases evaluated (100.0% exact match) | **measured pass** |
| **Constraint Enforcement** | Zero breaches of floors, ceilings, or regulatory caps | 0 constraint violations detected across 140 boundary & ordinary cases | **measured pass** |
| **Determinism** | Bit-identical outputs across repeated executions | 100.0% determinism across 5x corpus iterations + 1,000 run fingerprint test | **measured pass** |
| **Explainability & Trace** | 100% of price calculations include complete audit trace | 100.0% trace completeness with full inputs, rules applied, and intermediate steps | **measured pass** |
| **Rule Conflict Detection** | Identify priority overlaps and contradictory rules | C1–C7 schema validations active; 95.58% precision / 100.0% recall on conflict corpus | **measured pass** |
| **Calculation Flexibility** | Support multiply, add, subtract, set, lookup, formula | Tested across all 4 production packs without engine extensions | **measured pass** |
| **Engine Micro-Benchmark** | In-memory evaluation throughput > 2,000 RPS | Measured peak: **5369.5 RPS**; p95 latency: **0.2478 ms** | **measured pass** |
| **API HTTP Benchmark** | Concurrent FastAPI `/v1/price` throughput with 0% errors | Measured peak: **54.6 RPS**; p95 latency: **98.2942 ms** (concurrency=4, 0% error) | **measured pass** |
| **Studio Rule Configuration UX** | Interactive visual pack builder & real-time simulation | Visual schema APIs verified; browser UI manual interaction not automated in CI | **partial** |
| **AI Copilot Pack Generation** | NL description $\rightarrow$ valid domain pack draft | `/v1/copilot/generate` operational & schema-valid; domain quality requires human review | **partial** |
| **Live Predictive Revenue Lift** | Measured conversion / margin improvement | Synthetic data tests policy correctness; empirical lift requires production A/B tests | **not measured** |

---

## 🧪 Synthetic Evaluation Corpus Audit (`docs/evidence/correctness_report.md`)

- **Dataset File:** `data/synthetic_evaluation_corpus.json` (Version `1.0.0`, Synthetic: `true`)
- **Total Test Cases:** **140** distinct labelled cases
- **Covered Domains:** Hospitality (35), E-Commerce (40), Banking (35), EV Charging (30)
- **Scenario Breakdown:** Ordinary (35), Boundary (35), Rule Priority Conflict (20), Invalid Input (50)
- **Exact Expected Price Match Rate:** **100.0%** (90 / 90 valid cases)
- **Invalid Input Rejection Rate:** **100.0%** (50 / 50)
- **Execution Determinism (5x repeats):** **100.0%**
- **Explainability Trace Completeness:** **100.0%**
- **Constraint Violations:** **0**
- **Conflict Detection F1 Score:** **97.74%**

---

## ⚡ Performance Benchmark Details

### 1. In-Memory Engine Micro-Benchmark (`docs/evidence/benchmark.json`)
Warm-up: 50 iterations | Measurement: 3,000 iterations per domain

| Domain Pack | Latency (p50) | Latency (p95) | Latency (p99) | Engine RPS |
| :--- | :--- | :--- | :--- | :--- |
| `hospitality` | 0.2079 ms | 0.3577 ms | 0.5848 ms | **4,261.0** |
| `ecommerce` | 0.2861 ms | 0.4661 ms | 0.6521 ms | **3,116.0** |
| `banking` | 0.1747 ms | 0.2478 ms | 0.3869 ms | **5,369.5** |
| `ev_charging` | 0.1668 ms | 0.3563 ms | 0.9907 ms | **4,785.1** |
| `airline` | 0.2383 ms | 0.4321 ms | 0.5757 ms | **3,778.5** |

### 2. FastAPI HTTP API Benchmark (`docs/evidence/api_benchmark.json`)
Endpoint: `/v1/price` | Concurrency: 4 workers | Requests: 500 per domain

| Domain Pack | Concurrency | Latency (p50) | Latency (p95) | Latency (p99) | API RPS | Error Rate |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `hospitality` | 4 | 77.7979 ms | 108.7789 ms | 121.5762 ms | **50.5** | 0.0% |
| `ecommerce` | 4 | 78.1784 ms | 113.4161 ms | 128.9127 ms | **49.9** | 0.0% |
| `banking` | 4 | 71.6259 ms | 107.1583 ms | 142.9908 ms | **53.9** | 0.0% |
| `ev_charging` | 4 | 72.1202 ms | 98.2942 ms | 111.8033 ms | **54.6** | 0.0% |
| `airline` | 4 | 74.7625 ms | 106.249 ms | 135.0957 ms | **53.1** | 0.0% |

---

## 🛡️ Pytest Test Suite Verification

```
........................................................................ [ 22%]
........................................................................ [ 45%]
........................................................................ [ 67%]
........................................................................ [ 90%]
................................                                         [100%]
============================== warnings summary ===============================
.venv\Lib\site-packages\starlette\testclient.py:40
  D:\Project\hackfest\monetize360\.venv\Lib\site-packages\starlette\testclient.py:40: DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
    _PortalFactoryType = typing.Callable[[], typing.ContextManager[anyio.abc.BlockingPortal]]

api\config.py:47
  D:\Project\hackfest\monetize360\api\config.py:47: UserWarning: [security] API_KEY is not set. Mutating endpoints (draft/publish/rollback) are unprotected. Set API_KEY in your environment for production use.
    warnings.warn(

.venv\Lib\site-packages\fastapi\routing.py:233: 50 warnings
  D:\Project\hackfest\monetize360\.venv\Lib\site-packages\fastapi\
```

---

## 🔬 Scientific Limitations & Verification Notes

1. **Synthetic Data Disclosure:** All evaluation cases are synthesized to systematically stress boundary invariants, rule collisions, and type validations. They do not simulate non-stationary consumer shopping behavior.
2. **Deterministic Guarantee:** Every price response includes an immutable execution trace. Fingerprints are calculated cryptographically using input signals and pack versioning.
3. **Guardrail Invariants:** Floors and ceilings are checked both pre-rounding and post-rounding to guarantee that rounding steps never push prices beyond approved policy bounds.
