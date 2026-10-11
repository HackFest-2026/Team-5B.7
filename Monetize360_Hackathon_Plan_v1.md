# Monetize360 --- Hackathon Winning Execution Plan

## Problem 5B --- Universal Dynamic Pricing Engine

**Objective:** Build the smallest system that convincingly proves the
core thesis of Problem 5B:

> **One deterministic pricing engine can support multiple industries
> through configuration, not domain-specific rewrites.**

The project is judged on domain-agnostic architecture, pricing
correctness/determinism, configuration UX, explainability/auditability,
pricing-model flexibility, performance, AI value, and
presentation/documentation.

------------------------------------------------------------------------

# 1. Winning Strategy

## The thesis

Do **not** present Monetize360 as five pricing applications.

Present it as:

> **A universal pricing runtime with configurable domain packs.**

The architecture is:

``` text
                  BUSINESS INTENT
                        │
             ┌──────────┴──────────┐
             │                     │
        No-code Builder        AI Copilot
             │                     │
             └──────────┬──────────┘
                        ▼
                 DOMAIN PACK
                        │
                        ▼
                VALIDATION LAYER
                        │
             ┌──────────┴──────────┐
             │                     │
        Conflict Check        Test Generation
             │                     │
             └──────────┬──────────┘
                        ▼
               DETERMINISTIC ENGINE
                        │
             ┌──────────┼──────────┐
             ▼          ▼          ▼
          Price       Trace      Fingerprint
             │          │
             └────┬─────┘
                  ▼
          Simulation / What-if
```

The key proof:

``` text
Hotel Pack ──────┐
Ride Pack ───────┼──► SAME ENGINE
Banking Pack ────┘

New Domain ──────► NEW PACK ─────► SAME ENGINE
                                   NO ENGINE CODE CHANGE
```

That last line is the hero moment.

------------------------------------------------------------------------

# 2. Scope: What We Actually Build

## P0 --- Non-negotiable

Everything below must work before anything else is added.

### Core engine

-   Domain-pack JSON schema
-   Base price
-   Conditions
-   Rule priorities
-   Stages
-   Percentage/multiplier adjustment
-   Fixed adjustment
-   Tier/lookup adjustment
-   Formula adjustment
-   Floor
-   Ceiling
-   Rate/change constraint
-   Rounding
-   Deterministic evaluation
-   Full price trace
-   Deterministic fingerprint

### Domains

Three fully working domains:

1.  Hospitality
2.  Ride-hailing
3.  Banking

### Application

One React application with three functional areas:

1.  **Domain / Rule Builder**
2.  **Simulator**
3.  **Explain + Audit**

### API

Only implement what the UI and demo need:

``` text
GET  /v1/domains
GET  /v1/domains/{domain}
POST /v1/validate
POST /v1/publish
POST /v1/price
POST /v1/simulate
GET  /v1/audit/{domain}
```

### AI

Only one AI feature:

> **Natural language pricing intent → structured domain pack draft**

AI does not directly calculate or publish prices.

Flow:

``` text
Natural language
      ↓
LLM
      ↓
JSON domain pack
      ↓
Schema validation
      ↓
Engine validation
      ↓
Human review
      ↓
Publish
```

### Validation

Must demonstrate:

-   malformed configuration
-   overlapping/conflicting rules
-   missing constraints
-   invalid ranges
-   unsupported expressions
-   publish blocked when validation fails

### Simulation

Only:

-   single price
-   one-variable sweep
-   before/after comparison

### Evidence

-   golden tests
-   deterministic repeated-run test
-   conflict detection test
-   benchmark
-   AI evaluation
-   KPI scorecard

------------------------------------------------------------------------

# 3. P1 --- Only After P0 Is Stable

Implement in this exact order:

1.  Counterfactual explanation
2.  Fourth domain
3.  Version comparison
4.  Rollback
5.  Better charts
6.  Load-test dashboard

