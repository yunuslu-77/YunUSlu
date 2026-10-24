import json
from types import SimpleNamespace

import httpx

from yworkspace.core import Workspace
from yworkspace.engine.loop import TEXT, AgentLoop
from yworkspace.models import Message, ToolCall, get_profile
from yworkspace.models.base import parse_arguments
from yworkspace.models.claude import ClaudeProvider
from yworkspace.models.gemini import GeminiProvider
from yworkspace.models.openai_compat import OpenAICompatProvider
from yworkspace.models.scripted import ScriptedProvider, say
from yworkspace.protocol import text_protocol
from yworkspace.tools.builtin import build_registry
from yworkspace.tools.registry import gemini_schema


def reg(tmp_path):
    ws = Workspace(tmp_path / "p")
    return ws, build_registry(ws)


def test_registry_formats_and_coercion(tmp_path):
    ws, r = reg(tmp_path)
    assert {t["function"]["name"] for t in r.to_openai()} >= {"read", "edit", "create"}
    assert r.to_anthropic()[0]["input_schema"]["type"] == "object"
    g = r.to_gemini()[0]["functionDeclarations"][0]["parameters"]
    assert g["type"] == "OBJECT" and "additionalProperties" not in g
    ws.create("a.txt", "\n".join(map(str, range(50))) + "\n")
    res = r.call("read", {"path": "a.txt", "offset": "10", "limit": "2", "bogus": 1})
    assert "lines 10-11" in res.text and "ignored unknown arguments: bogus" in res.text
    assert r.call("nope", {}).is_error
    assert "missing_argument" in r.call("read", {}).text


def test_gemini_schema_nested():
    s = gemini_schema({"type": "object", "properties": {"x": {"type": "array", "items": {"type": "object",
                       "properties": {"a": {"type": "string"}}, "additionalProperties": False}}},
                       "additionalProperties": False})
    assert s["properties"]["x"]["items"]["type"] == "OBJECT"
    assert "additionalProperties" not in s["properties"]["x"]["items"]


def test_parse_arguments_repairs():
    assert parse_arguments('{"a": 1,}') == ({"a": 1}, None)
    assert parse_arguments('```json\n{"a": 1}\n```')[0] == {"a": 1}
    assert parse_arguments('{"a": {"b": 1}')[0] == {"a": {"b": 1}}
    assert parse_arguments("not json")[1] == "not json"


def test_text_protocol_parse(tmp_path):
    _, r = reg(tmp_path)
    text = '''I will read it.
<<<yw:read path="src/a.py" offset='5' limit=10>>>
<<<yw:edit path="src/a.py">>>
<<<find
    return a - b
===replace
    return a + b
<<<find
x = 1
===replace
x = 2
>>>end
<<<yw:create path="new.md">>>
# Title
<<<yw:not-a-call-inside-file>>>
>>>end
<<<yw:glob pattern="*.py">>>
'''
    p = text_protocol.parse(text, r)
    names = [c.name for c in p.calls]
    assert names == ["read", "multi_edit", "create", "glob"]
    assert p.calls[0].arguments == {"path": "src/a.py", "offset": "5", "limit": "10"}
    assert p.calls[1].arguments["edits"][0] == {"find": "    return a - b", "replace": "    return a + b"}
    assert "not-a-call-inside-file" in p.calls[2].arguments["content"]
    assert p.text == "I will read it."


def test_text_protocol_tolerance(tmp_path):
    ws = Workspace(tmp_path / "s")
    from yworkspace.sandbox import LocalSandbox
    r = build_registry(ws, LocalSandbox(ws.root))
    p = text_protocol.parse("<<<yw:run>>>\n```bash\necho hi\n```\n", r)
    assert p.calls[0].arguments["command"] == "echo hi" and p.errors
    p = text_protocol.parse('<<<yw:run command="ls -la">>>\nThen I wait.', r)
    assert p.calls[0].arguments["command"] == "ls -la" and p.text == "Then I wait."
    p = text_protocol.parse('Here:\n```json\n{"tool": "glob", "args": {"pattern": "*.md"}}\n```', r)
    assert p.calls[0].name == "glob"
    assert "Unknown tool" in text_protocol.parse("<<<yw:fly>>>", r).errors[0]
    instr = text_protocol.instructions(r)
    assert "<<<yw:run>>>" in instr and "<<<find" in instr


def test_openai_compat_request_and_parse():
    seen = {}

    def handler(request: httpx.Request):
        seen["body"] = json.loads(request.content)
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"model": "deepseek-chat", "choices": [{"finish_reason": "tool_calls",
            "message": {"content": None, "tool_calls": [{"id": "c1", "type": "function", "function": {
                "name": "read", "arguments": '{"path": "a.py",}'}}]}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 7, "prompt_cache_hit_tokens": 40}})

    p = OpenAICompatProvider("deepseek-chat", "https://api.deepseek.com", "sk-test",
                             transport=httpx.MockTransport(handler))
    msgs = [Message("system", "sys"), Message("user", "hi"),
            Message("assistant", "", [ToolCall("glob", {"pattern": "*"}, "c0")]),
            Message("tool", "a.py", tool_call_id="c0", name="glob")]
    resp = p.chat(msgs, [{"type": "function", "function": {"name": "read"}}])
    assert seen["auth"] == "Bearer sk-test"
    assert seen["body"]["messages"][2]["tool_calls"][0]["function"]["name"] == "glob"
    assert seen["body"]["messages"][3] == {"role": "tool", "tool_call_id": "c0", "content": "a.py"}
    assert resp.stop_reason == "tool_calls" and resp.message.tool_calls[0].arguments == {"path": "a.py"}
    assert resp.usage.cached_input_tokens == 40


