from yworkspace.adopt import discover as dsc
from yworkspace.app import build_session
from yworkspace.config import Config


def legacy(root):
    (root / "shop").mkdir(parents=True)
    (root / "shop/__init__.py").write_text("", encoding="utf-8")
    (root / "shop/models.py").write_text(
        "try:\n    from sqlalchemy import Column, Integer, String\nexcept ImportError:  # the CLI works without it\n"
        "    Column = Integer = String = lambda *a, **k: None\nfrom .db import Base\n\n\nclass Order(Base):\n"
        "    __tablename__ = 'orders'\n    id = Column(Integer, primary_key=True)\n    item = Column(String)\n", encoding="utf-8")
    (root / "shop/db.py").write_text("import os\nURL = os.environ['DATABASE_URL']\nBase = object\n", encoding="utf-8")
    (root / "shop/pricing.py").write_text("from shop.models import Order\n\n\ndef total(prices, vat=0.2):\n"
                                          "    # TODO: rounding rules\n    return round(sum(prices) * (1 + vat), 2)\n", encoding="utf-8")
    (root / "cli.py").write_text("import sys\nfrom shop.pricing import total\n\nif __name__ == \"__main__\":\n"
                                 "    print('total', total([float(x) for x in sys.argv[1:]]))\n", encoding="utf-8")
    (root / "requirements.txt").write_text("sqlalchemy\nfastapi==0.110.0\n", encoding="utf-8")
    (root / "schema.sql").write_text("CREATE TABLE customers (\n  id INTEGER PRIMARY KEY,\n  name TEXT NOT NULL,\n"
                                     "  email TEXT,\n  PRIMARY KEY (id)\n);\n", encoding="utf-8")


def test_discover_map_health(tmp_path):
    legacy(tmp_path)
    d = dsc.discover(tmp_path)
    assert d.languages["Python"] > 10 and "SQLAlchemy" in d.technologies and "FastAPI" in d.technologies
    assert "pip install -r requirements.txt" in d.install and "cli.py" in d.entrypoints
    assert "DATABASE_URL" in d.env_vars and not d.has_readme and d.tests_found == 0
    g = dsc.python_imports(tmp_path)
    assert g["shop.models"] == {"shop.db"} and g["cli"] == {"shop.pricing"} and "shop.models" in g["shop.pricing"]
    t = dsc.data_model(tmp_path)
    assert t["orders"] == ["id", "item"] and t["customers"] == ["id", "name", "email"]
    assert "erDiagram" in dsc.er_mermaid(t) and "-->" in dsc.mermaid(g)
    assert dsc.cycles({"a": {"b"}, "b": {"a"}})
    h = dsc.health(tmp_path, d)
    text = h.text()
    assert "No tests" in text and "Unpinned Python dependencies: sqlalchemy" in text and h.score < 70


def test_js_imports(tmp_path):
    (tmp_path / "src/lib").mkdir(parents=True)
    (tmp_path / "src/index.ts").write_text("import { a } from './lib/a'\nconst b = require('../x')\n", encoding="utf-8")
    (tmp_path / "src/lib/a.ts").write_text("export const a = 1\nimport('./b')\n", encoding="utf-8")
    (tmp_path / "src/lib/b.js").write_text("", encoding="utf-8")
    g = dsc.js_imports(tmp_path)
    assert g["src/index.ts"] == {"src/lib/a.ts"} and g["src/lib/a.ts"] == {"src/lib/b.js"}


def test_adopt_tools_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setenv("YW_HOME", str(tmp_path / "home"))
    root = tmp_path / "eski"
    legacy(root)
    sess = build_session(root, Config(sandbox="local"), with_engine=True)
    call = sess.registry.call
    assert "SQLAlchemy" in call("adopt_discover", {}).text
    m = call("adopt_map", {}).text
    assert "```mermaid" in m and "orders" in m
    assert "WARNING: the command failed" in call("adopt_golden", {"name": "x", "command": "python cli.py 1"}).text
    rec = call("adopt_golden", {"name": "toplam", "command": "DATABASE_URL=sqlite:// python cli.py 10 5.5"})
    assert not rec.is_error, rec.text
    assert "total 18.6" in (root / "tests/golden/toplam.out").read_text(encoding="utf-8")
    assert (root / "tests/test_golden_master.py").exists()
    assert "behave exactly as recorded" in call("adopt_golden_check", {}).text
    pricing = root / "shop/pricing.py"
    pricing.write_text(pricing.read_text(encoding="utf-8").replace("round(", "int(").replace(", 2)", ")"), encoding="utf-8")
    changed = call("adopt_golden_check", {}).text
    assert "BEHAVIOUR CHANGED" in changed and "total 18" in changed
    import subprocess
    import sys
    r = subprocess.run([sys.executable, "tests/golden/check.py"], cwd=root, capture_output=True, text=True)
    assert r.returncode == 1 and "CHANGED: toplam" in r.stdout
    docs = call("adopt_docs", {}).text
    assert "README.md" in docs and ".env.example" in docs
    assert "DATABASE_URL=" in (root / ".env.example").read_text(encoding="utf-8")
    assert "erDiagram" in (root / "docs/ARCHITECTURE.md").read_text(encoding="utf-8")
    health = call("adopt_health", {}).text
    assert "Health score" in health
    mig = call("adopt_migration", {"goal": "SQLAlchemy 2", "steps": ["typed models", "new session API"]}).text
    assert "Added tasks" in mig
    tasks = sess.engine.state.tasks
    assert tasks[-1].depends_on == [tasks[-2].id] and tasks[-1].verify == "adopt_golden_check"