Nothing else.

------------------------------------------------------------------------

# 4. P2 --- Cut Unless Everything Is Finished

Do **not** start these before P0 is complete:

-   demand forecasting
-   anomaly detection
-   optimizer
-   reinforcement learning
-   WebSockets
-   real-time streaming dashboard
-   Postgres
-   Redis
-   Kubernetes
-   RBAC
-   API-key management
-   multilingual UI
-   sophisticated authentication
-   microservices
-   public cloud deployment
-   elaborate cryptographic audit chain
-   large Playwright suite
-   five production-quality domains

These are not the reason to choose Problem 5B.

------------------------------------------------------------------------

# 5. Why This Scope Wins

The official problem asks for:

-   multiple industries
-   configuration rather than hardcoded domain logic
-   simulation/testing
-   real-time pricing
-   explanation
-   visual no-code configuration
-   validation/conflict detection
-   approval/audit/rollback
-   optional AI assistance
-   measurable correctness, flexibility and performance

Our P0 directly maps to those requirements.

The project does **not** need to become a complete enterprise pricing
platform.

The judge needs to believe:

> "If this team had another month, the architecture could become a real
> platform."

That is much more valuable than seeing 20 half-finished features.

------------------------------------------------------------------------

# 6. Technology Stack

Keep it boring.

## Frontend

-   React
-   Vite
-   Tailwind CSS
-   Recharts

## Backend

-   Python
-   FastAPI
-   Pydantic

## Engine

Pure Python package.

No network calls.

No database dependency.

``` text
engine/
    schema/
    validate/
    compile/
    evaluate/
    trace/
    simulate/
```

## Storage

SQLite.

Use JSON columns/files where convenient.

Do not introduce Postgres unless SQLite becomes a genuine blocker.

## AI

One provider.

Use a stored fallback pack/template if the provider fails.

## Testing

-   pytest
-   Hypothesis
-   FastAPI TestClient
-   Locust or k6 if already available

## Deployment

Primary:

``` bash
docker compose up
```

Run locally.

Optional public mirror only if it already works.

------------------------------------------------------------------------

# 7. Repository Structure

``` text
monetize360/
├── README.md
├── docker-compose.yml
├── .env.example
│
├── engine/
│   ├── schema/
│   ├── validate/
│   ├── compile/
│   ├── evaluate/
│   ├── trace/
│   ├── simulate/
│   └── fingerprint/
│
├── api/
│   ├── main.py
│   ├── routes/
│   ├── services/
│   └── storage/
│
├── copilot/
│   ├── prompts/
│   ├── provider.py
│   ├── repair.py
│   └── evaluator.py
│
├── packs/
│   ├── hospitality.json
│   ├── ride_hailing.json
│   ├── banking.json
│   └── ev_charging.json
│
├── web/
│   └── ...
│
├── tests/
│   ├── unit/
│   ├── golden/
│   ├── property/
│   ├── api/
│   └── copilot/
│
├── docs/
│   ├── architecture.md
│   ├── decisions.md
│   ├── evidence/
│   └── demo-script.md
│
└── scripts/
    ├── seed.py
    ├── benchmark.py
    └── scorecard.py
```

------------------------------------------------------------------------

# 8. Domain-Pack Contract

The domain pack is the product.

A simplified pack:

