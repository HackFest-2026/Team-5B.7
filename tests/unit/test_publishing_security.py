"""
Unit and integration tests for Publishing, Versioning, Persistence, and Security.

Covers:
  1. Immutable versions (prevent overwriting published/archived versions, draft workflow, startup seeding idempotency).
  2. SHA-256 canonical fingerprints (determinism, storage, tamper detection).
  3. Cryptographic audit log (SHA-256 hash chain, genesis hash, chronological linkage).
  4. Audit verification (integrity checks, tampering detection for data or chain breaks).
  5. Rollback (restoring past version, preserving version history, audit logging).
  6. Publishing safeguards (reject invalid packs, four-eyes role separation, golden-test enforcement).
  7. Input validation and security (request body size limits, rule count limits, formula safety).
"""
from __future__ import annotations

import copy
import json
import sqlite3
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.storage.db import (
    GENESIS_HASH,
    ImmutableVersionError,
    TamperError,
    get_audit_log,
    get_pack,
    get_published_pack,
    init_db,
    list_all_pack_versions,
    publish_pack,
    rollback_pack,
    upsert_pack,
    verify_audit_chain,
)
from engine.fingerprint import (
    canonical_pack_json,
    compute_pack_fingerprint,
    verify_pack_fingerprint,
)
from engine.schema.pack import DomainPack
from engine.validate import validate_pack


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    """Provide a fresh, isolated database for each test."""
    test_db_path = tmp_path / "test_monetize360.db"
    monkeypatch.setattr("api.storage.db.DB_PATH", test_db_path)
    init_db()
    return test_db_path


@pytest.fixture
def sample_pack_dict() -> dict:
    """Return a minimal valid pack dictionary."""
    return {
        "pack_id": "test_saas",
        "version": "1.0.0",
        "description": "SaaS Subscription Pricing",
        "unit": {"kind": "currency", "code": "USD", "decimals": 2},
        "signals": [
            {"key": "seats", "type": "integer", "min": 1, "max": 1000, "required": True},
            {"key": "is_annual", "type": "boolean", "required": False},
        ],
        "base": {"type": "fixed", "value": 50.0},
        "stages": [
            {"id": "discount", "stacking": "all", "description": "Discount stage"}
        ],
        "rules": [
            {
                "id": "R-ANNUAL-DISCOUNT",
                "stage": "discount",
                "priority": 10,
                "when": {"all": [{"signal": "is_annual", "op": "eq", "value": True}]},
                "then": {"op": "multiply", "value": 0.80},
            }
        ],
        "constraints": [
            {"id": "C-FLOOR", "type": "floor", "expr": "base * 0.50"},
            {"id": "C-CEIL", "type": "ceiling", "expr": "base * 2.00"},
        ],
        "rounding": {"mode": "nearest", "step": 1.0},
    }


# ===========================================================================
# 1. SHA-256 Canonical Fingerprints
# ===========================================================================

class TestFingerprints:
    def test_fingerprint_determinism_and_key_order_independence(self, sample_pack_dict):
        """Fingerprint must be deterministic regardless of dictionary key ordering."""
        fp1 = compute_pack_fingerprint(sample_pack_dict)

        # Create reversed-order copy
        reversed_dict = {k: sample_pack_dict[k] for k in reversed(list(sample_pack_dict.keys()))}
        fp2 = compute_pack_fingerprint(reversed_dict)

        assert fp1 == fp2
        assert len(fp1) == 64
        assert verify_pack_fingerprint(sample_pack_dict, fp1) is True
        assert verify_pack_fingerprint(reversed_dict, fp1) is True

    def test_fingerprint_changes_on_content_modification(self, sample_pack_dict):
        """Any content alteration must produce a distinct fingerprint."""
        original_fp = compute_pack_fingerprint(sample_pack_dict)

        modified = copy.deepcopy(sample_pack_dict)
        modified["base"]["value"] = 55.0
        modified_fp = compute_pack_fingerprint(modified)

        assert original_fp != modified_fp
        assert verify_pack_fingerprint(modified, original_fp) is False

    def test_fingerprint_works_with_domainpack_model(self, sample_pack_dict):
        """compute_pack_fingerprint must handle DomainPack Pydantic objects seamlessly."""
        pack_obj = DomainPack.model_validate(sample_pack_dict)
        fp_obj = compute_pack_fingerprint(pack_obj)
        fp_dict = compute_pack_fingerprint(sample_pack_dict)

        assert fp_obj == fp_dict


