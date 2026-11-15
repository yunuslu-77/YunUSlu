"""Gerçek Gemini cevap nesneleriyle LLM sarmalayıcısı (ağ yok, istemci taklit)."""
from types import SimpleNamespace

from google.genai import types

from bot.llm import LLM


def make_resp(parts, prompt=1000, out=50, cached=0, thoughts=10):
    return types.GenerateContentResponse(
        candidates=[types.Candidate(content=types.Content(role="model", parts=parts))],
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=prompt, candidates_token_count=out, cached_content_token_count=cached,
            thoughts_token_count=thoughts))


class FakeModels:
    def __init__(self, resps):
        self.resps, self.requests = list(resps), []

    async def generate_content(self, model, contents, config):
        self.requests.append((model, contents, config))
        r = self.resps.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def llm_with(app, resps):
    llm = LLM(app.cfg, app.budget)
    models = FakeModels(resps)
    llm.client = SimpleNamespace(aio=SimpleNamespace(models=models))
    return llm, models


async def test_generate_tool_calls_and_usage(app):
    resp = make_resp([types.Part(function_call=types.FunctionCall(name="get_weather", args={"city": "İzmir"}))])
    llm, models = llm_with(app, [resp])
    tools = [{"name": "get_weather", "description": "hava", "parameters": {"type": "object", "properties": {
        "city": {"type": "string"}}, "required": ["city"]}}]
    r = await llm.generate("fast", ["hava?"], "sistem", tools)
    assert r.calls[0].name == "get_weather" and r.calls[0].args == {"city": "İzmir"}
    model, _, cfg = models.requests[0]
    assert model == app.cfg.model_fast and cfg.automatic_function_calling.disable
    assert cfg.tools[0].function_declarations[0].name == "get_weather"
    row = app.db.one("SELECT * FROM usage")
    assert row["input_tokens"] == 1000 and row["output_tokens"] == 60


async def test_generate_text_skips_thoughts_and_retries(app):
    resp = make_resp([types.Part(text="düşünce", thought=True), types.Part(text="Cevap")], cached=800)
    llm, models = llm_with(app, [Exception("429 RESOURCE_EXHAUSTED"), resp])
    import bot.llm as m
    orig = m.asyncio.sleep

    async def nosleep(s):
        return None
    m.asyncio.sleep = nosleep
    try:
        r = await llm.generate("smart", ["x"], "s")
    finally:
        m.asyncio.sleep = orig
    assert r.text == "Cevap" and len(models.requests) == 2
    cost = app.db.one("SELECT cost FROM usage")["cost"]
    expected = (200 * 1.5 + 800 * 0.15 + 60 * 7.5) / 1e6
    assert abs(cost - expected) < 1e-12


async def test_search_sources(app):
    resp = make_resp([types.Part(text="Özet")])
    resp.candidates[0].grounding_metadata = types.GroundingMetadata(grounding_chunks=[
        types.GroundingChunk(web=types.GroundingChunkWeb(uri="https://a.com", title="A"))])
    llm, models = llm_with(app, [resp])
    r = await llm.search("dolar kuru")
    assert r == {"summary": "Özet", "sources": [{"title": "A", "url": "https://a.com"}]}
    assert models.requests[0][2].tools[0].google_search is not None