``` json
{
  "pack_id": "hotel-rooms",
  "version": "1.0.0",

  "unit": {
    "kind": "currency",
    "code": "INR",
    "decimals": 0
  },

  "entity": {
    "name": "room_night",
    "attributes": [
      {
        "key": "room_type",
        "type": "enum",
        "values": ["standard", "deluxe", "suite"]
      }
    ]
  },

  "signals": [
    {
      "key": "occupancy_pct",
      "type": "number",
      "min": 0,
      "max": 100
    },
    {
      "key": "days_to_stay",
      "type": "integer",
      "min": 0,
      "max": 365
    },
    {
      "key": "loyalty_tier",
      "type": "enum",
      "values": ["none", "silver", "gold"]
    }
  ],

  "base": {
    "type": "table",
    "by": "room_type",
    "values": {
      "standard": 3200,
      "deluxe": 4500,
      "suite": 8000
    }
  },

  "stages": [
    {
      "id": "demand",
      "stacking": "first"
    },
    {
      "id": "customer",
      "stacking": "max_discount"
    }
  ],

  "rules": [
    {
      "id": "R-OCC-HIGH",
      "stage": "demand",
      "priority": 10,
      "when": {
        "all": [
          {
            "signal": "occupancy_pct",
            "op": "gte",
            "value": 85
          }
        ]
      },
      "then": {
        "op": "multiply",
        "value": 1.30
      }
    }
  ],

  "constraints": [
    {
      "id": "C-FLOOR",
      "type": "floor",
      "expr": "base * 0.70"
    },
    {
      "id": "C-CAP",
      "type": "ceiling",
      "expr": "base * 2.00"
    }
  ],

  "rounding": {
    "mode": "nearest",
    "step": 10
  }
}
```

The engine knows nothing about hotels.

It only knows:

``` text
signals
base
rules
stages
actions
constraints
rounding
```

That is the central architectural proof.

------------------------------------------------------------------------

# 9. Engine Execution Pipeline

Implement exactly this:

``` text
INPUT
  │
  ▼
Validate request
  │
  ▼
Load published pack
  │
  ▼
Resolve base price
  │
  ▼
Evaluate stages
  │
  ├── conditions
  ├── priorities
  └── stacking
  │
  ▼
Apply constraints
  │
  ▼
Round
  │
  ▼
Generate trace
  │
  ▼
Generate fingerprint
  │
  ▼
PRICE RESPONSE
```

Every step must be deterministic.

------------------------------------------------------------------------

# 10. Rule Primitives

Do not build a programming language.

Support only:

## Conditions

``` text
eq
neq
gt
gte
lt
lte
in
between
and
or
not
```

## Actions

``` text
multiply
add
subtract
set
lookup
formula
```

## Constraints

``` text
floor
ceiling
max_change_pct
```

## Formula functions

Only:

``` text
min()
max()
clamp()
```

Add date helpers only if a domain genuinely needs them.

If a requirement cannot be expressed by these primitives, it goes into
an `unsupported` response rather than becoming a new primitive.

------------------------------------------------------------------------

# 11. Three Core Domains

## Domain 1 --- Hospitality

Signals:

``` text
room_type
occupancy_pct
days_to_stay
stay_date
loyalty_tier
```

Demonstrates:

-   threshold rules
-   percentage adjustments
-   customer discount
-   stacking
-   floor/ceiling
-   rounding

------------------------------------------------------------------------

## Domain 2 --- Ride-Hailing

Signals:

``` text
base_fare
demand
supply
distance_km
time_of_day
weather_level
```

Demonstrates:

-   formula
-   continuous pricing
-   surge
-   maximum surge cap
-   additive + multiplicative rules

Example:

``` text
surge =
clamp(
    demand / max(supply, 1),
    1.0,
    2.5
)
```

------------------------------------------------------------------------

## Domain 3 --- Banking

Signals:

``` text
credit_score
risk_tier
loan_amount
loan_term
customer_segment
```

Demonstrates:

-   lookup tables
-   risk-based pricing
-   regulatory/business cap
-   different adjustment mechanisms

This third domain is important because it prevents judges from thinking:

> "This is just e-commerce/hotel pricing with renamed variables."

------------------------------------------------------------------------

# 12. Live New Domain

Prepare one additional domain:

## EV Charging

Signals:

``` text
charger_type
time_of_day
grid_load
membership
session_duration
```

Example request:

> Price EV charging per kWh. Base ₹18. Peak hours add 25%. Fast chargers
> add 40%. Members receive 10% off. Floor ₹12. Ceiling ₹40.

