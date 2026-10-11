# Monetize360 — Universal Dynamic Pricing Engine

> **Thesis:** One deterministic pricing engine can support multiple industries through configuration (Domain Packs), without domain-specific rewrites or custom logic.

---

## 🌟 Core Features

- **Domain-Agnostic Engine:** Evaluates Base Formulas, Multi-Stage Rules, Priority Ordering, Lookup Tables, Rate Limits, and Safety Floor/Ceiling Guardrails.
- **100% Deterministic & Auditable:** Every evaluation produces a cryptographic SHA-256 fingerprint hash and a step-by-step trace timeline.
- **Static Guardrail Validation:** Conflict engine checks for signal errors, overlapping priority conditions, missing constraints, and disallowed formula math (Errors C1–C7).
- **Five Production Domain Packs:**
  1. 🏨 **Hospitality:** Dynamic hotel room pricing (occupancy surge, lead-time advance booking, seasonal multipliers, loyalty discounts).
  2. 🛒 **E-commerce:** Dynamic retail product pricing (MRP base, inventory markdown, demand score surge, flash sales, bulk tiers).
  3. 🏦 **Banking:** Personal loan interest rate calculation (prime rate anchor, credit score adjustment, LTI risk penalty).
  4. ⚡ **EV Charging:** kWh tariff pricing (peak grid load surcharge, battery SOC urgency, renewable discount).
  5. ✈️ **Airline:** Synthetic fare-class pricing (route distance, demand/seat pressure, cabin tier, baggage fees).
- **AI Copilot:** Natural language prompt to domain pack JSON synthesis with live validation & 1-click publishing.
- **Full React Studio UI:** Interactive signal sliders, price sensitivity sweep charts, visual rule builder, guardrail inspector, and KPI scorecard.

---

## 🚀 Quick Start Guide

### 1. Backend Setup & Server (Windows PowerShell)

Prerequisites: Python 3.10 or newer and Node.js 18 or newer.

From the repository root:

```powershell
# Create and activate a virtual environment
py -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install the pinned backend and test dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# Verify the backend imports
python -c "import api.main; print('Backend import: OK')"

# Run the FastAPI server (starts at http://localhost:8000)
python -m uvicorn api.main:app --reload --port 8000
```

### 2. Frontend Setup (React / Vite)

Open a second PowerShell terminal in the repository root:

```powershell
Set-Location .\web

# Install dependencies and create/update package-lock.json
npm install

# Start Vite development server (starts at http://localhost:5173)
npm run dev
```

For a production build, run `npm run build` from `web`.

---

## 💻 Command Line Interface (CLI)

Evaluate prices directly from the terminal without starting a server:

```bash
# 1. Price Evaluation (E-commerce Domain)
python cli.py price --pack packs/ecommerce.json --context '{"category":"electronics","mrp":1000,"inventory_pct":15,"demand_score":85}'

# 2. Price Evaluation (Hospitality Domain)
python cli.py price --pack packs/hospitality.json --context '{"base_price":200,"occupancy_pct":92,"season":"peak"}'

# 3. Price Evaluation (Airline Domain)
python cli.py price --pack packs/airline.json --context '{"cabin_class":"economy","base_fare":150,"distance_km":1200,"demand_index":50,"available_seats":200,"total_seats":300,"days_to_departure":10}'

# 4. Static Pack Validation
python cli.py validate --pack packs/ecommerce.json

# 5. Run Benchmarks
python cli.py benchmark
```

---

## 🧪 Test Suite Execution

Run the complete test suite covering golden tests, property-based tests, static validation tests, and determinism tests:

```bash
# Run all tests
python -m pytest tests/ -v

# Run domain-specific golden tests
python -m pytest tests/golden/ -v

# Run Hypothesis property-based tests
python -m pytest tests/property/ -v

# Run determinism verification (1,000 iterations per domain)
python -m pytest tests/unit/test_determinism.py -v
```

---

## 📊 Benchmarking & Scorecard Generation

Measure real evaluation throughput and generate the KPI scorecard evidence table:

```bash
# Run latency & throughput benchmark
python scripts/benchmark.py

# Generate Markdown KPI Scorecard table
python scripts/scorecard.py
```

---

## 🏛️ Project Architecture

```text
monetize360/
├── api/                  # FastAPI backend routes (domains, pricing, copilot)
│   ├── main.py
│   ├── models.py
│   ├── routes/
│   └── storage/
├── copilot/              # AI Copilot prompt-to-pack synthesizer
│   └── provider.py
├── engine/               # Universal Deterministic Engine Runtime
│   ├── evaluate/         # Condition matcher, formula evaluator, lookup tables
│   ├── fingerprint/      # SHA-256 determinism hasher
│   ├── runtime.py        # Main execution pipeline & step trace generator
│   ├── schema/           # Pydantic v2 domain pack schema definitions
│   └── validate/         # Static analyzer & conflict engine (C1-C7)
├── packs/                # Domain configuration JSON packs
│   ├── banking.json
│   ├── ecommerce.json
│   ├── ev_charging.json
│   ├── hospitality.json
│   └── airline.json
├── scripts/              # Benchmark, seed DB, and scorecard scripts
├── tests/                # Golden tests, property tests, determinism tests
├── web/                  # Premium React / Vite Web Application
└── cli.py                # Command Line Interface
```
