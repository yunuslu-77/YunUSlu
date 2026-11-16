package dev.yai.app.core

import android.content.ContentValues
import android.content.Context
import android.database.Cursor
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import org.json.JSONArray
import org.json.JSONObject

/** YAi'nin telefondaki hafızası: sohbet, kalıcı bilgiler, notlar, görevler, onaylar, maliyet, kayıtlar. */
class Db(context: Context, name: String? = "yai.db") : SQLiteOpenHelper(context, name, null, 1) {

    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL("CREATE TABLE messages(id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT, text TEXT, ts INTEGER)")
        db.execSQL("CREATE TABLE memories(id INTEGER PRIMARY KEY AUTOINCREMENT, fact TEXT, ts INTEGER)")
        db.execSQL("CREATE TABLE pages(id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, content TEXT, updated INTEGER)")
        db.execSQL("""CREATE TABLE schedules(id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, payload TEXT,
            spec TEXT, next_run INTEGER, enabled INTEGER DEFAULT 1, created INTEGER)""")
        db.execSQL("""CREATE TABLE approvals(id INTEGER PRIMARY KEY AUTOINCREMENT, tool TEXT, args TEXT, summary TEXT,
            status TEXT DEFAULT 'pending', result TEXT, created INTEGER)""")
        db.execSQL("CREATE TABLE usage(id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER, day TEXT, month TEXT, model TEXT, tin INTEGER, tout INTEGER, cost REAL)")
        db.execSQL("CREATE TABLE audit(id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER, tool TEXT, args TEXT, result TEXT, ok INTEGER)")
        db.execSQL("CREATE TABLE skills(name TEXT PRIMARY KEY, trigger TEXT, steps TEXT, uses INTEGER DEFAULT 0)")
    }

    override fun onUpgrade(db: SQLiteDatabase, o: Int, n: Int) {}

    private fun <T> query(sql: String, args: Array<String> = emptyArray(), map: (Cursor) -> T): List<T> =
        readableDatabase.rawQuery(sql, args).use { c -> buildList { while (c.moveToNext()) add(map(c)) } }

    private fun insert(table: String, vararg kv: Pair<String, Any?>): Long =
        writableDatabase.insert(table, null, ContentValues().apply {
            kv.forEach { (k, v) ->
                when (v) { null -> putNull(k); is Int -> put(k, v); is Long -> put(k, v); is Double -> put(k, v)
                    is Boolean -> put(k, if (v) 1 else 0); else -> put(k, v.toString()) }
            }
        })

    private fun now() = System.currentTimeMillis()

    // ---------------- sohbet ----------------
    data class Msg(val role: String, val text: String, val ts: Long)

    fun addMessage(role: String, text: String) { insert("messages", "role" to role, "text" to text, "ts" to now()) }
    fun recentMessages(limit: Int): List<Msg> =
        query("SELECT role,text,ts FROM messages ORDER BY id DESC LIMIT $limit") { Msg(it.getString(0), it.getString(1), it.getLong(2)) }.reversed()
    fun clearMessages() { writableDatabase.delete("messages", null, null) }

    // ---------------- hafıza ----------------
    data class Memory(val id: Long, val fact: String)

    fun addMemory(fact: String) = insert("memories", "fact" to fact, "ts" to now())
    fun memories(): List<Memory> = query("SELECT id,fact FROM memories ORDER BY id") { Memory(it.getLong(0), it.getString(1)) }
    fun deleteMemory(id: Long) = writableDatabase.delete("memories", "id=?", arrayOf("$id")) > 0

    // ---------------- sayfalar ----------------
    data class Page(val id: Long, val title: String, val content: String, val updated: Long)

    fun savePage(id: Long?, title: String?, content: String, append: Boolean = false): Long {
        if (id == null) return insert("pages", "title" to (title ?: "Not"), "content" to content, "updated" to now())
        val old = page(id) ?: return -1
        writableDatabase.update("pages", ContentValues().apply {
            put("content", if (append) old.content + "\n\n" + content else content); put("updated", now())
            title?.let { put("title", it) }
        }, "id=?", arrayOf("$id"))
        return id
    }
    fun page(id: Long): Page? = query("SELECT id,title,content,updated FROM pages WHERE id=?", arrayOf("$id")) {
        Page(it.getLong(0), it.getString(1), it.getString(2), it.getLong(3)) }.firstOrNull()
    fun pages(): List<Page> = query("SELECT id,title,'',updated FROM pages ORDER BY updated DESC LIMIT 100") {
        Page(it.getLong(0), it.getString(1), "", it.getLong(3)) }
    fun deletePage(id: Long) = writableDatabase.delete("pages", "id=?", arrayOf("$id")) > 0

    // ---------------- görevler ----------------
    data class Schedule(val id: Long, val kind: String, val payload: String, val spec: String, val nextRun: Long)

    fun addSchedule(kind: String, payload: String, spec: String, nextRun: Long) =
        insert("schedules", "kind" to kind, "payload" to payload, "spec" to spec, "next_run" to nextRun, "enabled" to 1, "created" to now())
    fun schedules(): List<Schedule> = query("SELECT id,kind,payload,spec,next_run FROM schedules WHERE enabled=1 ORDER BY next_run") {
        Schedule(it.getLong(0), it.getString(1), it.getString(2), it.getString(3), it.getLong(4)) }
    fun schedule(id: Long) = schedules().firstOrNull { it.id == id }
    fun updateNextRun(id: Long, next: Long?) {
        writableDatabase.update("schedules", ContentValues().apply {
            if (next == null) put("enabled", 0) else put("next_run", next) }, "id=?", arrayOf("$id"))
    }
    fun deleteSchedule(id: Long) = writableDatabase.update("schedules", ContentValues().apply { put("enabled", 0) },
        "id=? AND enabled=1", arrayOf("$id")) > 0

    // ---------------- onaylar ----------------
    data class Approval(val id: Long, val tool: String, val args: JSONObject, val summary: String, val status: String)

    fun addApproval(tool: String, args: JSONObject, summary: String) =
        insert("approvals", "tool" to tool, "args" to args.toString(), "summary" to summary, "created" to now())
    fun pendingApprovals(): List<Approval> = query("SELECT id,tool,args,summary,status FROM approvals WHERE status='pending' ORDER BY id DESC") {
        Approval(it.getLong(0), it.getString(1), JSONObject(it.getString(2)), it.getString(3), it.getString(4)) }
    fun approval(id: Long): Approval? = query("SELECT id,tool,args,summary,status FROM approvals WHERE id=?", arrayOf("$id")) {
        Approval(it.getLong(0), it.getString(1), JSONObject(it.getString(2)), it.getString(3), it.getString(4)) }.firstOrNull()
    fun findPending(tool: String, args: JSONObject): Long? =
        pendingApprovals().firstOrNull { it.tool == tool && it.args.toString() == args.toString() }?.id
    fun decideApproval(id: Long, status: String, result: String? = null) {
        writableDatabase.update("approvals", ContentValues().apply { put("status", status); result?.let { put("result", it) } },
            "id=?", arrayOf("$id"))
    }

    // ---------------- beceriler ----------------
    fun saveSkill(name: String, trigger: String, steps: String) {
        writableDatabase.insertWithOnConflict("skills", null, ContentValues().apply {
            put("name", name); put("trigger", trigger); put("steps", steps) }, SQLiteDatabase.CONFLICT_REPLACE)
    }
    fun skills(): JSONArray = JSONArray().apply {
        query("SELECT name,trigger,steps,uses FROM skills") { JSONObject().put("name", it.getString(0)).put("trigger", it.getString(1))
            .put("steps", it.getString(2)).put("uses", it.getInt(3)) }.forEach { put(it) } }
    fun useSkill(name: String): JSONObject? {
        writableDatabase.execSQL("UPDATE skills SET uses=uses+1 WHERE name=?", arrayOf(name))
        return (0 until skills().length()).map { skills().getJSONObject(it) }.firstOrNull { it.getString("name") == name }
    }
    fun deleteSkill(name: String) = writableDatabase.delete("skills", "name=?", arrayOf(name)) > 0

    // ---------------- maliyet ----------------
    fun addUsage(day: String, month: String, model: String, tin: Int, tout: Int, cost: Double) {
        insert("usage", "ts" to now(), "day" to day, "month" to month, "model" to model, "tin" to tin, "tout" to tout, "cost" to cost)
    }
    fun spent(column: String, value: String): Double =
        query("SELECT COALESCE(SUM(cost),0) FROM usage WHERE $column=?", arrayOf(value)) { it.getDouble(0) }.first()

    // ---------------- denetim ----------------
    fun audit(tool: String, args: String, result: String, ok: Boolean) {
        insert("audit", "ts" to now(), "tool" to tool, "args" to args.take(1500), "result" to result.take(1500), "ok" to ok)
    }
    fun auditCount() = query("SELECT COUNT(*) FROM audit") { it.getInt(0) }.first()
}