The AI generates the pack.

The engine remains untouched.

The judge should see:

``` text
Before:
engine supports 3 domains

After:
EV charging added

git diff engine/
→ 0 changes
```

That is the single strongest technical proof in the demo.

------------------------------------------------------------------------

# 13. UI Design

Do not build six pages.

Build three.

## Screen 1 --- Studio

``` text
┌─────────────────────────────────────────────┐
│ Monetize360                                 │
├──────────────┬──────────────────────────────┤
│ Domains      │ Hospitality                   │
│              │                               │
│ ● Hotel      │ Signals                       │
│ ○ Ride       │ occupancy_pct                 │
│ ○ Banking    │ loyalty_tier                  │
│ ○ EV         │                               │
│              │ Rules                         │
│ + New Domain │ [Occupancy >= 85] [+30%]     │
│              │ [Gold Member] [-8%]          │
│              │                               │
│              │ [Validate] [Publish]          │
└──────────────┴──────────────────────────────┘
```

## Screen 2 --- Simulator

``` text
Input
──────────────
Room: Deluxe
Occupancy: 90%
Loyalty: Gold

          ↓

BASE       ₹4,500
WEEKEND    +15%
DEMAND     +30%
GOLD       -8%
CAP/FLOOR  PASS
ROUNDING   ₹6,190

FINAL      ₹6,190
```

Add one sweep chart.

## Screen 3 --- Explain

``` text
Why was the price ₹6,190?

₹4,500
   ↓
+15% weekend
   ↓
+30% occupancy
   ↓
-8% gold customer
   ↓
floor/cap check
   ↓
nearest ₹10

₹6,190
```

Below:

``` text
Pack: hotel-rooms v1.2
Fingerprint: 9f8a...
Published: 14:31
Approved: demo-user
```

------------------------------------------------------------------------

# 14. AI Copilot

The copilot is intentionally constrained.

## Input

``` text
Price EV charging per kWh.
Base ₹18.
Peak hours add 25%.
Fast chargers add 40%.
Members get 10% off.
Never below ₹12 or above ₹40.
```

## Output

A JSON pack.

Then:

``` text
Schema validation
        ↓
Semantic validation
        ↓
Conflict detection
        ↓
Generated test cases
        ↓
Human approval
```

The AI cannot:

-   publish
-   directly set a price
-   bypass validation
-   invent unsupported primitives

This gives you a strong answer to:

> "What happens if the AI is wrong?"

Answer:

> "The AI proposes configuration. It never becomes the pricing
> authority. The deterministic engine, validation layer and human
> approval gate decide what is allowed."

------------------------------------------------------------------------

# 15. Explainability

Every price must produce a trace.

Example:

``` json
{
  "price": 6190,
  "trace": [
    {
      "step": "base",
      "before": null,
      "after": 4500
    },
    {
      "step": "weekend",
      "before": 4500,
      "after": 5175
    },
    {
      "step": "high_occupancy",
      "before": 5175,
      "after": 6727.5
    },
    {
      "step": "gold_member",
      "before": 6727.5,
      "after": 6189.3
    },
    {
      "step": "constraints",
      "before": 6189.3,
      "after": 6189.3
    },
    {
      "step": "rounding",
      "before": 6189.3,
      "after": 6190
    }
  ]
}
```

This is not an LLM explanation.

It is the actual execution trace.

That makes it trustworthy.

------------------------------------------------------------------------

# 16. Counterfactuals

If time permits, implement:

``` text
Current:
Gold member → ₹6,190

Without gold:
₹6,730

If occupancy < 85:
₹5,330
```

This is extremely high demo value because it makes the engine feel
intelligent without requiring another ML system.

------------------------------------------------------------------------

# 17. Conflict Detection

Minimum useful implementation:

### Conflict

Two rules:

``` text
R1:
occupancy >= 70 → +10%

R2:
occupancy >= 80 → +30%
```