# ===========================================================================
# 2. Immutable Versions
# ===========================================================================

class TestVersionImmutability:
    def test_draft_is_mutable(self, isolated_db, sample_pack_dict):
        """Draft packs can be repeatedly updated before publishing."""
        upsert_pack("test_saas", "1.0.0", sample_pack_dict, status="draft", actor="editor1")
        saved1 = get_pack("test_saas", "1.0.0")
        assert saved1["status"] == "draft"
        assert saved1["pack_data"]["base"]["value"] == 50.0

        # Update draft
        updated_dict = copy.deepcopy(sample_pack_dict)
        updated_dict["base"]["value"] = 60.0
        upsert_pack("test_saas", "1.0.0", updated_dict, status="draft", actor="editor1")
        saved2 = get_pack("test_saas", "1.0.0")
        assert saved2["pack_data"]["base"]["value"] == 60.0

    def test_published_version_cannot_be_overwritten(self, isolated_db, sample_pack_dict):
        """Attempting to overwrite a published version with altered content must raise ImmutableVersionError."""
        upsert_pack("test_saas", "1.0.0", sample_pack_dict, status="draft", actor="editor1")
        publish_pack("test_saas", "1.0.0", actor="approver1")

        published = get_published_pack("test_saas")
        assert published["version"] == "1.0.0"
        assert published["status"] == "published"

        # Try to modify published version
        tampered = copy.deepcopy(sample_pack_dict)
        tampered["base"]["value"] = 99.0

        with pytest.raises(ImmutableVersionError) as exc_info:
            upsert_pack("test_saas", "1.0.0", tampered, status="draft", actor="hacker")

        assert "immutable" in str(exc_info.value).lower()
        # Verify published content was not altered
        unchanged = get_pack("test_saas", "1.0.0")
        assert unchanged["pack_data"]["base"]["value"] == 50.0
        assert unchanged["status"] == "published"

    def test_seeding_identical_content_is_idempotent(self, isolated_db, sample_pack_dict):
        """Re-saving the identical pack (like on startup seeding) is permitted and leaves status published."""
        upsert_pack("test_saas", "1.0.0", sample_pack_dict, status="draft", actor="seed")
        publish_pack("test_saas", "1.0.0", actor="seed")

        # Simulate second startup seed with identical content
        reseeded = upsert_pack("test_saas", "1.0.0", sample_pack_dict, status="published", actor="seed")
        assert reseeded["version"] == "1.0.0"
        assert reseeded["status"] == "published"


# ===========================================================================
# 3. Cryptographic Audit Log & Verification
# ===========================================================================

class TestAuditChainAndVerification:
    def test_audit_log_hash_chain_linking(self, isolated_db, sample_pack_dict):
        """Every audit log entry must link to the preceding entry's hash."""
        upsert_pack("test_saas", "1.0.0", sample_pack_dict, status="draft", actor="alice")
        publish_pack("test_saas", "1.0.0", actor="bob")

        log = get_audit_log("test_saas", limit=10)
        assert len(log) >= 2

        # In get_audit_log, entries are returned ordered by id DESC
        latest_entry = log[0]
        first_entry = log[-1]

        assert first_entry["prev_hash"] == GENESIS_HASH
        assert first_entry["entry_hash"] is not None
        assert latest_entry["prev_hash"] == first_entry["entry_hash"]

    def test_verify_audit_chain_intact(self, isolated_db, sample_pack_dict):
        """Unmodified audit log must pass verification."""
        upsert_pack("test_saas", "1.0.0", sample_pack_dict, status="draft", actor="alice")
        publish_pack("test_saas", "1.0.0", actor="bob")

        verification = verify_audit_chain()
        assert verification["valid"] is True
        assert verification["total_records"] >= 2
        assert "verified" in verification["message"].lower()

    def test_verify_audit_chain_detects_content_tampering(self, isolated_db, sample_pack_dict):
        """Tampering with any audit log field must be flagged by verify_audit_chain."""
        upsert_pack("test_saas", "1.0.0", sample_pack_dict, status="draft", actor="alice")
        publish_pack("test_saas", "1.0.0", actor="bob")

        # Directly tamper with actor in database
        conn = sqlite3.connect(str(isolated_db))
        conn.execute("UPDATE audit_log SET actor = 'malicious_user' WHERE id = 1")
        conn.commit()
        conn.close()

        verification = verify_audit_chain()
        assert verification["valid"] is False
        assert verification["tampered_id"] == 1
        assert "modified" in verification["reason"].lower() or "mismatch" in verification["reason"].lower()

    def test_verify_audit_chain_detects_broken_chain(self, isolated_db, sample_pack_dict):
        """Tampering with prev_hash breaks the chain and must be reported."""
        upsert_pack("test_saas", "1.0.0", sample_pack_dict, status="draft", actor="alice")
        publish_pack("test_saas", "1.0.0", actor="bob")

        conn = sqlite3.connect(str(isolated_db))
        conn.execute("UPDATE audit_log SET prev_hash = 'badbeef' WHERE id = 2")
        conn.commit()
        conn.close()

        verification = verify_audit_chain()
        assert verification["valid"] is False
        assert verification["tampered_id"] == 2
        assert "chain" in verification["reason"].lower()


