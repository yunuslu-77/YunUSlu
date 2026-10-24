# YunUSlu Skills

> Her yapay zekâ için açık kaynaklı, Türkçe + İngilizce skill ve özel prompt kütüphanesi.
> An open-source library of skills and custom prompts for every AI, in Turkish + English.

## Yapı / Structure

```
skills/
├── _template/                  # Yeni skill için şablon / template for new skills
├── software-development/       # Yazılım geliştirme / Software development
├── business-marketing/         # İş ve pazarlama / Business & marketing
├── education-life/             # Eğitim ve günlük yaşam / Education & daily life
├── yunuslu-products/           # YunUSlu ürünleri (yOffice, yDocs, ...) / YunUSlu products
└── general/                    # Genel / General
```

Her skill kendi klasöründe, her yapay zekâ ve her dil için ayrı sürümle durur:
Each skill lives in its own folder with a separate version per AI and per language:

```
<kategori>/<skill-adi>/
├── README.md            # Kısa tanım (TR + EN) / Short description
├── claude/
│   ├── tr/SKILL.md      # Claude skill (Türkçe)
│   └── en/SKILL.md      # Claude skill (English)
├── chatgpt/
│   ├── tr.md            # Custom GPT talimatları (Türkçe)
│   └── en.md            # Custom GPT instructions (English)
└── gemini/
    ├── tr.md            # Gem talimatları (Türkçe)
    └── en.md            # Gem instructions (English)
```

## Nasıl kullanılır / How to use

| AI | Türkçe | English |
|---|---|---|
| **Claude** | `claude/tr/` klasörünü Claude'a skill olarak yükle (Ayarlar → Yetenekler) ya da `~/.claude/skills/` altına kopyala. | Upload the `claude/en/` folder as a skill (Settings → Capabilities) or copy it under `~/.claude/skills/`. |
| **ChatGPT** | Yeni bir GPT oluştur, `chatgpt/tr.md` içindeki alanları ilgili kutulara yapıştır. | Create a new GPT and paste the fields from `chatgpt/en.md` into the matching boxes. |
| **Gemini** | Yeni bir Gem oluştur, `gemini/tr.md` içindeki talimatları yapıştır. | Create a new Gem and paste the instructions from `gemini/en.md`. |

## Kurallar / Conventions

- Klasör adları İngilizce, küçük harf ve tire ile: `code-review`, `social-media-post`.
  Folder names are English, lowercase, hyphenated.
- Claude skill adları: İngilizce sürümde `skill-adi`, Türkçe sürümde `skill-adi-tr` (ikisi birlikte yüklenebilsin diye).
  Claude skill names: `skill-name` for English, `skill-name-tr` for Turkish, so both can be installed together.
- Yeni skill eklerken `_template/` klasörünü kopyala.
  Copy `_template/` when adding a new skill.

## Skill listesi / Skill index

| Kategori | Skill | Açıklama |
|---|---|---|
| software-development | [code-review](software-development/code-review/) | Kodu hata, güvenlik ve okunabilirlik açısından inceler. / Reviews code for bugs, security and readability. |
