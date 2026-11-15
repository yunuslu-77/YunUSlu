import json
import sys
from pathlib import Path

import pytest
from google.genai import types

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot.app import App  # noqa: E402
from bot.config import Config  # noqa: E402
from bot.llm import LLMResult, ToolCall  # noqa: E402


class FakeLLM:
    """Sırayla önceden yazılmış cevaplar döner. Cevap: str (metin) veya [(araç, args), ...]."""

    def __init__(self, script=None):
        self.script = list(script or [])
        self.calls = []
        self.simple_answers = []

    def push(self, *items):
        self.script.extend(items)

    async def generate(self, tier, contents, system, tools=None, purpose=""):
        self.calls.append({"tier": tier, "contents": contents, "system": system, "tools": tools})
        item = self.script.pop(0) if self.script else "tamam"
        if isinstance(item, str):
            return LLMResult(text=item, content=types.Content(role="model", parts=[types.Part.from_text(text=item)]))
        calls = [ToolCall(name, args, f"id{i}") for i, (name, args) in enumerate(item)]
        content = types.Content(role="model", parts=[
            types.Part(function_call=types.FunctionCall(name=c.name, args=c.args)) for c in calls])
        return LLMResult(text="", calls=calls, content=content)

    async def simple(self, prompt, tier="fast", system="", json_mode=False, purpose=""):
        self.calls.append({"simple": prompt})
        return self.simple_answers.pop(0) if self.simple_answers else json.dumps({})

    async def search(self, query):
        return {"summary": f"özet: {query}", "sources": []}

    async def vision(self, image, question, mime="image/png", tier="fast"):
        return f"görüntü {len(image)} bayt"

    async def tts(self, text):
        return b"\x00\x00" * 2400


@pytest.fixture
def cfg(tmp_path):
    c = Config(data_dir=tmp_path, owner_id=42, dashboard_token="d" * 20, phone_token="p" * 20,
               browser_executable="/opt/pw-browsers/chromium")
    c.workspace.mkdir(parents=True, exist_ok=True)
    return c


@pytest.fixture
def llm():
    return FakeLLM()


@pytest.fixture
def app(cfg, llm):
    return App(cfg, llm=llm)
