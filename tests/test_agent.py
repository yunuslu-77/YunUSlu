import json

from bot.tools import REGISTRY
from bot.tools.registry import P, tool


@tool("test_dangerous", "Test için onay isteyen araç", "core", {"x": P(int, "sayı")}, approval=True,
      summary=lambda a: f"Tehlikeli işlem x={a['x']}")
async def _dangerous(ctx, x):
    ctx.app.db.set("dangerous_ran", x)
    return {"done": x}


async def test_simple_reply_and_history(app, llm):
    llm.push("Merhaba! 👋")
    out = await app.agent.handle_user(42, ["selam"], "selam")
    assert out == "Merhaba! 👋"
    hist = app.db.recent_messages(42, 10)
    assert [h["role"] for h in hist] == ["user", "model"]
    # ikinci mesajda geçmiş modele gider
    llm.push("Tekrar merhaba")
    await app.agent.handle_user(42, ["nasılsın"], "nasılsın")
    assert len(llm.calls[-1]["contents"]) == 3
    # sistem talimatı ad, kural ve saat içerir
    assert "YAi" in llm.calls[-1]["system"] and "ŞU AN" in llm.calls[-1]["system"]


async def test_tool_loop_and_memory(app, llm):
    llm.push([("remember", {"fact": "Kullanıcı İzmir'de yaşıyor"}), ("get_datetime", {})], "Kaydettim")
    out = await app.agent.handle_user(42, ["İzmir'de yaşıyorum"], "İzmir'de yaşıyorum")
    assert out == "Kaydettim"
    assert app.db.memories()[0]["fact"] == "Kullanıcı İzmir'de yaşıyor"
    # araç sonuçları modele geri gönderildi
    tool_turn = llm.calls[1]["contents"][-1]
    names = [p.function_response.name for p in tool_turn.parts]
    assert names == ["remember", "get_datetime"]
    # hafıza bir sonraki sistem talimatında görünür
    llm.push("ok")
    await app.agent.handle_user(42, ["test"], "test")
    assert "İzmir" in llm.calls[-1]["system"]
    # denetim kaydı tutuldu
    assert app.db.one("SELECT COUNT(*) n FROM audit")["n"] == 2


async def test_unknown_tool_and_bad_args(app, llm):
    llm.push([("yok_boyle_arac", {}), ("remember", {"wrong": 1})], "hata gördüm")
    await app.agent.handle_user(42, ["x"], "x")
    results = [p.function_response.response["result"] for p in llm.calls[1]["contents"][-1].parts]
    assert "Bilinmeyen araç" in results[0]["error"]
    assert "Geçersiz parametre" in results[1]["error"]


async def test_approval_flow(app, llm):
    llm.push([("test_dangerous", {"x": 7})], "Onay butonuna bas lütfen")
    out = await app.agent.handle_user(42, ["yap"], "yap")
    assert "Onay" in out
    approvals = [s for s in app.notifier.sent if s[0] == "approval"]
    assert approvals and "x=7" in approvals[0][2]
    assert app.db.get("dangerous_ran") is None  # henüz çalışmadı
    aid = approvals[0][1]
    # aynı istek tekrar gelirse yeni onay açılmaz
    llm.push([("test_dangerous", {"x": 7})], "bekliyorum")
    await app.agent.handle_user(42, ["yap"], "yap")
    assert len([s for s in app.notifier.sent if s[0] == "approval"]) == 1

    llm.push("✅ İşlem yapıldı")
    out = await app.agent.resolve_approval(aid, True)
    assert out == "✅ İşlem yapıldı"
    assert app.db.get("dangerous_ran") == 7
    assert "ONAYLADI" in llm.calls[-1]["contents"][-1].parts[0].text
    assert "zaten" in await app.agent.resolve_approval(aid, True)


async def test_approval_denied(app, llm):
    llm.push([("test_dangerous", {"x": 1})], "bekliyorum")
    await app.agent.handle_user(42, ["yap"], "yap")
    aid = [s for s in app.notifier.sent if s[0] == "approval"][0][1]
    assert "İptal" in await app.agent.resolve_approval(aid, False)
    assert app.db.get("dangerous_ran") is None


async def test_delegation_and_custom_agent(app, llm):
    llm.push([("create_agent", {"name": "Finans", "role": "Bütçe takibi", "instructions": "Harcamaları izle",
                                "groups": ["google", "pages", "olmayan"]})], "Oluşturdum")
    await app.agent.handle_user(42, ["finans ajanı yap"], "x")
    fin = app.agents.get("finans")
    assert fin.role == "Bütçe takibi" and "olmayan" not in fin.groups and "core" in fin.groups

    llm.push([("delegate_to_agent", {"agent": "arastirmaci", "task": "Konu X'i araştır"})],
             "araştırma sonucu", "Araştırmacı şunu buldu")
    out = await app.agent.handle_user(42, ["araştır"], "araştır")
    assert out == "Araştırmacı şunu buldu"
    sub = llm.calls[-2]
    assert sub["tier"] == "smart" and "arastirmaci" in sub["system"]
    sub_tools = {t["name"] for t in sub["tools"]}
    assert "browser_open" in sub_tools and "gmail_send" not in sub_tools


async def test_tools_per_agent(app, llm):
    llm.push("ok")
    await app.agent.handle_user(42, ["x"], "x")
    names = {t["name"] for t in llm.calls[-1]["tools"]}
    assert {"gmail_send", "phone_sms_send", "create_schedule", "delegate_to_agent"} <= names
    assert "phone_tap" not in names and "run_shell" not in names  # operatöre ait
    for t in llm.calls[-1]["tools"]:
        json.dumps(t)


async def test_max_steps(app, llm):
    app.cfg.max_tool_steps = 3
    llm.push(*[[("get_datetime", {})]] * 5)
    out = await app.agent.handle_user(42, ["döngü"], "döngü")
    assert "çok fazla adım" in out


async def test_budget_exceeded_message(app, llm):
    app.budget.record("gemini-3.8-flash", 10_000_000, 0)
    from bot.llm import LLM
    real = LLM(app.cfg, app.budget)
    app.llm = real
    out = await app.agent.handle_user(42, ["x"], "x")
    assert "bütçe" in out.lower()


def test_registry_complete():
    must = ["gmail_search", "gmail_send", "calendar_create", "drive_search", "docs_create", "sheets_append",
            "web_search", "get_weather", "create_schedule", "set_reminder", "save_skill", "create_agent",
            "browser_open", "run_shell", "phone_sms_send", "phone_location", "phone_set_alarm", "phone_tasker",
            "phone_screen_look", "phone_tap", "create_page", "set_voice_replies"]
    for m in must:
        assert m in REGISTRY, m
    for name in ["gmail_send", "phone_sms_send", "phone_call", "run_shell", "phone_screen_control", "save_skill"]:
        assert REGISTRY[name].needs_approval({"command": "x", "number": "1", "text": "x"}), name


async def test_browser_tools_hidden_without_playwright(app, llm, monkeypatch):
    monkeypatch.setattr(type(app.browser), "available", property(lambda self: False))
    llm.push("ok")
    await app.agent.run_task(42, "araştır", agent="arastirmaci")
    names = {t["name"] for t in llm.calls[-1]["tools"]}
    assert "browser_open" not in names and "web_search" in names
