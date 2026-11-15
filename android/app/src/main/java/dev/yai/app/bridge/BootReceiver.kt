package dev.yai.app.bridge

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import dev.yai.app.YaiApp

class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val prefs = YaiApp.instance.prefs
        if (prefs.bridgeEnabled && prefs.server.isComplete) BridgeService.start(context, fromBackground = true)
    }
}
