# Gerçekçi Karakter (çalışma sürüyor)

Akdenizli, sokak stili erkek karakter: MakeHuman/MPFB verileri + kendi yükleyicim (dışarıdan kod çalıştırılmaz),
tel tel saç/sakal (Cycles), CMU mocap animasyonları.

| Dosya | Görev |
|---|---|
| `mh.py` | base mesh, şekil hedefleri, kıyafet uydurma (mhclo), iskelet eklemleri |
| `build.py` | karakteri kurar → `.blend` |
| `groom.py` | saç (üst + fade), sakal, deri maskeleri |
| `textures.py` | kıyafet dokusunu yeniden renklendirir (deri ceket, koyu kot) |
| `anim.py` | BVH → iskelet hareket aktarımı (ayak-zemin oturtmalı) |
| `clips.py` | animasyon listesi |
| `render_still.py`, `render_anim.py`, `preview_clips.py` | render |
| `export.py` | `.blend`, FBX, GLB dışa aktarma |
