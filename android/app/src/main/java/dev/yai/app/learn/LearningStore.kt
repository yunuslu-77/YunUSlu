package dev.yai.app.learn

import android.content.ContentValues
import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import org.json.JSONArray
import org.json.JSONObject

/**
 * Öğrenme modu verisi (sadece bu telefonda saklanır, sunucu istediğinde gönderilir).
 * Kaydedilenler: ekran adı, buton/sekme etiketleri, hangi butonun hangi ekrana götürdüğü.
 * KAYDEDİLMEYENLER: yazdığın metinler, şifre alanları, liste içerikleri (mesajlar, kişiler vb.).
 */
class LearningStore(context: Context) : SQLiteOpenHelper(context, "learning.db", null, 1) {

    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL("CREATE TABLE apps(pkg TEXT PRIMARY KEY, label TEXT, enabled INTEGER, added INTEGER)")
        db.execSQL("""CREATE TABLE screens(id INTEGER PRIMARY KEY AUTOINCREMENT, pkg TEXT, sig TEXT UNIQUE,
            activity TEXT, title TEXT, controls TEXT, lists INTEGER, seen INTEGER, last INTEGER)""")
        db.execSQL("""CREATE TABLE transitions(from_id INTEGER, label TEXT, to_id INTEGER, count INTEGER,
            PRIMARY KEY(from_id, label, to_id))""")
    }

    override fun onUpgrade(db: SQLiteDatabase, o: Int, n: Int) {}

    // ---------------- uygulama seçimi ----------------
    fun setEnabled(pkg: String, label: String, enabled: Boolean) {
        if (Sensitive.isSensitive(pkg)) return
        writableDatabase.insertWithOnConflict("apps", null, ContentValues().apply {
            put("pkg", pkg); put("label", label); put("enabled", if (enabled) 1 else 0)
            put("added", System.currentTimeMillis())
        }, SQLiteDatabase.CONFLICT_REPLACE)
        cache = null
    }

    @Volatile private var cache: Set<String>? = null

    fun enabledPackages(): Set<String> = cache ?: readableDatabase
        .rawQuery("SELECT pkg FROM apps WHERE enabled=1", null).use { c ->
            buildSet { while (c.moveToNext()) add(c.getString(0)) }
        }.also { cache = it }

    fun isLearning(pkg: String?) = pkg != null && !Sensitive.isSensitive(pkg) && pkg in enabledPackages()

    // ---------------- kayıt ----------------
    /** Ekranı kaydeder ve ekran id'sini döner. */
    fun recordScreen(pkg: String, activity: String, title: String, controls: List<String>, lists: Int): Long {
        val sig = pkg + "|" + activity + "|" + controls.sorted().take(12).joinToString(",")
        val db = writableDatabase
        val now = System.currentTimeMillis()
        db.rawQuery("SELECT id FROM screens WHERE sig=?", arrayOf(sig)).use { c ->
            if (c.moveToFirst()) {
                val id = c.getLong(0)
                db.execSQL("UPDATE screens SET seen=seen+1, last=? WHERE id=?", arrayOf<Any>(now, id))
                return id
            }
        }
        return db.insert("screens", null, ContentValues().apply {
            put("pkg", pkg); put("sig", sig); put("activity", activity); put("title", title)
            put("controls", JSONArray(controls).toString()); put("lists", lists); put("seen", 1); put("last", now)
        })
    }

    fun recordTransition(fromId: Long, label: String, toId: Long) {
        if (fromId == toId || fromId <= 0 || toId <= 0) return
        writableDatabase.execSQL(
            """INSERT INTO transitions(from_id,label,to_id,count) VALUES(?,?,?,1)
               ON CONFLICT(from_id,label,to_id) DO UPDATE SET count=count+1""",
            arrayOf<Any>(fromId, label, toId))
    }

    // ---------------- okuma ----------------
    data class AppStat(val pkg: String, val label: String, val enabled: Boolean, val screens: Int, val transitions: Int)

    fun stats(): List<AppStat> = readableDatabase.rawQuery(
        """SELECT a.pkg, a.label, a.enabled,
             (SELECT COUNT(*) FROM screens s WHERE s.pkg=a.pkg),
             (SELECT COUNT(*) FROM transitions t JOIN screens s ON s.id=t.from_id WHERE s.pkg=a.pkg)
           FROM apps a ORDER BY a.enabled DESC, a.label""", null).use { c ->
        buildList { while (c.moveToNext()) add(AppStat(c.getString(0), c.getString(1), c.getInt(2) == 1, c.getInt(3), c.getInt(4))) }
    }

    fun learnedAppsJson(): JSONArray = JSONArray().apply {
        stats().filter { it.screens > 0 }.forEach {
            put(JSONObject().put("package", it.pkg).put("name", it.label).put("screens", it.screens)
                .put("transitions", it.transitions).put("learning", it.enabled))
        }
    }

    fun guideJson(pkg: String): JSONObject {
        if (Sensitive.isSensitive(pkg)) return JSONObject().put("error", "Hassas uygulama: öğrenme kapalı")
        val db = readableDatabase
        val names = HashMap<Long, String>()
        val screens = JSONArray()
        db.rawQuery("SELECT id, activity, title, controls, lists, seen FROM screens WHERE pkg=? ORDER BY seen DESC LIMIT 60",
            arrayOf(pkg)).use { c ->
            while (c.moveToNext()) {
                val id = c.getLong(0)
                val name = c.getString(2).ifBlank { c.getString(1).substringAfterLast('.') }
                names[id] = name
                screens.put(JSONObject().put("id", id).put("screen", name).put("activity", c.getString(1))
                    .put("buttons", JSONArray(c.getString(3))).put("list_count", c.getInt(4)).put("seen", c.getInt(5)))
            }
        }
        val moves = JSONArray()
        db.rawQuery("""SELECT t.from_id, t.label, t.to_id, t.count FROM transitions t JOIN screens s ON s.id=t.from_id
                       WHERE s.pkg=? ORDER BY t.count DESC LIMIT 150""", arrayOf(pkg)).use { c ->
            while (c.moveToNext()) {
                val f = names[c.getLong(0)] ?: continue
                val t = names[c.getLong(2)] ?: continue
                moves.put(JSONObject().put("from", f).put("tap", c.getString(1)).put("to", t).put("times", c.getInt(3)))
            }
        }
        return JSONObject().put("package", pkg).put("screens", screens).put("navigation", moves)
    }

    fun forget(pkg: String) {
        val db = writableDatabase
        db.execSQL("DELETE FROM transitions WHERE from_id IN (SELECT id FROM screens WHERE pkg=?)", arrayOf(pkg))
        db.delete("screens", "pkg=?", arrayOf(pkg))
    }
}