If both are in the same stage and their stacking semantics are
ambiguous:

``` text
⚠ Potential overlap
Rules: R1, R2
Region: occupancy >= 80
Resolution: explicit stacking required
```

### Validation rules

At minimum:

``` text
C1 — unknown signal
C2 — invalid operator
C3 — invalid value range
C4 — invalid action
C5 — overlapping rules
C6 — missing ceiling/floor warning
C7 — unsupported formula
```

A failed validation must block publish.

------------------------------------------------------------------------

# 18. Determinism

Use Decimal for monetary calculations.

Do not use binary floating-point arithmetic for final price computation.

Canonicalize:

``` text
pack
input
rule order
trace
final price
```

Then:

``` text
SHA-256(canonical_result)
```

Do not include:

-   latency
-   random IDs
-   generated timestamps
-   request IDs

in the fingerprint.

Test:

``` text
same input
same pack
1000 executions
→ identical fingerprint
```

------------------------------------------------------------------------

# 19. Testing Strategy

Do not chase enormous test counts.

Test the important things.

## Golden tests

10--15 carefully designed cases per domain.

Focus on:

-   boundaries
-   thresholds
-   stacking
-   discounts
-   constraints
-   rounding
-   missing signals
-   conflicts

Target:

``` text
3 domains × 10–15 cases
= 30–45 cases
```

## Property tests

Test:

``` text
floor <= price <= ceiling
```

and:

``` text
same input + same pack
→ same output
```

and:

``` text
rule-file ordering
does not change result
```

when the rules are semantically independent.

## Determinism

Run repeated requests in separate processes.

## Copilot evaluation

Prepare 10--15 prompts.

Measure:

``` text
schema-valid %
behavior-match %
median repair attempts
```

Do not claim "AI accuracy" without defining what passed.

------------------------------------------------------------------------

# 20. Performance Benchmark

Do not invent an arbitrary requirement.

Measure and report:

``` text
Machine:
CPU:
RAM:
Number of rules:
Number of concurrent clients:

p50:
p95:
p99:
requests/sec:
```

The exact measured number matters less than being honest and
reproducible.

Example presentation:

> "On a 4-core laptop with a 20-rule pack, our deterministic engine
> achieved X req/s at Y ms p95."

------------------------------------------------------------------------

# 21. KPI Scorecard

Create this automatically before the demo.

  -----------------------------------------------------------------------
  Official KPI            What we show            Evidence
  ----------------------- ----------------------- -----------------------
  Domain-agnostic         3 domains + live EV     Engine git diff
  architecture            domain                  

  Pricing correctness     Golden cases            CI report

  Determinism             Repeated fingerprints   Determinism test

  Configuration UX        Rule creation stopwatch Recorded measurement

  Explainability          100% traced prices      API/test evidence

  Conflict detection      Injected conflicts      Validation report

  Flexibility             Primitive coverage      Feature matrix

  Performance             p50/p95/p99/RPS         Benchmark

  AI value                NL → valid pack         Copilot evaluation

  Presentation            Architecture + research README/slides
  -----------------------------------------------------------------------

The scorecard should show **measured values**, not adjectives.

------------------------------------------------------------------------

# 22. Team Structure

## Team of 4

### Person 1 --- Engine Lead

Owns:

-   schema
-   evaluator
-   stacking
-   constraints
-   trace
-   fingerprint

### Person 2 --- Backend

Owns:

-   FastAPI
-   storage
-   validation API
-   publish
-   audit
-   Docker

### Person 3 --- Frontend

Owns:

-   Studio
-   Simulator
-   Explain screen
-   charts

### Person 4 --- AI + QA + Demo

Owns:

-   copilot
-   evaluation
-   golden tests
-   scorecard
-   documentation
-   demo

------------------------------------------------------------------------

## Team of 5

Split AI/QA into separate people.

No one should own "everything frontend".

