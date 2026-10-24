"""Turkish / English interface strings. Add a language by adding a column."""

from __future__ import annotations

STRINGS: dict[str, dict[str, str]] = {
    "tagline": {"tr": "her yapay zekâya tam bir geliştirme ortamı",
                "en": "a full working environment for every AI"},
    "help_init": {"tr": "yeni proje klasörü oluştur", "en": "create a project folder"},
    "help_do": {"tr": "bir hedefi baştan sona yaptır (Derin Çalışma Motoru)",
                "en": "get a goal done end to end (Deep Work Engine)"},
    "help_manual": {"tr": "elle mod: herhangi bir sohbet botuyla kopyala-yapıştır çalış",
                    "en": "manual mode: work with any chatbot by copy and paste"},
    "help_tools": {"tr": "araçları listele", "en": "list tools"},
    "help_call": {"tr": "bir aracı doğrudan çalıştır", "en": "call a tool directly"},
    "help_models": {"tr": "modelleri ve anahtar durumunu göster", "en": "show models and key status"},
    "help_config": {"tr": "ayarları göster veya değiştir", "en": "show or change settings"},
    "help_key": {"tr": "API anahtarını güvenle kaydet", "en": "store an API key securely"},
    "help_status": {"tr": "projenin durumunu göster", "en": "show project status"},
    "help_doctor": {"tr": "sistem sağlığını kontrol et", "en": "check system health"},
    "home_dir": {"tr": "Ayar klasörü", "en": "Settings folder"},
    "init_done": {"tr": "Proje hazır: {path}", "en": "Project ready: {path}"},
    "stopped": {"tr": "Durduruldu. Kaldığı yerden devam etmek için aynı komutu tekrar çalıştır.",
                "en": "Stopped. Run the same command again to continue where it left off."},
    "approve_spec": {"tr": "Proje tanımı onayı", "en": "Approve the specification"},
    "approve_plan": {"tr": "Plan onayı", "en": "Approve the plan"},
    "approve_tool": {"tr": "İşlem onayı", "en": "Approve this action"},
    "approve_deploy": {"tr": "Yayına alma onayı", "en": "Approve deployment"},
    "approve_prompt": {"tr": "Onaylıyor musun? [Enter=evet / h=hayır / ya da ne değişsin yaz]: ",
                       "en": "Approve? [Enter=yes / n=no / or type what to change]: "},
    "key_saved": {"tr": "{name} kaydedildi ({where}).", "en": "{name} saved ({where})."},
    "manual_intro": {"tr": "ELLE MOD: Aşağıdaki mesajı yapay zekâ sohbetine yapıştır.",
                     "en": "MANUAL MODE: Paste the message below into your AI chat."},
    "manual_copied": {"tr": "Panoya kopyalandı. Sohbete yapıştırıp Enter'a bas... ",
                      "en": "Copied to clipboard. Paste it into the chat, then press Enter... "},
    "manual_wait_clip": {"tr": "Yapay zekânın cevabını kopyala, sonra burada Enter'a bas... ",
                         "en": "Copy the AI's reply, then press Enter here... "},
    "manual_paste": {"tr": "Yapay zekânın cevabını yapıştır, bitince tek başına /// yaz:",
                     "en": "Paste the AI's reply, then type /// on its own line:"},
    "manual_ran": {"tr": "{calls} işlem çalıştı, {errors} hata. Sonucu sohbete gönder:",
                   "en": "{calls} actions ran, {errors} errors. Send the result to the chat:"},
    "manual_done": {"tr": "Yapay zekâ işini bitirdiğini söylüyor:", "en": "The AI says it is finished:"},
}


def t(key: str, lang: str = "tr") -> str:
    row = STRINGS.get(key)
    if not row:
        return key
    return row.get(lang) or row.get("en") or key
