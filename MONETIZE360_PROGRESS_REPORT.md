# Monetize360 MVP Recovery Progress Report

Date: 2026-10-10

## Project Overview

Monetize360 is a configuration-driven dynamic pricing engine. The core thesis is that one deterministic pricing runtime can support multiple industries through JSON domain packs instead of domain-specific engine rewrites.

The repository contains:

- A FastAPI backend in `api/`.
- A deterministic pricing runtime in `engine/`.
- Four domain packs in `packs/`: hospitality, ecommerce, banking, and EV charging.
- A React/Vite frontend in `web/`.
- A Copilot provider that generates draft domain packs.
- SQLite-backed pack publishing and audit storage.
- Golden, property-based, validation, determinism, and CLI tests in `tests/`.

The current recovery effort is focused on making the existing MVP runnable and trustworthy before adding new domains or features.

## Phase 0: Reconnaissance

The original review identified:

- Missing reproducible Python dependency declarations.
- Missing installed backend and frontend dependencies.
- A broken CLI import: `evaluate_price` did not exist; the engine exposed `compute_price`.
- Incorrect top-level relative imports in API routes.
- Frontend/backend payload and response mismatches.
- Unsafe formula execution through Python `eval()`.
- Missing request signal validation.
- Constraints applied before final rounding.
- Incomplete overlap, publishing, rollback, audit, authentication, and scorecard behavior.
- A workspace without Git metadata.

The Phase 0 baseline could not import FastAPI, collect pytest tests, or build the frontend because dependencies were unavailable.

## Phase 1: Installability and Baseline Recovery

Completed changes:

- Added pinned Python dependencies in `requirements.txt`.
- Added Windows PowerShell setup instructions to `README.md`.
- Created `web/package-lock.json` from the existing frontend manifest.
- Fixed the CLI to call `compute_price(pack, context)`.
- Added focused CLI help and pricing tests in `tests/unit/test_cli.py`.
- Fixed API route imports so `api.main` can load under Uvicorn.
- Added `.gitignore` rules for Python environments, Node dependencies, build output, runtime data, caches, and `phase*.txt` notes.
- Initialized Git, created `main`, and pushed the baseline to `origin/main`.

Phase 1 verification:

- Local virtual-environment dependency installation: passed.
- Backend import: passed.
- Test collection: 67 tests collected.
- CLI help: passed.
- Backend startup and `/health`: passed.
- Frontend `npm ci`: passed.
- Frontend production build: passed.
- Phase 1 full backend suite: 66 passed, 1 failed.

The Phase 1 failure was:

```text
tests/golden/test_banking.py::TestBankingGolden::test_home_excellent_premium_customer
Expected: Decimal("6.0")
Actual:   Decimal("6.50")
```

That expected-value mismatch was intentionally not changed.

## Phase 2: Formula Evaluator Recovery

Phase 2 replaced Python `eval()` with a restricted AST interpreter.

Changed implementation files:

- `engine/evaluate/formula.py`
- `engine/validate/validator.py`
- `tests/unit/test_formula.py`

No domain pack, API contract, rounding rule, constraint order, or frontend file was changed.

### Supported Formula Grammar

The evaluator currently supports:

- Finite integer and floating-point constants.
- Numeric names supplied by the runtime context.
- Parenthesized expressions.
- Binary `+`, `-`, `*`, and `/` operators.
- Unary `+` and `-` operators.
- `min(value1, value2, ...)`.
- `max(value1, value2, ...)`.
- `clamp(value, lower, upper)`.

There are no exposed constants, Python built-ins, modules, globals, locals, or arbitrary objects.

Expression limits are:

- 256 characters maximum.
- 64 AST nodes maximum.
- 16 levels of AST depth maximum.

The evaluator returns `Decimal`, preserving the existing public return type and the existing float-to-string conversion behavior for valid formulas.

### Rejected Formula Constructs

The AST validator rejects:

