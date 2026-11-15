"""Web araçları: arama, sayfa okuma, hava durumu."""
from __future__ import annotations

import httpx
from bs4 import BeautifulSoup

from .registry import P, ToolContext, tool

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) YAi-assistant"}
WMO = {0: "açık", 1: "çoğunlukla açık", 2: "parçalı bulutlu", 3: "kapalı", 45: "sisli", 48: "kırağılı sis",
       51: "hafif çisenti", 53: "çisenti", 55: "yoğun çisenti", 61: "hafif yağmur", 63: "yağmur", 65: "kuvvetli yağmur",
       66: "dondurucu yağmur", 67: "kuvvetli dondurucu yağmur", 71: "hafif kar", 73: "kar", 75: "yoğun kar",
       77: "kar taneleri", 80: "sağanak", 81: "kuvvetli sağanak", 82: "şiddetli sağanak", 85: "kar sağanağı",
       86: "yoğun kar sağanağı", 95: "gök gürültülü fırtına", 96: "dolu ile fırtına", 99: "şiddetli dolu"}


def html_to_text(html: str, limit: int = 8000) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript", "svg", "header", "footer", "nav"]):
        t.decompose()
    title = soup.title.get_text(strip=True) if soup.title else ""
    text = "\n".join(line.strip() for line in soup.get_text("\n").splitlines() if line.strip())
    return {"title": title, "text": text[:limit], "truncated": len(text) > limit}


@tool("web_search", "Google'da arama yapıp güncel bilgiyi kaynaklarıyla özetler (haber, fiyat, olay, genel bilgi).",
      "web", {"query": P(str, "Arama sorgusu")})
async def web_search(ctx: ToolContext, query: str):
    return await ctx.app.llm.search(query)


@tool("fetch_url", "Bir web sayfasını indirip metnini döner.", "web", {"url": P(str, "Sayfa adresi")})
async def fetch_url(ctx: ToolContext, url: str):
    async with httpx.AsyncClient(follow_redirects=True, timeout=20, headers=UA) as c:
        r = await c.get(url)
    if "html" not in r.headers.get("content-type", "html"):
        return {"status": r.status_code, "text": r.text[:8000]}
    return {"status": r.status_code, **html_to_text(r.text)}


@tool("get_weather", "Bir şehrin güncel hava durumu ve 3 günlük tahmini (ücretsiz Open-Meteo).", "web",
      {"city": P(str, "Şehir adı, ör. İstanbul")})
async def get_weather(ctx: ToolContext, city: str):
    async with httpx.AsyncClient(timeout=15) as c:
        g = (await c.get("https://geocoding-api.open-meteo.com/v1/search",
                         params={"name": city, "count": 1, "language": "tr"})).json()
        if not g.get("results"):
            return {"error": f"Şehir bulunamadı: {city}"}
        loc = g["results"][0]
        w = (await c.get("https://api.open-meteo.com/v1/forecast", params={
            "latitude": loc["latitude"], "longitude": loc["longitude"], "timezone": "auto", "forecast_days": 3,
            "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m,relative_humidity_2m",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max"})).json()
    cur = w.get("current", {})
    d = w.get("daily", {})
    days = [{"date": d["time"][i], "durum": WMO.get(d["weather_code"][i], "?"),
             "max": d["temperature_2m_max"][i], "min": d["temperature_2m_min"][i],
             "yağış_olasılığı": d["precipitation_probability_max"][i]} for i in range(len(d.get("time", [])))]
    return {"yer": f"{loc['name']}, {loc.get('country', '')}",
            "şimdi": {"sıcaklık": cur.get("temperature_2m"), "hissedilen": cur.get("apparent_temperature"),
                      "durum": WMO.get(cur.get("weather_code"), "?"), "rüzgar_kmh": cur.get("wind_speed_10m"),
                      "nem": cur.get("relative_humidity_2m")},
            "tahmin": days}
