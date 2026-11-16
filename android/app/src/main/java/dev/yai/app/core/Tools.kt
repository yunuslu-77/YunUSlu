package dev.yai.app.core

import org.json.JSONArray
import org.json.JSONObject

/** Ajanın kullanabileceği bir araç. */
class Tool(
    val name: String,
    val description: String,
    val params: JSONObject,
    val approval: (JSONObject) -> Boolean = { false },
    val summary: ((JSONObject) -> String)? = null,
    val run: suspend (ToolCtx, JSONObject) -> Any?,
) {
    fun declaration(): JSONObject = JSONObject().put("name", name).put("description", description).put("parametersJsonSchema", params)
    fun describe(a: JSONObject): String = runCatching { summary?.invoke(a) }.getOrNull()
        ?: (name + "(" + a.keys().asSequence().joinToString(", ") { "$it=${a.opt(it)?.toString()?.take(150)}" } + ")")
}

class ToolCtx(val yai: Yai, val approved: Boolean = false)

class ToolError(message: String) : Exception(message)

/** JSON şema kısayolları. */
object P {
    data class Param(val schema: JSONObject, val required: Boolean)
    fun str(d: String, required: Boolean = true, enum: List<String>? = null) =
        Param(JSONObject().put("type", "string").put("description", d).apply { enum?.let { put("enum", JSONArray(it)) } }, required)
    fun int(d: String, required: Boolean = true) = Param(JSONObject().put("type", "integer").put("description", d), required)
    fun bool(d: String, required: Boolean = true) = Param(JSONObject().put("type", "boolean").put("description", d), required)
    fun schema(vararg ps: Pair<String, Param>): JSONObject {
        val props = JSONObject(); val req = JSONArray()
        ps.forEach { (k, p) -> props.put(k, p.schema); if (p.required) req.put(k) }
        return JSONObject().put("type", "object").put("properties", props).apply { if (req.length() > 0) put("required", req) }
    }
}

fun tool(name: String, description: String, vararg params: Pair<String, P.Param>, approval: (JSONObject) -> Boolean = { false },
         summary: ((JSONObject) -> String)? = null, run: suspend (ToolCtx, JSONObject) -> Any?) =
    Tool(name, description, P.schema(*params), approval, summary, run)

fun approvalAlways(): (JSONObject) -> Boolean = { true }
