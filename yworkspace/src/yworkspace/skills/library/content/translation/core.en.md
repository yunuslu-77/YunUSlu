- Translate meaning, not words; keep the register (formal "siz" vs informal "sen") consistent with the brand.
- Build a glossary first (product terms, UI labels, names that stay untranslated) and follow it everywhere.
- Never translate code, placeholders ({name}, %s, {{var}}), URLs, or keys in i18n files; keep plural forms and
  formatting (dates 27.10.2026 vs 10/27/2026, decimal comma vs point, ₺ position).
- Turkish specifics: vowel harmony in suffixes after variables ("{app}'a" breaks - rephrase), dotted/dotless
  i in uppercasing (İ/ı), length grows ~20-30 %: check UI fit.
- Check: back-translate a sample, compare counts of placeholders, run the app in the new language.