# ===========================================================================
# 4. Rollback
# ===========================================================================

class TestRollback:
    def test_rollback_restores_previous_version_safely(self, isolated_db, sample_pack_dict):
        """Rollback restores historical version, archives current, and preserves history."""
        # Step 1: publish v1.0.0
        upsert_pack("test_saas", "1.0.0", sample_pack_dict, status="draft", actor="alice")
        publish_pack("test_saas", "1.0.0", actor="bob")

        # Step 2: publish v2.0.0
        v2_dict = copy.deepcopy(sample_pack_dict)
        v2_dict["version"] = "2.0.0"
        v2_dict["base"]["value"] = 80.0
        upsert_pack("test_saas", "2.0.0", v2_dict, status="draft", actor="alice")
        publish_pack("test_saas", "2.0.0", actor="bob")

        assert get_published_pack("test_saas")["version"] == "2.0.0"

        # Step 3: Rollback to v1.0.0
        restored = rollback_pack("test_saas", "1.0.0", actor="operator")

        assert restored["version"] == "1.0.0"
        assert restored["status"] == "published"
        assert get_published_pack("test_saas")["version"] == "1.0.0"

        # Verify v2.0.0 is archived and its content was NOT mutated
        v2_row = get_pack("test_saas", "2.0.0")
        assert v2_row["status"] == "archived"
        assert v2_row["pack_data"]["base"]["value"] == 80.0

        # Verify audit log recorded rollback
        audit = get_audit_log("test_saas", limit=5)
        latest_audit = audit[0]
        assert latest_audit["event"] == "rollback"
        detail = json.loads(latest_audit["detail"])
        assert detail["from_version"] == "2.0.0"
        assert detail["to_version"] == "1.0.0"

        # Verify audit chain integrity remains intact
        assert verify_audit_chain()["valid"] is True

    def test_rollback_rejects_nonexistent_or_already_active_version(self, isolated_db, sample_pack_dict):
        """Rollback to a nonexistent version or the currently active version must be rejected."""
        upsert_pack("test_saas", "1.0.0", sample_pack_dict, status="draft", actor="alice")
        publish_pack("test_saas", "1.0.0", actor="bob")

        with pytest.raises(ValueError) as exc:
            rollback_pack("test_saas", "9.9.9", actor="admin")
        assert "not found" in str(exc.value).lower()

        with pytest.raises(ValueError) as exc:
            rollback_pack("test_saas", "1.0.0", actor="admin")
        assert "already at version" in str(exc.value).lower()


# ===========================================================================
# 5. Publishing Safeguards & Role Separation
# ===========================================================================

