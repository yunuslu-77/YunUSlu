import yaml

from yworkspace.skills import load_all, model_family, select, skills_for
from yworkspace.skills.export import export


def test_library_is_complete():
    skills = load_all()
    assert len(skills) >= 25
    for s in skills:
        assert (s.path / "core.en.md").read_text(encoding="utf-8").strip() and (s.path / "core.tr.md").read_text(encoding="utf-8").strip(), s.name
        assert s.triggers and s.description


def test_matching():
    names = [s.name for s in select("developer", "FastAPI ile iyzico abonelik ödemesi ekle")]
    assert "python-fastapi" in names and "payments" in names
    assert "deep-work" in names  # always on
    names = [s.name for s in select("analyst", "kuaför randevu uygulaması")]
    assert "spec-writing" in names


def test_skills_for_language_and_model_notes():
    tr = skills_for("developer", "fix the failing test", "tr", None, "deepseek-chat")
    assert "Derin çalışma" in tr and "Notes for your model" in tr
    en = skills_for("developer", "fix the failing test", "en", None, "claude-opus")
    assert "Deep work" in en and len(en) < 12000
    assert model_family("ollama:qwen2.5-coder:7b") == "small-local"


def test_export_all_formats(tmp_path):
    files = export(tmp_path, names=["payments"])
    assert len(files) == 10
    skill_md = (tmp_path / "claude/tr/payments-tr/SKILL.md").read_text(encoding="utf-8")
    front = yaml.safe_load(skill_md.split("---")[1])
    assert front["name"] == "payments-tr" and "Şu konularda kullan" in front["description"]
    assert "Talimatlar" in (tmp_path / "chatgpt/tr/payments.md").read_text(encoding="utf-8")
    assert "Gem" in (tmp_path / "gemini/en/payments.md").read_text(encoding="utf-8")
    assert (tmp_path / "deepseek/en/payments.md").exists()
