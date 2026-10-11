from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from api.main import app
from api.storage.db import init_db, upsert_pack, publish_pack

ROOT = Path(__file__).parent.parent.parent


def test_scorecard_endpoint_returns_evidence_and_domains(monkeypatch, tmp_path):
    test_db = tmp_path / "test_scorecard.db"
    monkeypatch.setattr("api.storage.db.DB_PATH", test_db)
    init_db()

    # Seed all packs
    packs_dir = ROOT / "packs"
    for pfile in packs_dir.glob("*.json"):
        data = json.loads(pfile.read_text(encoding="utf-8"))
        upsert_pack(data["pack_id"], data.get("version", "1.0.0"), data, status="draft", actor="test")
        publish_pack(data["pack_id"], data.get("version", "1.0.0"), actor="test")

    client = TestClient(app)
    res = client.get("/v1/scorecard")
    assert res.status_code == 200

    data = res.json()
    assert "engine_benchmark" in data
    assert "api_benchmark" in data
    assert "correctness" in data
    assert "audit_verification" in data
    assert data["audit_verification"]["valid"] is True
    assert "domains" in data

    # Verify all 5 domains are reported
    domain_ids = [d["pack_id"] for d in data["domains"]]
    for expected in ["hospitality", "ecommerce", "banking", "ev_charging", "airline"]:
        assert expected in domain_ids


def test_delete_context_endpoint_clears_snapshot(monkeypatch, tmp_path):
    test_db = tmp_path / "test_del_ctx.db"
    monkeypatch.setattr("api.storage.db.DB_PATH", test_db)
    init_db()

    # Seed airline pack
    airline_data = json.loads((ROOT / "packs" / "airline.json").read_text(encoding="utf-8"))
    upsert_pack("airline", "1.0.0", airline_data, status="draft", actor="test")
    publish_pack("airline", "1.0.0", actor="test")

    client = TestClient(app)

    # 1. Update context
    put_res = client.put(
        "/v1/context/airline",
        json={
            "signals": {"demand_index": 50, "available_seats": 200},
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "max_age_seconds": 300,
            "source": "test",
        },
    )
    assert put_res.status_code == 200

    # 2. Verify context exists
    get_res = client.get("/v1/context/airline")
    assert get_res.status_code == 200

    # 3. Delete context
    del_res = client.delete("/v1/context/airline")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "cleared"

    # 4. Verify context is now gone (404)
    get_res2 = client.get("/v1/context/airline")
    assert get_res2.status_code == 404