------------------------------------------------------------------------

# 23. Work Rules

## Rule 1 --- Main always works

No giant branches.

Small PRs.

## Rule 2 --- Freeze contracts immediately

Freeze:

-   domain pack schema
-   `/price` request
-   `/price` response
-   trace structure

Changing these late will destroy the schedule.

## Rule 3 --- UI starts with mock data

Frontend does not wait for backend.

## Rule 4 --- Engine has no network code

It must run independently.

## Rule 5 --- Expected values are independently calculated

Never generate golden expected prices from the same engine being tested.

## Rule 6 --- No feature without a KPI

If a feature cannot be connected to a judge-visible KPI, it is probably
cut.

## Rule 7 --- Demo freeze

Three hours before presentation:

``` text
NO NEW FEATURES
```

Only:

-   bug fixes
-   demo data
-   presentation
-   rehearsal

------------------------------------------------------------------------

# 24. Execution Timeline

Assume approximately 28 team-hours of real parallel work.

## Hour 0--1 --- Contract Freeze

Everyone does this together.

Deliver:

-   repository
-   folder structure
-   pack schema
-   API request/response
-   trace format
-   mock `/price`
-   one example pack

**STOP CONDITION:**

Everyone can run the project.

------------------------------------------------------------------------

## Hour 1--5 --- Engine

Engine person builds:

``` text
base
→ condition
→ stage
→ action
→ constraint
→ rounding
→ trace
→ fingerprint
```

Backend creates pack loading.

Frontend creates Studio skeleton.

AI person creates prompt/schema pipeline.

------------------------------------------------------------------------

## Hour 5 --- First Milestone

You must have:

``` text
POST /price
hotel pack
correct result
trace
```

If this does not work, **stop everything else.**

Do not start ML.

Do not polish UI.

Do not create another domain.

Fix the engine.

------------------------------------------------------------------------

## Hour 5--7 --- Domain Expansion

Add:

-   ride-hailing
-   banking

Do not build them through special-case code.

Only create packs.

This is where you prove the architecture.

------------------------------------------------------------------------

## Hour 7--10 --- API + Studio

Connect:

``` text
UI
 ↓
API
 ↓
Engine
```

Implement:

-   create/edit rules
-   validate
-   publish
-   price

------------------------------------------------------------------------

## Hour 10--13 --- Simulator + Explain

Build:

-   single simulation
-   sweep
-   waterfall
-   counterfactual if easy

At this point the product should already look impressive.

------------------------------------------------------------------------

## Hour 13--15 --- Validation

Implement:

-   schema validation
-   conflicts
-   publish gate
-   audit entries

------------------------------------------------------------------------

## Hour 15--17 --- AI Copilot

Connect:

``` text
prompt
 ↓
LLM
 ↓
JSON
 ↓
schema
 ↓
validation
 ↓
draft
```

Do not spend more than two hours debugging prompt perfection.

Have a fallback.

------------------------------------------------------------------------

## Hour 17--20 --- Testing

Write:

-   golden cases
-   property tests
-   determinism test
-   conflict tests
-   formula safety test

------------------------------------------------------------------------

## Hour 20--22 --- Live New Domain

Build EV charging pack.

Test:

``` text
engine/
git diff
```

It should show no engine changes.

Then run:

``` text
prompt
→ pack
→ validate
→ publish
→ price
→ explain
```

------------------------------------------------------------------------

## Hour 22--24 --- Benchmark + Scorecard

Run:

-   golden tests
-   determinism
-   conflict evaluation
-   benchmark
-   copilot evaluation

Generate the KPI table.

------------------------------------------------------------------------

## Hour 24--25 --- Demo Hardening

Prepare:

-   seed data
-   reserve prompts
-   backup pack
-   local Docker
-   backup laptop
-   recorded demo

------------------------------------------------------------------------

## Hour 25--28 --- Rehearsal

Run the full demo at least three times.

