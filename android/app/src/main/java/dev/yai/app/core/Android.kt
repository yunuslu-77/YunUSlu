package dev.yai.app.core

import android.Manifest
import android.app.AlarmManager
import android.app.Notification
import android.app.PendingIntent
import android.app.Service
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.app.ServiceCompat
import androidx.core.content.ContextCompat
import dev.yai.app.MainActivity
import dev.yai.app.R
import dev.yai.app.YaiApp
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

private fun openApp(ctx: Context) = PendingIntent.getActivity(ctx, 0, Intent(ctx, MainActivity::class.java)
    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP), PendingIntent.FLAG_IMMUTABLE)

private fun canNotify(ctx: Context) = Build.VERSION.SDK_INT < 33 ||
    ContextCompat.checkSelfPermission(ctx, Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED

/** Bildirimler: onay istekleri (Onayla/İptal butonlu) ve YAi mesajları. */
class AndroidNotifier(private val ctx: Context) : Notifier {
    override fun approvalRequested(id: Long, summary: String) {
        YaiApp.instance.yai.changed()
        if (!canNotify(ctx)) return
        fun action(approve: Boolean) = PendingIntent.getBroadcast(ctx, (id * 2 + if (approve) 1 else 0).toInt(),
            Intent(ctx, ApprovalReceiver::class.java).putExtra("id", id).putExtra("approve", approve), PendingIntent.FLAG_IMMUTABLE)
        val n = NotificationCompat.Builder(ctx, YaiApp.CHANNEL_MESSAGES).setSmallIcon(R.drawable.ic_stat_yai)
            .setContentTitle("🔐 YAi onay istiyor").setContentText(summary.lineSequence().first())
            .setStyle(NotificationCompat.BigTextStyle().bigText(summary)).setContentIntent(openApp(ctx)).setAutoCancel(true)
            .addAction(0, "✅ Onayla", action(true)).addAction(0, "❌ İptal", action(false))
            .setPriority(NotificationCompat.PRIORITY_HIGH).build()
        NotificationManagerCompat.from(ctx).notify(10_000 + id.toInt(), n)
    }

    override fun message(title: String, text: String) {
        YaiApp.instance.yai.changed()
        if (!canNotify(ctx)) return
        val n = NotificationCompat.Builder(ctx, YaiApp.CHANNEL_MESSAGES).setSmallIcon(R.drawable.ic_stat_yai)
            .setContentTitle(title).setContentText(text.lineSequence().first())
            .setStyle(NotificationCompat.BigTextStyle().bigText(text)).setContentIntent(openApp(ctx)).setAutoCancel(true).build()
        NotificationManagerCompat.from(ctx).notify((System.currentTimeMillis() % 100_000).toInt(), n)
    }
}

/** Görevleri Android alarmlarıyla zamanlar: uygulama kapalıyken de zamanında uyanır. */
class Alarms(private val ctx: Context, private val db: Db) : AlarmScheduler {
    private val am = ctx.getSystemService(AlarmManager::class.java)

    private fun pi(id: Long) = PendingIntent.getBroadcast(ctx, id.toInt(), Intent(ctx, AlarmReceiver::class.java).putExtra("id", id),
        PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)

    fun arm(id: Long, at: Long) {
        if (Build.VERSION.SDK_INT < 31 || am.canScheduleExactAlarms()) am.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, at, pi(id))
        else am.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, at, pi(id))
    }

    override fun add(kind: String, payload: String, spec: String): Long {
        val next = TimeParse.next(spec) ?: throw ToolError("Bu zaman geçmişte kaldı")
        val id = db.addSchedule(kind, payload, spec, next)
        arm(id, next)
        YaiApp.instance.yai.changed()
        return id
    }

    override fun remove(id: Long): Boolean {
        am.cancel(pi(id))
        return db.deleteSchedule(id).also { YaiApp.instance.yai.changed() }
    }

    fun rearmAll() = db.schedules().forEach { s ->
        val next = if (s.nextRun > System.currentTimeMillis()) s.nextRun else TimeParse.next(s.spec)
        if (next == null) db.updateNextRun(s.id, null) else { db.updateNextRun(s.id, next); arm(s.id, next) }
    }
}

class AlarmReceiver : BroadcastReceiver() {
    override fun onReceive(ctx: Context, intent: Intent) {
        val id = intent.getLongExtra("id", -1)
        val yai = YaiApp.instance.yai
        val s = yai.db.schedule(id) ?: return
        val next = TimeParse.next(s.spec)
        yai.db.updateNextRun(id, next)
        next?.let { (yai.alarms as? Alarms)?.arm(id, it) }
        if (s.kind == "message") yai.notifier.message("⏰ Hatırlatma", s.payload)
        else TaskService.start(ctx, s.payload)
        yai.changed()
    }
}

class BootReceiver : BroadcastReceiver() {
    override fun onReceive(ctx: Context, intent: Intent) {
        (YaiApp.instance.yai.alarms as? Alarms)?.rearmAll()
    }
}

class ApprovalReceiver : BroadcastReceiver() {
    override fun onReceive(ctx: Context, intent: Intent) {
        val id = intent.getLongExtra("id", -1)
        NotificationManagerCompat.from(ctx).cancel(10_000 + id.toInt())
        TaskService.startApproval(ctx, id, intent.getBooleanExtra("approve", false))
    }
}

/** Arka planda bir YAi işi (zamanlanmış görev veya bildirimden onay) çalıştıran kısa ön plan servisi. */
class TaskService : Service() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private var running = 0

    companion object {
        fun start(ctx: Context, task: String) =
            ContextCompat.startForegroundService(ctx, Intent(ctx, TaskService::class.java).putExtra("task", task))
        fun startApproval(ctx: Context, id: Long, approve: Boolean) =
            ContextCompat.startForegroundService(ctx, Intent(ctx, TaskService::class.java).putExtra("approval", id).putExtra("approve", approve))
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun working(): Notification = NotificationCompat.Builder(this, YaiApp.CHANNEL_SERVICE).setSmallIcon(R.drawable.ic_stat_yai)
        .setContentTitle("YAi çalışıyor…").setOngoing(true).setPriority(NotificationCompat.PRIORITY_MIN).build()

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val type = if (Build.VERSION.SDK_INT >= 34) ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE else 0
        ServiceCompat.startForeground(this, 7, working(), type)
        val yai = YaiApp.instance.yai
        running++
        scope.launch {
            try {
                if (intent?.hasExtra("approval") == true) {
                    val reply = yai.agent.resolveApproval(intent.getLongExtra("approval", -1), intent.getBooleanExtra("approve", false))
                    yai.notifier.message("YAi", reply)
                } else intent?.getStringExtra("task")?.let { task ->
                    yai.notifier.message("🤖 YAi", yai.agent.runTask(task))
                }
            } catch (e: Exception) {
                yai.notifier.message("⚠️ YAi", e.message ?: "Hata")
            } finally {
                if (--running <= 0) stopSelf()
            }
        }
        return START_NOT_STICKY
    }
}
