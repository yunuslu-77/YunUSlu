package dev.yai.app.bridge

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.provider.Telephony
import org.json.JSONObject

class SmsReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Telephony.Sms.Intents.SMS_RECEIVED_ACTION) return
        val msgs = Telephony.Sms.Intents.getMessagesFromIntent(intent) ?: return
        val from = msgs.firstOrNull()?.originatingAddress ?: return
        val body = msgs.joinToString("") { it.messageBody ?: "" }
        BridgeService.emitEvent("sms", JSONObject().put("number", from).put("sender", from).put("body", body))
    }
}
