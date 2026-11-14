"""Animasyon klip listesi: (isim, CMU klibi, başlangıç sn, süre sn, kategori).
Kaynak: CMU Graphics Lab Motion Capture Database (cgspeed BVH dönüşümü)."""
CLIPS = [
    # hareket
    ("bekleme",        "140_06", 2.0, 6.0, "hareket"),
    ("bekleme_2",      "141_20", 0.5, 5.0, "hareket"),
    ("yurume",         "35_01",  0.0, None, "hareket"),
    ("yurume_2",       "08_01",  0.0, None, "hareket"),
    ("kosma",          "127_03", 0.0, None, "hareket"),
    ("kosma_2",        "16_35",  0.0, None, "hareket"),
    # dövüş
    ("boks",           "13_17",  4.0, 6.0, "dovus"),
    ("boks_2",         "14_01",  6.0, 6.0, "dovus"),
    ("yumruk_serisi",  "143_23", 0.5, 6.0, "dovus"),
    ("tekme",          "143_24", 0.5, 7.0, "dovus"),
    ("on_tekme",       "135_04", 1.0, 6.0, "dovus"),
    ("ziplayan_tekme", "90_05",  0.0, None, "dovus"),
    ("dovus_kombo",    "86_01",  2.0, 8.0, "dovus"),
    # dans + jest
    ("dans_twist",     "141_12", 0.0, None, "dans"),
    ("breakdance",     "90_28",  0.0, None, "dans"),
    ("rus_dansi",      "90_30",  1.0, 8.0, "dans"),
    ("dans_donus",     "55_01",  2.0, 8.0, "dans"),
    ("makarena",       "143_35", 1.0, 8.0, "dans"),
    ("el_sallama",     "141_16", 0.0, None, "jest"),
    ("yumruk_jest",    "141_14", 0.0, None, "jest"),
    # zıplama + akrobasi
    ("ziplama",        "16_01",  0.0, None, "akrobasi"),
    ("ileri_ziplama",  "16_05",  0.0, None, "akrobasi"),
    ("ters_takla",     "88_01",  0.0, None, "akrobasi"),
    ("yan_takla",      "90_08",  0.0, None, "akrobasi"),
    ("cember_takla",   "90_02",  0.0, None, "akrobasi"),
    ("kosup_atlama",   "127_25", 0.0, None, "akrobasi"),
    ("donen_tekme",    "88_06",  0.0, None, "akrobasi"),
]
