"""Last resort: read a window region with OCR (Tesseract). Unreliable for code; the user is warned."""

from __future__ import annotations


def read_window(rect: tuple[int, int, int, int]) -> str:
    import pyautogui
    import pytesseract
    x, y, w, h = rect
    img = pyautogui.screenshot(region=(x, y, w, h))
    return pytesseract.image_to_string(img)
