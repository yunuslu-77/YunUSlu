package dev.yai.app.core

import java.time.LocalDate
import java.time.LocalDateTime
import java.time.LocalTime
import java.time.ZoneId
import java.time.ZonedDateTime

class WhenError(message: String) : Exception(message)

/**
 * Türkçe zaman ifadeleri → görev zamanı.
 * Spec biçimi: "daily:HH:MM:1,2,3,4,5" (tekrarlayan; günler 1=Pzt..7=Paz, boşsa her gün) veya "once:<epochMillis>".
 */
object TimeParse {
    const val HELP = "08:00 · hafta içi 08:30 · pzt,cum 09:00 · her pazartesi 10:00 · +30dk · 2 saat sonra · yarın 09:00 · 20.12.2026 14:00"

    private val DAYS = mapOf(
        "pazartesi" to 1, "pzt" to 1, "salı" to 2, "sali" to 2, "sal" to 2, "çarşamba" to 3, "carsamba" to 3, "çar" to 3,
        "car" to 3, "perşembe" to 4, "persembe" to 4, "per" to 4, "cuma" to 5, "cum" to 5, "cumartesi" to 6, "cmt" to 6,
        "pazar" to 7, "paz" to 7,
    )
    private val UNITS = mapOf("dk" to 1L, "dakika" to 1L, "dak" to 1L, "m" to 1L, "s" to 60L, "sa" to 60L, "saat" to 60L,
        "h" to 60L, "g" to 1440L, "gün" to 1440L, "gun" to 1440L, "d" to 1440L)

    private fun hm(s: String): Pair<Int, Int> {
        val m = Regex("(\\d{1,2})[:.](\\d{2})").find(s) ?: throw WhenError("Saat bulunamadı (örnek: 08:00)")
        val h = m.groupValues[1].toInt(); val mi = m.groupValues[2].toInt()
        if (h > 23 || mi > 59) throw WhenError("Geçersiz saat")
        return h to mi
    }

    fun parse(text: String, now: ZonedDateTime = ZonedDateTime.now()): String {
        val s = text.trim().lowercase()
        val zone = now.zone

        Regex("^\\+?\\s*(\\d+)\\s*([a-zçğışöü]+)(\\s+sonra)?$").find(s)?.let { m ->
            if (s.startsWith("+") || m.groupValues[3].isNotEmpty()) {
                val unit = UNITS[m.groupValues[2]] ?: throw WhenError("Bilinmeyen birim: ${m.groupValues[2]}")
                return "once:" + now.plusMinutes(m.groupValues[1].toLong() * unit).toInstant().toEpochMilli()
            }
        }
        (Regex("(\\d{4})-(\\d{2})-(\\d{2})").find(s)?.let { Triple(it.groupValues[1].toInt(), it.groupValues[2].toInt(), it.groupValues[3].toInt()) to it }
            ?: Regex("(\\d{1,2})\\.(\\d{1,2})\\.(\\d{4})").find(s)?.let { Triple(it.groupValues[3].toInt(), it.groupValues[2].toInt(), it.groupValues[1].toInt()) to it })
            ?.let { (ymd, m) ->
                val rest = s.substring(m.range.last + 1)
                val (h, mi) = if (Regex("\\d{1,2}[:.]\\d{2}").containsMatchIn(rest)) hm(rest) else 9 to 0
                val dt = ZonedDateTime.of(LocalDate.of(ymd.first, ymd.second, ymd.third), LocalTime.of(h, mi), zone)
                if (!dt.isAfter(now)) throw WhenError("Bu tarih geçmişte kaldı")
                return "once:" + dt.toInstant().toEpochMilli()
            }
        if (s.startsWith("yarın") || s.startsWith("yarin") || s.startsWith("bugün") || s.startsWith("bugun")) {
            val (h, mi) = hm(s)
            val base = if (s.startsWith("yar")) now.toLocalDate().plusDays(1) else now.toLocalDate()
            val dt = ZonedDateTime.of(base, LocalTime.of(h, mi), zone)
            if (!dt.isAfter(now)) throw WhenError("Bu saat bugün için geçti")
            return "once:" + dt.toInstant().toEpochMilli()
        }
        val (h, mi) = hm(s)
        val days = when {
            "hafta içi" in s || "hafta ici" in s -> listOf(1, 2, 3, 4, 5)
            "hafta sonu" in s -> listOf(6, 7)
            else -> Regex("[a-zçğışöü]+").findAll(s).mapNotNull { w ->
                val word = w.value
                DAYS[word] ?: DAYS[word.replace(Regex("(leri|ları|lari|si|sı|i|ı)$"), "")]
            }.toSortedSet().toList()
        }
        return "daily:%02d:%02d:%s".format(h, mi, days.joinToString(","))
    }

    /** Bir sonraki çalışma zamanı (epoch ms); bir kerelik ve geçmişse null. */
    fun next(spec: String, after: ZonedDateTime = ZonedDateTime.now()): Long? {
        if (spec.startsWith("once:")) return spec.removePrefix("once:").toLong().takeIf { it > after.toInstant().toEpochMilli() }
        val p = spec.removePrefix("daily:").split(":")
        val time = LocalTime.of(p[0].toInt(), p[1].toInt())
        val days = p.getOrNull(2)?.split(",")?.filter { it.isNotBlank() }?.map { it.toInt() } ?: emptyList()
        var d = after.toLocalDate()
        repeat(8) {
            val cand = ZonedDateTime.of(LocalDateTime.of(d, time), after.zone)
            if (cand.isAfter(after) && (days.isEmpty() || cand.dayOfWeek.value in days)) return cand.toInstant().toEpochMilli()
            d = d.plusDays(1)
        }
        return null
    }

    private val DAY_TR = mapOf(1 to "Pzt", 2 to "Sal", 3 to "Çar", 4 to "Per", 5 to "Cum", 6 to "Cmt", 7 to "Paz")

    fun describe(spec: String, zone: ZoneId = ZoneId.systemDefault()): String {
        if (spec.startsWith("once:")) {
            val t = java.time.Instant.ofEpochMilli(spec.removePrefix("once:").toLong()).atZone(zone)
            return "bir kez: %02d.%02d.%d %02d:%02d".format(t.dayOfMonth, t.monthValue, t.year, t.hour, t.minute)
        }
        val p = spec.removePrefix("daily:").split(":")
        val days = p.getOrNull(2)?.split(",")?.filter { it.isNotBlank() }?.map { it.toInt() } ?: emptyList()
        val dayText = when (days) { emptyList<Int>() -> "her gün"; listOf(1, 2, 3, 4, 5) -> "hafta içi"; listOf(6, 7) -> "hafta sonu"
            else -> days.joinToString(",") { DAY_TR[it]!! } }
        return "$dayText ${p[0]}:${p[1]}"
    }

}
