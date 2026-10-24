"""Interface texts in Turkish and English."""

TEXT = {
    "tr": {
        "login": "Giriş yap", "signup": "Kayıt ol", "logout": "Çıkış", "email": "E-posta", "password": "Parola",
        "name": "Ad", "org_name": "Ekip / şirket adı", "dashboard": "Panel", "members": "Üyeler", "billing": "Abonelik",
        "account": "Hesabım", "admin": "Yönetim", "invite": "Davet et", "role": "Rol", "save": "Kaydet",
        "forgot": "Parolamı unuttum", "reset": "Parolayı sıfırla", "new_password": "Yeni parola",
        "email_taken": "Bu e-posta zaten kayıtlı.", "bad_login": "E-posta ya da parola hatalı.",
        "too_many": "Çok fazla deneme. Bir dakika sonra tekrar deneyin.",
        "password_short": "Parola en az 8 karakter olmalı.", "password_common": "Bu parola çok yaygın, başka bir tane seçin.",
        "bad_email": "Geçerli bir e-posta adresi girin.", "check_email": "E-postanızı kontrol edin.",
        "verify_sent": "Doğrulama bağlantısı e-postanıza gönderildi.", "verified": "E-postanız doğrulandı.",
        "link_invalid": "Bağlantı geçersiz ya da süresi dolmuş.", "reset_done": "Parolanız değiştirildi. Giriş yapabilirsiniz.",
        "reset_sent": "Bu adres kayıtlıysa, sıfırlama bağlantısı gönderildi.", "invite_sent": "Davet gönderildi.",
        "invite_accepted": "Ekibe katıldınız.", "forbidden": "Bu işlem için yetkiniz yok.",
        "current_plan": "Mevcut plan", "upgrade": "Yükselt", "cancel_sub": "Aboneliği iptal et",
        "canceled": "Aboneliğiniz dönem sonunda iptal edilecek.", "paid": "Ödeme alındı, planınız etkin.",
        "export": "Verilerimi indir (KVKK)", "delete_account": "Hesabımı sil", "deleted": "Hesabınız silindi.",
        "confirm_delete": "Silmek için e-postanızı yazın", "welcome": "Hoş geldiniz", "verify_first": "Lütfen önce e-postanızı doğrulayın.",
        "per_month": "/ay", "audit": "Denetim kaydı", "users": "Kullanıcılar", "orgs": "Ekipler", "subscriptions": "Abonelikler",
        "last_owner": "Ekibin son sahibini çıkaramazsınız.", "remove": "Çıkar",
    },
    "en": {
        "login": "Log in", "signup": "Sign up", "logout": "Log out", "email": "E-mail", "password": "Password",
        "name": "Name", "org_name": "Team / company name", "dashboard": "Dashboard", "members": "Members",
        "billing": "Billing", "account": "My account", "admin": "Admin", "invite": "Invite", "role": "Role", "save": "Save",
        "forgot": "Forgot password", "reset": "Reset password", "new_password": "New password",
        "email_taken": "This e-mail is already registered.", "bad_login": "Wrong e-mail or password.",
        "too_many": "Too many attempts. Try again in a minute.", "password_short": "Password must be at least 8 characters.",
        "password_common": "This password is too common, choose another.", "bad_email": "Enter a valid e-mail address.",
        "check_email": "Check your e-mail.", "verify_sent": "A verification link was sent to your e-mail.",
        "verified": "Your e-mail is verified.", "link_invalid": "The link is invalid or expired.",
        "reset_done": "Your password was changed. You can log in.", "reset_sent": "If this address is registered, a reset link was sent.",
        "invite_sent": "Invitation sent.", "invite_accepted": "You joined the team.", "forbidden": "You are not allowed to do this.",
        "current_plan": "Current plan", "upgrade": "Upgrade", "cancel_sub": "Cancel subscription",
        "canceled": "Your subscription will end at the end of the period.", "paid": "Payment received, your plan is active.",
        "export": "Download my data", "delete_account": "Delete my account", "deleted": "Your account was deleted.",
        "confirm_delete": "Type your e-mail to delete", "welcome": "Welcome", "verify_first": "Please verify your e-mail first.",
        "per_month": "/month", "audit": "Audit log", "users": "Users", "orgs": "Teams", "subscriptions": "Subscriptions",
        "last_owner": "You cannot remove the team's last owner.", "remove": "Remove",
    },
}


def t(lang: str, key: str) -> str:
    return TEXT.get(lang, TEXT["tr"]).get(key) or TEXT["en"].get(key, key)