class TestPublishingSafeguards:
    def test_publishing_rejects_invalid_pack(self, isolated_db, sample_pack_dict):
        """Packs failing validation must be rejected from publishing."""
        invalid_pack = copy.deepcopy(sample_pack_dict)
        # Introduce unknown signal reference
        invalid_pack["rules"][0]["when"] = {"all": [{"signal": "unknown_signal", "op": "eq", "value": 1}]}

        upsert_pack("test_saas", "1.0.0", invalid_pack, status="draft", actor="alice")

        with pytest.raises(ValueError) as exc:
            publish_pack("test_saas", "1.0.0", actor="bob")
        assert "validation failed" in str(exc.value).lower()

    def test_publishing_golden_test_verification(self, isolated_db, sample_pack_dict):
        """Packs with embedded golden tests must pass them before being published."""
        pack_with_tests = copy.deepcopy(sample_pack_dict)
        pack_with_tests["test_cases"] = [
            {
                "description": "Base price check without annual discount",
                "signals": {"seats": 5, "is_annual": False},
                "expected_price": 50.0,
            },
            {
                "description": "Failing test check",
                "signals": {"seats": 5, "is_annual": True},
                "expected_price": 999.0,  # Actual is 40.0 (50 * 0.8)
            },
        ]

        upsert_pack("test_saas", "1.0.0", pack_with_tests, status="draft", actor="alice")

        with pytest.raises(ValueError) as exc:
            publish_pack("test_saas", "1.0.0", actor="bob", run_golden_tests=True)
        assert "golden test #2 failed" in str(exc.value).lower()

        # Fix expected price
        pack_with_tests["test_cases"][1]["expected_price"] = 40.0
        upsert_pack("test_saas", "1.0.0", pack_with_tests, status="draft", actor="alice")
        published = publish_pack("test_saas", "1.0.0", actor="bob", run_golden_tests=True)
        assert published["status"] == "published"

    def test_publishing_four_eyes_role_separation(self, isolated_db, sample_pack_dict):
        """Editor cannot approve/publish their own pack when role separation is enforced."""
        upsert_pack("test_saas", "1.0.0", sample_pack_dict, status="draft", actor="alice")

        # Alice tries to publish her own draft
        with pytest.raises(ValueError) as exc:
            publish_pack("test_saas", "1.0.0", actor="alice", enforce_role_separation=True)
        assert "role separation" in str(exc.value).lower()

        # Bob (a separate approver) publishes
        published = publish_pack("test_saas", "1.0.0", actor="bob", enforce_role_separation=True)
        assert published["status"] == "published"
        assert published["published_by"] == "bob"

    def test_publishing_tamper_detection(self, isolated_db, sample_pack_dict):
        """If stored pack content is silently mutated without updating fingerprint, publish fails."""
        upsert_pack("test_saas", "1.0.0", sample_pack_dict, status="draft", actor="alice")

        # Tamper directly in SQLite
        conn = sqlite3.connect(str(isolated_db))
        tampered_data = copy.deepcopy(sample_pack_dict)
        tampered_data["base"]["value"] = 999.0
        conn.execute("UPDATE packs SET pack_data = ? WHERE pack_id = 'test_saas'", (json.dumps(tampered_data),))
        conn.commit()
        conn.close()

        with pytest.raises(TamperError) as exc:
            publish_pack("test_saas", "1.0.0", actor="bob")
        assert "integrity check failed" in str(exc.value).lower()


# ===========================================================================
# 6. Input Validation & Security Limits
# ===========================================================================

class TestSecurityAndInputValidation:
    def test_rule_count_limit_in_validation(self, sample_pack_dict):
        """Pack exceeding maximum rule limit (500) must fail validation."""
        pack_data = copy.deepcopy(sample_pack_dict)
        base_rule = pack_data["rules"][0]
        # Generate 505 rules
        pack_data["rules"] = [
            {**base_rule, "id": f"R-{i}", "priority": i}
            for i in range(505)
        ]

        pack_obj = DomainPack.model_validate(pack_data)
        result = validate_pack(pack_obj)
        assert result.valid is False
        assert any(e.code == "C-LIMIT" and "Rule count" in e.message for e in result.errors)

    def test_request_body_size_limit_via_api(self, isolated_db):
        """Requests exceeding 1MB payload must return HTTP 413."""
        client = TestClient(app)

        # Huge payload over 1MB
        oversized_data = {"pack": {"padding": "X" * (1_050_000)}}
        response = client.post("/v1/draft", json=oversized_data)
        assert response.status_code == 413
        assert "too large" in response.json()["detail"].lower()

    def test_api_publishing_and_rollback_flow(self, isolated_db, sample_pack_dict):
        """Test complete API lifecycle: draft -> publish -> rollback -> audit verify."""
        client = TestClient(app)

        # 1. Save Draft v1.0.0
        res = client.post("/v1/draft", json={"pack": sample_pack_dict, "actor": "alice"})
        assert res.status_code == 200

        # 2. Try to publish with role separation violation
        res = client.post(
            "/v1/publish",
            json={
                "pack_id": "test_saas",
                "version": "1.0.0",
                "actor": "alice",
                "enforce_role_separation": True,
            },
        )
        assert res.status_code == 403

        # 3. Publish with separate approver
        res = client.post(
            "/v1/publish",
            json={
                "pack_id": "test_saas",
                "version": "1.0.0",
                "actor": "bob",
                "enforce_role_separation": True,
            },
        )
        assert res.status_code == 200
        assert res.json()["status"] == "published"

        # 4. Attempting to overwrite published v1.0.0 fails with 409 Conflict
        tampered_v1 = copy.deepcopy(sample_pack_dict)
        tampered_v1["base"]["value"] = 123.0
        res = client.post("/v1/draft", json={"pack": tampered_v1, "actor": "alice"})
        assert res.status_code == 409

        # 5. Create and publish v2.0.0
        v2_dict = copy.deepcopy(sample_pack_dict)
        v2_dict["version"] = "2.0.0"
        v2_dict["base"]["value"] = 75.0
        res = client.post("/v1/draft", json={"pack": v2_dict, "actor": "alice"})
        assert res.status_code == 200
        res = client.post(
            "/v1/publish",
            json={
                "pack_id": "test_saas",
                "version": "2.0.0",
                "actor": "bob",
                "enforce_role_separation": True,
            },
        )
        assert res.status_code == 200

        # Verify active version is 2.0.0
        res = client.get("/v1/domains/test_saas")
        assert res.status_code == 200
        assert res.json()["version"] == "2.0.0"

        # 6. Rollback to v1.0.0
        res = client.post(
            "/v1/rollback",
            json={
                "pack_id": "test_saas",
                "target_version": "1.0.0",
                "actor": "admin",
            },
        )
        assert res.status_code == 200
        assert res.json()["pack"]["version"] == "1.0.0"

        # Verify active is now 1.0.0
        res = client.get("/v1/domains/test_saas")
        assert res.json()["version"] == "1.0.0"

        # 7. Verify audit chain via API
        res = client.get("/v1/audit/verify")
        assert res.status_code == 200
        assert res.json()["valid"] is True


