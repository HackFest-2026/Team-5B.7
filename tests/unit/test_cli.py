import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from cli import main


def test_cli_help(capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["cli.py", "--help"])

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 0
    assert "Monetize360" in capsys.readouterr().out


def test_cli_price_with_existing_pack(capsys, monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "cli.py",
            "price",
            "--pack",
            str(ROOT / "packs" / "ecommerce.json"),
            "--context",
            json.dumps(
                {
                    "category": "electronics",
                    "mrp": 1000,
                    "inventory_pct": 15,
                    "demand_score": 85,
                }
            ),
        ],
    )

    main()

    result = json.loads(capsys.readouterr().out)
    assert result["pack_id"] == "ecommerce"
    assert "price" in result
    assert "fingerprint" in result