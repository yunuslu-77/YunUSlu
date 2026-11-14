"""Kıyafet dokusunu yeniden renklendirir: siyah deri ceket, koyu gömlek, koyu indigo kot.
python3 -I karakter/textures.py <kaynak_diffuse.png> <cikti_klasoru>
"""
import os, sys
import numpy as np
from PIL import Image, ImageFilter

src, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
im = Image.open(src).convert("RGBA")
a = np.asarray(im).astype(np.float32) / 255.0
rgb, alpha = a[..., :3], a[..., 3:]
hsv = np.asarray(im.convert("RGB").convert("HSV")).astype(np.float32) / 255.0
h, s, v = hsv[..., 0] * 360, hsv[..., 1], hsv[..., 2]
lum = rgb @ np.array([0.299, 0.587, 0.114])

def close(m, grow, shrink):
    im_ = Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(grow)).filter(ImageFilter.MinFilter(shrink))
    return np.asarray(im_) > 127

jeans = (h > 180) & (h < 250) & (s > 0.18)
jeans = close(jeans, 31, 25) & (lum > 0.03)
shirt = ((h < 25) | (h > 320)) & (s > 0.25)
# çizgili gömlek bölgesini genişlet (çizgiler arasındaki koyu pikseller de gömlek)
shirt = close(shirt, 41, 35) & ~jeans & (lum > 0.03)
jacket = (lum > 0.08) & ~jeans & ~shirt

res = rgb.copy()
# ceket: siyah deri — ayrıntıyı (dikiş, kırışık) koru, tonu kahve-siyaha çek
d = (lum - np.median(lum[jacket])) if jacket.any() else lum
leather = np.array([0.045, 0.038, 0.034])
res[jacket] = np.clip(leather + d[jacket][:, None] * np.array([0.55, 0.5, 0.48]), 0, 1)
# gömlek: koyu kömür gri, çizgiler hafif ton farkı olarak kalsın
g = lum[shirt]
res[shirt] = np.clip(np.array([0.09, 0.09, 0.095]) + (g[:, None] - g.mean()) * 0.18, 0, 1)
# kot: koyu indigo
jl = lum[jeans]
indigo = np.array([0.035, 0.05, 0.11])
res[jeans] = np.clip(indigo + (jl[:, None] - jl.mean()) * np.array([0.35, 0.42, 0.65]), 0, 1)

Image.fromarray((np.concatenate([res, alpha], -1) * 255).astype(np.uint8)).save(os.path.join(out, "kiyafet_diffuse.png"))
rough = np.full(lum.shape, 0.75, np.float32)
rough[jacket] = 0.5 + (lum[jacket] - lum[jacket].mean()) * 0.8  # deri: daha parlak
rough[shirt] = 0.8
rough[jeans] = 0.85
Image.fromarray((np.clip(rough, 0, 1) * 255).astype(np.uint8)).save(os.path.join(out, "kiyafet_rough.png"))
print("ceket", jacket.mean(), "gomlek", shirt.mean(), "kot", jeans.mean())