# ===========================================================================
# 7. Semantic Versioning & Version Creation
# ===========================================================================

class TestSemanticVersioning:
    def test_semver_validation_rules(self):
        """Standard SemVer strings pass; invalid formats are rejected."""
        from api.storage.db import validate_semver, bump_semver

        assert validate_semver("1.0.0") is True
        assert validate_semver("0.1.0") is True
        assert validate_semver("2.10.4") is True
        assert validate_semver("1.0.0-rc.1") is True

        assert validate_semver("1.0") is False
        assert validate_semver("v1.0.0") is False
        assert validate_semver("latest") is False
        assert validate_semver("abc") is False
        assert validate_semver("") is False

    def test_domainpack_schema_rejects_invalid_semver(self, sample_pack_dict):
        """DomainPack Pydantic model must reject invalid version strings."""
        invalid_pack = copy.deepcopy(sample_pack_dict)
        invalid_pack["version"] = "v1.0"

        with pytest.raises(Exception) as exc:
            DomainPack.model_validate(invalid_pack)
        assert "semantic version" in str(exc.value).lower()

    def test_semver_bumping_logic(self):
        """bump_semver correctly calculates major, minor, and patch increments."""
        from api.storage.db import bump_semver

        assert bump_semver("1.2.3", "patch") == "1.2.4"
        assert bump_semver("1.2.3", "minor") == "1.3.0"
        assert bump_semver("1.2.3", "major") == "2.0.0"

    def test_create_new_version_workflow(self, isolated_db, sample_pack_dict):
        """create_new_version creates an unreleased draft with bumped version."""
        from api.storage.db import create_new_version

        upsert_pack("test_saas", "1.0.0", sample_pack_dict, status="draft", actor="alice")
        publish_pack("test_saas", "1.0.0", actor="bob")

        # Bump minor -> 1.1.0
        new_v = create_new_version("test_saas", bump_type="minor", actor="alice")
        assert new_v["version"] == "1.1.0"
        assert new_v["status"] == "draft"

        # Verify 1.0.0 remains published and 1.1.0 is in draft
        assert get_published_pack("test_saas")["version"] == "1.0.0"
        assert get_pack("test_saas", "1.1.0")["status"] == "draft"

    def test_bump_version_api(self, isolated_db, sample_pack_dict):
        """POST /v1/domains/{domain_id}/bump creates next draft version."""
        client = TestClient(app)
        client.post("/v1/draft", json={"pack": sample_pack_dict, "actor": "alice"})
        client.post("/v1/publish", json={"pack_id": "test_saas", "version": "1.0.0", "actor": "bob"})

        res = client.post("/v1/domains/test_saas/bump", json={"bump_type": "patch", "actor": "alice"})
        assert res.status_code == 200
        assert res.json()["pack"]["version"] == "1.0.1"
        assert res.json()["pack"]["status"] == "draft"