- Unknown names and functions.
- Attribute access.
- Subscripting.
- Imports.
- Lambdas.
- Comprehensions and generator expressions.
- Assignments.
- Comparisons and conditional expressions.
- Unsupported operators.
- Keyword function arguments.
- Invalid function arity.
- Division by zero.
- Non-finite values such as infinity and NaN.
- Empty, syntactically invalid, overlong, or overly complex expressions.

The application Python search found no `eval()` or `exec()` calls. `rg` was unavailable in the Windows environment, so PowerShell `Select-String` was used for the final search.

### Validator and Runtime Agreement

The validator imports `SUPPORTED_FORMULA_FUNCTIONS` and `validate_formula` from the evaluator module. Runtime evaluation uses the same `SUPPORTED_FORMULA_FUNCTIONS` and AST validation path.

Focused tests cover:

- Arithmetic precedence and unary expressions.
- All three approved functions.
- Unknown names and functions.
- Attribute access, subscripting, lambdas, comprehensions, and import attempts.
- Division by zero and non-finite values.
- Validator/runtime agreement.
- Existing expressions from all four shipped packs.

## Phase 2 Verification

Exact commands run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_formula.py -q
.\.venv\Scripts\python.exe -m pytest tests -q
git diff --check
```

Focused formula result:

```text
17 passed
```

Full suite result:

```text
82 passed, 2 failed
```

The full-suite failures are:

### 1. Existing banking golden mismatch

```text
tests/golden/test_banking.py::TestBankingGolden::test_home_excellent_premium_customer

Expected: Decimal('6.0')
Actual:   Decimal('6.50')
```

This is the same failure recorded during Phase 1. Phase 2 did not modify the banking pack, rounding, constraints, or banking runtime path.

### 2. Ecommerce constraint property failure

```text
tests/property/test_properties.py::test_ecomm_price_within_constraints

Falsifying example:
mrp=100.5
inventory=0.0
demand=80.0
category='electronics'

Expected price <= 100.51
Actual price: 101.0
```

This failure was not present in the Phase 1 recorded result, so it is newly observed in the full run. It is caused by the existing constraint-before-rounding behavior, not by the Phase 2 formula diff. The Phase 2 scope explicitly prohibits changing rounding or constraint ordering, so it remains deferred.

The formula compatibility tests confirm that the existing shipped formula outputs remain unchanged for the formulas covered by the tests.

## Remaining Formula Review Findings

The AST interpreter is substantially narrower than the previous `eval()` implementation, but security is not proven by tests alone. Two compatibility issues remain for a later review:

1. `_numeric_value()` accepts subclasses of `int`, `float`, and `Decimal` through `isinstance()`. A direct in-process caller could provide a custom numeric subclass whose conversion behavior is not equivalent to a plain numeric value. API JSON inputs do not provide such objects, but the engine boundary could be hardened by accepting only exact numeric types.

2. Formula validation allows all declared signal names in formula expressions, while runtime evaluation filters the context to numeric values. A formula referring to a declared enum, string, or boolean signal could pass validation and then fail at runtime as an unknown numeric name. Formula validation should eventually restrict names to numeric signal metadata.

Additionally, constraint expressions are evaluated at runtime but are not currently passed through `_check_formula()` during pack validation. This should be addressed in a later formula-validation follow-up without changing pricing semantics.

## Recommended Next Steps

1. Review and harden the remaining formula boundary issues above.
2. Implement request signal validation for required fields, unknown fields, types, enum values, and numeric ranges.
3. Enforce floor, ceiling, and rate constraints after rounding.
4. Resolve rule overlap, gaps, and deterministic tie-breaking.
5. Repair frontend/backend request and response contracts.
6. Correct domain-pack expected prices independently of implementation changes.
7. Harden publishing, versioning, rollback, audit, and authentication behavior.
8. Replace hard-coded scorecard metrics with measured evidence.
9. Run clean-install and end-to-end release verification.

No Phase 3 implementation has been started in this report.
