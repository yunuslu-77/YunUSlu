"""Tüm araç modüllerini yükler (içe aktarınca REGISTRY dolar)."""
from . import browser, computer, core, google_ws, phone, web  # noqa: F401
from .registry import REGISTRY, Tool, ToolContext, tools_for_groups  # noqa: F401