# ===========================================================================
# 8. Explicit Lifecycle & State Transitions
# ===========================================================================

class TestExplicitLifecycle:
    def test_lifecycle_full_happy_path(self, isolated_db, sample_pack_dict):
        """Lifecycle transitions: draft -> in_review -> approved -> published."""
        from api.storage.db import transition_pack_lifecycle

        # 1. Created as draft
        upsert_pack("test_saas", "1.0.0", sample_pack_dict, status="draft", actor="alice")
        assert get_pack("test_saas", "1.0.0")["status"] == "draft"

        # 2. Submit for review (draft -> in_review)
        in_rev = transition_pack_lifecycle("test_saas", "1.0.0", "in_review", actor="alice")
        assert in_rev["status"] == "in_review"

        # 3. Approve (in_review -> approved)
        approved = transition_pack_lifecycle("test_saas", "1.0.0", "approved", actor="bob", enforce_role_separation=True)
        assert approved["status"] == "approved"

        # 4. Publish (approved -> published)
        pub = publish_pack("test_saas", "1.0.0", actor="bob", require_approval=True)
        assert pub["status"] == "published"
        assert get_published_pack("test_saas")["version"] == "1.0.0"

    def test_lifecycle_reject_back_to_draft(self, isolated_db, sample_pack_dict):
        """Reviewer can reject pack in review back to draft with reason."""
        from api.storage.db import transition_pack_lifecycle

        upsert_pack("test_saas", "1.0.0", sample_pack_dict, status="draft", actor="alice")
        transition_pack_lifecycle("test_saas", "1.0.0", "in_review", actor="alice")

        rejected = transition_pack_lifecycle("test_saas", "1.0.0", "draft", actor="reviewer_bob", reason="Fix pricing ceiling")
        assert rejected["status"] == "draft"

        # Check audit log recorded rejection
        logs = get_audit_log("test_saas", limit=5)
        latest = logs[0]
        assert latest["event"] == "status_draft"
        assert "Fix pricing ceiling" in latest["detail"]

    def test_lifecycle_disallows_invalid_transitions(self, isolated_db, sample_pack_dict):
        """Invalid transitions (e.g. draft directly to approved, archived to in_review) are blocked."""
        from api.storage.db import transition_pack_lifecycle

        upsert_pack("test_saas", "1.0.0", sample_pack_dict, status="draft", actor="alice")

        with pytest.raises(ValueError) as exc:
            transition_pack_lifecycle("test_saas", "1.0.0", "approved", actor="alice")
        assert "invalid lifecycle transition" in str(exc.value).lower()

    def test_editing_approved_draft_resets_to_draft(self, isolated_db, sample_pack_dict):
        """Modifying the content of an approved pack resets status to draft for re-review."""
        from api.storage.db import transition_pack_lifecycle

        upsert_pack("test_saas", "1.0.0", sample_pack_dict, status="draft", actor="alice")
        transition_pack_lifecycle("test_saas", "1.0.0", "in_review", actor="alice")
        transition_pack_lifecycle("test_saas", "1.0.0", "approved", actor="bob")
        assert get_pack("test_saas", "1.0.0")["status"] == "approved"

        # Alice modifies rule in approved draft
        modified = copy.deepcopy(sample_pack_dict)
        modified["base"]["value"] = 55.0
        upsert_pack("test_saas", "1.0.0", modified, status="draft", actor="alice")

        # Status must have reset to draft
        pack_now = get_pack("test_saas", "1.0.0")
        assert pack_now["status"] == "draft"

    def test_publishing_with_approval_gate_enforced(self, isolated_db, sample_pack_dict):
        """publish_pack(require_approval=True) blocks drafts that have not been approved."""
        upsert_pack("test_saas", "1.0.0", sample_pack_dict, status="draft", actor="alice")

        with pytest.raises(ValueError) as exc:
            publish_pack("test_saas", "1.0.0", actor="bob", require_approval=True)
        assert "must be in 'approved' status" in str(exc.value).lower()

    def test_lifecycle_api_routes(self, isolated_db, sample_pack_dict):
        """Verify API lifecycle endpoints (/submit, /approve, /reject)."""
        client = TestClient(app)

        client.post("/v1/draft", json={"pack": sample_pack_dict, "actor": "alice"})

        # Submit
        res = client.post("/v1/lifecycle/submit", json={"pack_id": "test_saas", "version": "1.0.0", "actor": "alice"})
        assert res.status_code == 200
        assert res.json()["pack"]["status"] == "in_review"

        # Approve with four-eyes separation
        # Alice cannot approve
        res = client.post(
            "/v1/lifecycle/approve",
            json={"pack_id": "test_saas", "version": "1.0.0", "actor": "alice", "enforce_role_separation": True},
        )
        assert res.status_code == 403

        # Bob can approve
        res = client.post(
            "/v1/lifecycle/approve",
            json={"pack_id": "test_saas", "version": "1.0.0", "actor": "bob", "enforce_role_separation": True},
        )
        assert res.status_code == 200
        assert res.json()["pack"]["status"] == "approved"