One rehearsal must include someone deliberately trying to break it.

------------------------------------------------------------------------

# 25. The 6-Minute Demo

## 0:00--0:30 --- Hook

Say:

> "Today, every industry tends to build pricing logic independently.
> Monetize360 separates the pricing engine from the industry
> configuration."

Show:

``` text
Hotel
Ride
Banking
```

Then:

> "Three industries. One engine."

------------------------------------------------------------------------

## 0:30--1:30 --- Real Prices

Run three requests.

Show:

``` text
Hotel       ₹6,190
Ride        ₹412
Loan        9.3%
```

Immediately open the hotel explanation.

------------------------------------------------------------------------

## 1:30--2:15 --- Explainability

Show:

``` text
Base
 ↓
Demand
 ↓
Customer
 ↓
Constraint
 ↓
Rounding
 ↓
Final price
```

Say:

> "This is not a generated explanation. This is the execution trace of
> the pricing engine."

That sentence is important.

------------------------------------------------------------------------

## 2:15--4:00 --- Hero Moment

Say:

> "Now let's add a completely new industry."

Use EV charging.

Enter the natural-language request.

Copilot produces a pack.

Validation catches an issue.

Fix it.

Publish.

Price a transaction.

Open explanation.

Then show:

``` text
engine/ git diff
```

No changes.

That is the money shot.

------------------------------------------------------------------------

## 4:00--4:45 --- Governance

Show:

``` text
Draft
 ↓
Validation
 ↓
Approval
 ↓
Published
```

Show audit.

If rollback is implemented, show it.

If not, don't fake it.

------------------------------------------------------------------------

## 4:45--5:30 --- Evidence

Show KPI scorecard.

Say actual numbers.

Not:

> "Highly scalable."

Say:

> "Our benchmark measured X requests/sec at Y ms p95."

------------------------------------------------------------------------

## 5:30--6:00 --- Close

Three statements:

> **One engine.**

> **Any domain through configuration.**

> **Every price explainable and reproducible.**

Stop.

Do not keep talking.

------------------------------------------------------------------------

# 26. Demo Fallbacks

## LLM fails

Use prepared EV pack.

Say:

> "The AI layer is optional. The pricing engine remains fully
> operational."

That actually strengthens the architecture story.

## Internet fails

Run locally.

## Hosted site fails

Do not care.

## Judge gives an impossible domain

Use one of the prepared supported templates.

## UI breaks

Call the API directly.

## API breaks

Use the recorded backup.

------------------------------------------------------------------------

# 27. Questions Judges Are Likely to Ask

## "Why not use ML to determine the price?"

> "The core price decision must be deterministic, bounded and
> explainable. ML can provide signals such as demand forecasts, but the
> pricing engine remains the final authority."

## "What makes this different from a rules engine?"

> "Pricing primitives, staged stacking, monetary constraints,
> simulation, versioned governance and execution-level price
> explanations are first-class parts of the system."

## "How do you add another industry?"

> "Create a domain pack. The engine does not change."

## "What if two rules conflict?"

> "Validation identifies overlapping rules before publish, and the pack
> explicitly defines precedence and stacking semantics."

## "What did AI actually do?"

> "It translates business pricing intent into a structured configuration
> draft. It cannot publish or bypass validation."

## "Can you trust AI-generated pricing?"

> "We don't trust it with the final decision. The AI generates
> configuration; schema validation, deterministic evaluation and human
> approval control the actual pricing."

## "Are your revenue improvements real?"

> "No. Revenue impact is simulated. We label it as simulation rather
> than claiming production gains."

## "How fast is it?"

Give the benchmark.

Do not invent the number.

------------------------------------------------------------------------

# 28. The Three Things Judges Must Remember

If the judges remember only three things, make them these:

### 1. Domain agnostic

``` text
3 industries
+
live new domain
+
0 engine changes
```

### 2. Deterministic

``` text
same input
+
same configuration
=
same price
```

