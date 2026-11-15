"""Gemini API sarmalayıcısı: araç çağırma, maliyet kaydı, arama, görme, ses."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from google import genai
from google.genai import types

from .budget import Budget
from .config import Config

log = logging.getLogger(__name__)


@dataclass
class ToolCall:
    name: str
    args: dict
    id: str | None = None


@dataclass
class LLMResult:
    text: str
    calls: list[ToolCall] = field(default_factory=list)
    content: Any = None  # modelin ham cevabı (geçmişe eklemek için)
    model: str = ""


class LLM:
    def __init__(self, cfg: Config, budget: Budget):
        self.cfg = cfg
        self.budget = budget
        self.client = genai.Client(api_key=cfg.gemini_api_key) if cfg.gemini_api_key else None

    def _require(self):
        if not self.client:
            raise RuntimeError("GEMINI_API_KEY ayarlı değil (.env dosyasına ekle).")
        return self.client

    async def _call(self, model: str, contents, config, purpose: str):
        client = self._require()
        last = None
        for attempt in range(3):
            try:
                resp = await client.aio.models.generate_content(model=model, contents=contents, config=config)
                break
            except Exception as e:  # ağ / 429 / 5xx için tekrar dene
                last = e
                msg = str(e)
                if any(c in msg for c in ("429", "500", "503", "UNAVAILABLE", "RESOURCE_EXHAUSTED")) and attempt < 2:
                    await asyncio.sleep(2 * (attempt + 1))
                    continue
                raise
        else:  # pragma: no cover
            raise last
        u = resp.usage_metadata
        if u:
            out = (u.candidates_token_count or 0) + (u.thoughts_token_count or 0)
            self.budget.record(model, u.prompt_token_count or 0, out, purpose, u.cached_content_token_count or 0)
        return resp

    async def generate(self, tier: str, contents: list, system: str, tools: list[dict] | None = None,
                       purpose: str = "sohbet") -> LLMResult:
        model = self.budget.choose_model(tier)
        cfg = types.GenerateContentConfig(
            system_instruction=system,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        if tools:
            cfg.tools = [types.Tool(function_declarations=[
                types.FunctionDeclaration(name=t["name"], description=t["description"],
                                          parameters_json_schema=t["parameters"]) for t in tools])]
        resp = await self._call(model, contents, cfg, purpose)
        calls = [ToolCall(fc.name, dict(fc.args or {}), fc.id) for fc in (resp.function_calls or [])]
        content = resp.candidates[0].content if resp.candidates else None
        text = ""
        if content and content.parts:
            text = "".join(p.text for p in content.parts if getattr(p, "text", None) and not getattr(p, "thought", False))
        return LLMResult(text=text.strip(), calls=calls, content=content, model=model)

    async def simple(self, prompt: str, tier: str = "fast", system: str = "", json_mode: bool = False,
                     purpose: str = "yardımcı") -> str:
        model = self.budget.choose_model(tier)
        cfg = types.GenerateContentConfig(system_instruction=system or None)
        if json_mode:
            cfg.response_mime_type = "application/json"
        resp = await self._call(model, prompt, cfg, purpose)
        return (resp.text or "").strip()

    async def search(self, query: str) -> dict:
        """Google Arama ile desteklenmiş cevap + kaynaklar."""
        model = self.budget.choose_model("fast")
        cfg = types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())])
        resp = await self._call(model, f"Şunu web'de araştır ve kısa, doğru bir özet ver (Türkçe): {query}", cfg, "arama")
        self.budget.record_search()
        sources = []
        try:
            gm = resp.candidates[0].grounding_metadata
            for ch in (gm.grounding_chunks or [])[:8]:
                if ch.web:
                    sources.append({"title": ch.web.title, "url": ch.web.uri})
        except (AttributeError, IndexError, TypeError):
            pass
        return {"summary": (resp.text or "").strip(), "sources": sources}

    async def vision(self, image: bytes, question: str, mime: str = "image/png", tier: str = "fast") -> str:
        model = self.budget.choose_model(tier)
        contents = [types.Content(role="user", parts=[types.Part.from_bytes(data=image, mime_type=mime),
                                                      types.Part.from_text(text=question)])]
        resp = await self._call(model, contents, types.GenerateContentConfig(), "görme")
        return (resp.text or "").strip()

    async def tts(self, text: str) -> bytes:
        """Metni sese çevirir. 24 kHz, 16-bit mono PCM döner."""
        model = self.cfg.model_tts
        self.budget.choose_model("fast")  # limit kontrolü
        cfg = types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=self.cfg.tts_voice))))
        resp = await self._call(model, text, cfg, "ses")
        return resp.candidates[0].content.parts[0].inline_data.data


def user_content(parts: list) -> types.Content:
    """Metin, (bytes, mime) ikilileri veya Part listesinden kullanıcı mesajı oluşturur."""
    out = []
    for p in parts:
        if isinstance(p, str):
            out.append(types.Part.from_text(text=p))
        elif isinstance(p, tuple):
            out.append(types.Part.from_bytes(data=p[0], mime_type=p[1]))
        else:
            out.append(p)
    return types.Content(role="user", parts=out)


def model_content(text: str) -> types.Content:
    return types.Content(role="model", parts=[types.Part.from_text(text=text)])


def tool_results_content(results: list[tuple[str, Any]]) -> types.Content:
    return types.Content(role="user", parts=[
        types.Part.from_function_response(name=name, response={"result": res}) for name, res in results])