# ===========================================================================
# 9. Persistence Across Restarts
# ===========================================================================

class TestPersistenceAcrossRestarts:
    def test_data_and_audit_chain_survive_restarts(self, isolated_db, sample_pack_dict):
        """Database re-initialization must preserve versions, fingerprints, published state, and audit chain."""
        # Session 1: create, publish, price
        upsert_pack("test_saas", "1.0.0", sample_pack_dict, status="draft", actor="alice")
        publish_pack("test_saas", "1.0.0", actor="bob")

        v1_fp = get_pack("test_saas", "1.0.0")["fingerprint"]
        audit_records_before = get_audit_log("test_saas")
        count_before = len(audit_records_before)

        # Simulate full application restart by running init_db() on the same file
        init_db()

        # Session 2: verify state
        restored_pub = get_published_pack("test_saas")
        assert restored_pub is not None
        assert restored_pub["version"] == "1.0.0"
        assert restored_pub["status"] == "published"
        assert restored_pub["published_by"] == "bob"
        assert restored_pub["fingerprint"] == v1_fp
        assert restored_pub["fingerprint_verified"] is True

        # Audit log remains intact
        audit_records_after = get_audit_log("test_saas")
        assert len(audit_records_after) == count_before

        # Audit hash chain verification passes across restart
        chain_verification = verify_audit_chain()
        assert chain_verification["valid"] is True
        assert chain_verification["total_records"] >= count_before


# ===========================================================================
# 10. Governance, API Key Guard, and Authorization
# ===========================================================================

class TestGovernanceAndApiKey:
    def test_unauthorized_mutating_requests_rejected_when_api_key_set(self, isolated_db, sample_pack_dict, monkeypatch):
        """When API_KEY is configured, POST operations without or with bad key receive 401."""
        monkeypatch.setattr("api.security.API_KEY", "super-secret-key-12345")
        client = TestClient(app)

        # 1. Draft without header -> 401
        res = client.post("/v1/draft", json={"pack": sample_pack_dict})
        assert res.status_code == 401
        assert "Unauthorized" in res.json()["detail"]

        # 2. Draft with wrong header -> 401
        res = client.post(
            "/v1/draft",
            json={"pack": sample_pack_dict},
            headers={"X-Api-Key": "wrong-key"},
        )
        assert res.status_code == 401

        # 3. Draft with valid header -> 200
        res = client.post(
            "/v1/draft",
            json={"pack": sample_pack_dict},
            headers={"X-Api-Key": "super-secret-key-12345"},
        )
        assert res.status_code == 200

        # 4. Lifecycle transition without header -> 401
        res = client.post(
            "/v1/lifecycle/submit",
            json={"pack_id": "test_saas", "version": "1.0.0", "actor": "alice"},
        )
        assert res.status_code == 401

        # 5. Rollback without header -> 401
        res = client.post(
            "/v1/rollback",
            json={"pack_id": "test_saas", "target_version": "1.0.0", "actor": "alice"},
        )
        assert res.status_code == 401

    def test_safe_read_endpoints_accessible_without_api_key(self, isolated_db, sample_pack_dict, monkeypatch):
        """Read-only and public documentation endpoints are open even when API_KEY is set."""
        monkeypatch.setattr("api.security.API_KEY", "super-secret-key-12345")
        client = TestClient(app)

        # GET /
        res = client.get("/")
        assert res.status_code == 200

        # GET /health
        res = client.get("/health")
        assert res.status_code == 200

        # GET /v1/domains
        res = client.get("/v1/domains")
        assert res.status_code == 200

        # GET /v1/audit/verify
        res = client.get("/v1/audit/verify")
        assert res.status_code == 200