def test_openai_compat_retries_429():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, headers={"retry-after": "0"}, text="slow down")
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}]})

    p = OpenAICompatProvider("m", "http://x", transport=httpx.MockTransport(handler))
    assert p.chat([Message("user", "hi")]).message.content == "ok" and calls["n"] == 2


def test_gemini_request_and_parse():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["key"] = request.headers.get("x-goog-api-key")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"candidates": [{"finishReason": "STOP", "content": {"parts": [
            {"text": "Reading."}, {"functionCall": {"name": "read", "args": {"path": "a.py"}},
                                   "thoughtSignature": "sig"}]}}],
            "usageMetadata": {"promptTokenCount": 50, "candidatesTokenCount": 5}})

    p = GeminiProvider("gemini-2.5-flash", "gk", transport=httpx.MockTransport(handler))
    resp = p.chat([Message("system", "be good"), Message("user", "hi")], [{"functionDeclarations": []}])
    assert seen["url"].endswith("/models/gemini-2.5-flash:generateContent") and seen["key"] == "gk"
    assert seen["body"]["systemInstruction"]["parts"][0]["text"] == "be good"
    call = resp.message.tool_calls[0]
    assert call.name == "read" and resp.stop_reason == "tool_calls"
    msgs = [Message("user", "hi"), resp.message, Message("tool", "content", tool_call_id=call.id, name="read")]
    p.chat(msgs)
    contents = seen["body"]["contents"]
    assert contents[1]["parts"][1]["thoughtSignature"] == "sig"
    assert contents[2]["parts"][0]["functionResponse"]["name"] == "read"


def test_claude_conversion_and_parse():
    captured = {}

    class Blocks:
        def __init__(self, **kw):
            self.__dict__.update(kw)

        def model_dump(self, exclude_none=True):
            return dict(self.__dict__)

    def create(**kw):
        captured.update(kw)
        return SimpleNamespace(content=[Blocks(type="thinking", thinking="", signature="s"),
                                        Blocks(type="text", text="ok"),
                                        Blocks(type="tool_use", id="tu1", name="read", input={"path": "a"})],
                               stop_reason="tool_use", model="claude-opus-5-5",
                               usage=SimpleNamespace(input_tokens=9, output_tokens=3, cache_read_input_tokens=2))

    fake = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create)),
                           messages=SimpleNamespace(create=create))
    p = ClaudeProvider(client=fake)
    msgs = [Message("system", "sys"), Message("user", "hi"),
            Message("assistant", "", [ToolCall("a", {}, "x1"), ToolCall("b", {}, "x2")]),
            Message("tool", "r1", tool_call_id="x1", name="a"), Message("tool", "r2", tool_call_id="x2", name="b",
                                                                        is_error=True)]
    resp = p.chat(msgs, [{"name": "read"}])
    assert captured["system"] == "sys" and captured["fallbacks"] == "default"
    assert "temperature" not in captured
    last = captured["messages"][-1]
    assert last["role"] == "user" and [b["tool_use_id"] for b in last["content"]] == ["x1", "x2"]
    assert last["content"][1]["is_error"] is True
    assert resp.message.tool_calls[0].id == "tu1" and resp.stop_reason == "tool_calls"
    p.chat(msgs + [resp.message])
    assert captured["messages"][-1]["content"][0]["type"] == "thinking"


def test_profiles():
    assert get_profile("deepseek-chat").base_url == "https://api.deepseek.com"
    assert get_profile("ollama:llama3.1:8b").model == "llama3.1:8b"


def test_loop_native_edits_real_file(tmp_path):
    ws, r = reg(tmp_path)
    ws.create("calc.py", "def add(a, b):\n    return a - b\n")
    ws._seen.clear()
    prov = ScriptedProvider([
        say("Let me look.", ("read", {"path": "calc.py"})),
        say("", ("edit", {"path": "calc.py", "find": "return a - b", "replace": "return a + b"})),
        say("Fixed the bug."),
    ])
    res = AgentLoop(prov, r).run([Message("system", "s"), Message("user", "fix add")])
    assert res.stop == "finished" and res.final_text == "Fixed the bug."
    assert (ws.root / "calc.py").read_text() == "def add(a, b):\n    return a + b\n"
    assert res.usage.input_tokens == 30


def test_loop_text_mode_with_recovery(tmp_path):
    ws, r = reg(tmp_path)
    ws.create("calc.py", "def add(a, b):\n        return a - b\n")
    ws._seen.clear()
    prov = ScriptedProvider([
        say('<<<yw:read path="calc.py">>>'),
        say('<<<yw:edit path="calc.py">>>\n<<<find\n    return a - b\n===replace\n    return a + b\n>>>end'),
        lambda msgs: say('<<<yw:edit path="calc.py">>>\n<<<find\n        return a - b\n===replace\n'
                         '        return a + b\n>>>end') if "Did you mean lines 2-2" in msgs[-1].content else say("??"),
        say("Done."),
    ], supports_tools=False)
    loop = AgentLoop(prov, r)
    assert loop.mode == TEXT
    res = loop.run([Message("system", "s"), Message("user", "fix")])
    assert res.stop == "finished"
    assert "return a + b" in (ws.root / "calc.py").read_text()
    assert "yWorkspace text protocol" in prov.seen[0][0].content


def test_loop_idle_nudge(tmp_path):
    _, r = reg(tmp_path)
    prov = ScriptedProvider([say("I think it's done."), say("Now truly done.")])
    nudges = iter(["Tests have not been run. Continue.", None])
    res = AgentLoop(prov, r, on_idle=lambda m: next(nudges)).run([Message("user", "x")])
    assert res.steps == 2 and res.final_text == "Now truly done."