### 3. Explainable

``` text
every price
→
every rule
→
every adjustment
→
final price
```

Everything else is supporting evidence.

------------------------------------------------------------------------

# 29. Cut-Line Rules

If you are behind schedule:

## If engine is late

Cut:

-   AI
-   charts
-   fourth domain
-   fancy UI

Do not cut engine.

## If UI is late

Make API demo the primary demo.

Do not cut engine.

## If AI is late

Use a prepared pack.

Do not cut deterministic pricing.

## If testing is late

Cut feature work.

Do not cut tests for the core engine.

## If three hours remain

No new features.

Only:

``` text
bug fixes
demo data
benchmark
scorecard
rehearsal
```

------------------------------------------------------------------------

# 30. Definition of Done

The project is DONE when:

-   [ ] Three domains work through the same engine
-   [ ] No domain-specific branches exist in engine code
-   [ ] Domain packs define signals/rules/constraints
-   [ ] `/price` works
-   [ ] Price trace works
-   [ ] Fingerprint works
-   [ ] Validation works
-   [ ] Conflict detection works
-   [ ] Publish gate works
-   [ ] Basic no-code builder works
-   [ ] Simulator works
-   [ ] AI can produce a valid pack
-   [ ] EV charging can be added without engine changes
-   [ ] Golden tests pass
-   [ ] Determinism test passes
-   [ ] Benchmark has measured values
-   [ ] KPI scorecard is generated
-   [ ] `docker compose up` works
-   [ ] Demo has been rehearsed three times

Everything else is optional.

------------------------------------------------------------------------

# 31. Final Architecture

``` text
                         ┌───────────────────┐
                         │   React Frontend  │
                         │                   │
                         │ Studio            │
                         │ Simulator         │
                         │ Explain           │
                         └─────────┬─────────┘
                                   │
                              REST / JSON
                                   │
                         ┌─────────▼─────────┐
                         │      FastAPI      │
                         │                   │
                         │ Pricing API       │
                         │ Validation        │
                         │ Publishing        │
                         │ Audit             │
                         └─────────┬─────────┘
                                   │
                     ┌─────────────▼─────────────┐
                     │    Deterministic Engine   │
                     │                           │
                     │ Conditions                │
                     │ Rules                     │
                     │ Stages                    │
                     │ Actions                   │
                     │ Constraints               │
                     │ Rounding                  │
                     │ Trace                     │
                     │ Fingerprint               │
                     └─────────────┬─────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
              ▼                    ▼                    ▼
         Hotel Pack          Ride Pack            Bank Pack
              │
              │
              └──────────────┐
                             ▼
                        EV Pack
                     added live by AI

              AI NEVER BYPASSES THE ENGINE
```

------------------------------------------------------------------------

# 32. The Actual Winning Narrative

Do not pitch this as:

> "We built an AI-powered dynamic pricing platform with ML, forecasting,
> optimization and anomaly detection."

That sounds like a feature dump.

Pitch this:

> **"We built a universal pricing runtime. The engine is
> domain-independent; industries are represented as configuration packs.
> Businesses can define pricing rules visually or through natural
> language, validate them before publication, simulate outcomes, and
> inspect the exact chain of decisions behind every price. We prove the
> architecture by adding a new industry live without modifying the
> engine."**

That is a much stronger product story.

------------------------------------------------------------------------

# 33. Final Priority Stack

When there is a conflict between tasks, use this order:

``` text
1. Deterministic engine
2. Domain-pack architecture
3. Three working domains
4. Price trace / explainability
5. Validation + conflicts
6. No-code configuration
7. Simulation
8. Live new-domain demo
9. AI copilot
10. Tests + benchmark
11. Governance
12. UI polish
13. Everything else
```

If you finish #1--#10 exceptionally well, **stop building**.

Polish.

Test.

Rehearse.

The biggest mistake at this stage would be continuing to add features
after you have a winning core.