# ===========================================================================
# 11. Stale-Version Conflict Detection (Optimistic Concurrency)
# ===========================================================================

class TestStaleVersionConflict:
    def test_draft_detects_stale_fingerprint_conflict(self, isolated_db, sample_pack_dict):
        """When base_fingerprint is provided and doesn't match current draft, return 409 Conflict."""
        client = TestClient(app)

        # Alice creates initial draft
        res = client.post("/v1/draft", json={"pack": sample_pack_dict, "actor": "alice"})
        assert res.status_code == 200
        initial_fp = res.json()["pack"]["fingerprint"]

        # Bob updates the draft, changing the content and fingerprint
        modified_by_bob = copy.deepcopy(sample_pack_dict)
        modified_by_bob["base"]["value"] = 65.0
        res = client.post("/v1/draft", json={"pack": modified_by_bob, "actor": "bob"})
        assert res.status_code == 200
        new_fp = res.json()["pack"]["fingerprint"]
        assert new_fp != initial_fp

        # Alice now attempts to submit changes based on initial_fp (stale write)
        modified_by_alice = copy.deepcopy(sample_pack_dict)
        modified_by_alice["base"]["value"] = 75.0
        res = client.post(
            "/v1/draft",
            json={
                "pack": modified_by_alice,
                "actor": "alice",
                "base_fingerprint": initial_fp,
            },
        )
        assert res.status_code == 409
        assert "stale version conflict" in res.json()["detail"].lower()

    def test_draft_succeeds_when_base_fingerprint_matches(self, isolated_db, sample_pack_dict):
        """When base_fingerprint matches current draft fingerprint, update succeeds."""
        client = TestClient(app)

        res = client.post("/v1/draft", json={"pack": sample_pack_dict, "actor": "alice"})
        assert res.status_code == 200
        current_fp = res.json()["pack"]["fingerprint"]

        modified = copy.deepcopy(sample_pack_dict)
        modified["base"]["value"] = 55.0
        res = client.post(
            "/v1/draft",
            json={
                "pack": modified,
                "actor": "alice",
                "base_fingerprint": current_fp,
            },
        )
        assert res.status_code == 200
        assert res.json()["pack"]["pack_data"]["base"]["value"] == 55.0


# ===========================================================================
# 12. CORS Configuration & Security Headers
# ===========================================================================

class TestCorsAndSecurityHeaders:
    def test_cors_headers_allowed_origin(self):
        """Allowed origin receives Access-Control-Allow-Origin matching origin."""
        client = TestClient(app)
        res = client.options(
            "/v1/domains",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert res.headers.get("access-control-allow-origin") == "http://localhost:5173"
        assert res.headers.get("access-control-allow-credentials") == "true"

    def test_cors_disallowed_origin_does_not_receive_allow_origin(self):
        """Disallowed origin does not receive Access-Control-Allow-Origin header."""
        client = TestClient(app)
        res = client.options(
            "/v1/domains",
            headers={
                "Origin": "https://malicious-site.attacker.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert res.headers.get("access-control-allow-origin") is None


# ===========================================================================
# 13. Audit Logging on Validation Outcomes
# ===========================================================================

class TestValidationAuditLogging:
    def test_validation_outcomes_recorded_in_audit_chain(self, isolated_db, sample_pack_dict):
        """Calling /v1/validate records validation events in the cryptographic audit chain."""
        client = TestClient(app)

        # 1. Valid pack
        res = client.post("/v1/validate", json={"pack": sample_pack_dict, "actor": "qa_auditor"})
        assert res.status_code == 200
        assert res.json()["valid"] is True

        log = get_audit_log("test_saas")
        assert len(log) >= 1
        assert log[0]["event"] == "validation_passed"
        assert log[0]["actor"] == "qa_auditor"

        # 2. Invalid pack (rule references nonexistent signal to trigger C1 error)
        invalid_pack = copy.deepcopy(sample_pack_dict)
        invalid_pack["rules"][0]["when"]["all"][0]["signal"] = "nonexistent_signal"

        res = client.post("/v1/validate", json={"pack": invalid_pack, "actor": "qa_auditor"})
        assert res.status_code == 200
        assert res.json()["valid"] is False

        log = get_audit_log("test_saas")
        assert log[0]["event"] == "validation_failed"
        assert "Validation failed" in log[0]["detail"]

        # Verification passes on complete chain
        chain = verify_audit_chain()
        assert chain["valid"] is True

