package dev.yai.app.learn

/**
 * Hassas uygulamalar: öğrenme modu, ekran okuma ve ekran kontrolü bu uygulamalarda HER ZAMAN kapalıdır.
 * (Banka, ödeme, kripto, şifre yöneticisi, 2FA, e-Devlet.)
 */
object Sensitive {
    private val keywords = listOf(
        "bank", "banka", "wallet", "cuzdan", "pay", "papara", "ininal", "enpara", "akbank", "garanti", "isbank",
        "ziraat", "yapikredi", "ykb", "halkbank", "vakif", "qnb", "finansbank", "denizbank", "teb", "ing.mobil",
        "kuveyt", "albaraka", "odeabank", "sekerbank", "fibabanka", "binance", "btcturk", "paribu", "coinbase",
        "crypto", "kripto", "metamask", "trustwallet", "authenticator", "authy", "2fa", "otp", "1password",
        "lastpass", "bitwarden", "keepass", "dashlane", "nordpass", "keeper", "password", "sifre", "edevlet",
        "turkiye.gov", "tr.gov", "android.vending.billing",
    )
    private val exact = setOf("com.google.android.apps.walletnfcrel", "com.samsung.android.spay", "dev.yai.app",
        "com.android.settings.password")

    fun isSensitive(pkg: String?): Boolean {
        if (pkg.isNullOrBlank()) return false
        val p = pkg.lowercase()
        return p in exact || keywords.any { p.contains(it) }
    }
}
