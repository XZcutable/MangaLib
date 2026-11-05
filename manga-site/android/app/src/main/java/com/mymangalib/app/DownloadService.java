package com.mymangalib.app;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;

import androidx.core.app.NotificationCompat;

/**
 * Keeps the app running while chapters download, so leaving the app doesn't stop them,
 * and shows their progress in a notification. OfflineDownloader starts and stops it.
 */
public class DownloadService extends Service {

    private static final String CHANNEL = "downloads";
    private static final int NOTIFICATION_ID = 7301;
    private static long lastUpdate = 0;
    // Set once startForeground() has run; only touched on the main thread.
    private static DownloadService running;

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        Notification notification = build(this);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC);
        } else {
            startForeground(NOTIFICATION_ID, notification);
        }
        running = this;
        // The queue may have emptied before Android got here (job failed or was already on disk).
        if (OfflineDownloader.get(this).idle()) stopSelf();
        return START_NOT_STICKY;
    }

    @Override
    public void onDestroy() {
        if (running == this) running = null;
        super.onDestroy();
    }

    /**
     * Stops the service once nothing is downloading. Never calls stopService() directly:
     * stopping a service started with startForegroundService() before it reached
     * startForeground() makes Android kill the app.
     */
    static void stopWhenIdle(Context context) {
        new Handler(Looper.getMainLooper()).post(() -> {
            if (running != null && OfflineDownloader.get(context).idle()) running.stopSelf();
        });
    }

    @Override
    public void onTimeout(int startId, int fgsType) {
        // Android 15 limits data-sync services to 6 hours a day. Stop politely; the app resumes later.
        stopSelf();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    /** Refreshes the notification text, at most a few times a second. */
    static void update(Context context) {
        long now = System.currentTimeMillis();
        OfflineDownloader downloader = OfflineDownloader.get(context);
        if (downloader.current() != null && now - lastUpdate < 300) return;
        lastUpdate = now;
        NotificationManager manager = (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);
        if (manager != null && downloader.current() != null) manager.notify(NOTIFICATION_ID, build(context));
    }

    private static Notification build(Context context) {
        NotificationManager manager = (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O && manager != null) {
            NotificationChannel channel = new NotificationChannel(CHANNEL, "Downloads", NotificationManager.IMPORTANCE_LOW);
            channel.setDescription("Progress of chapters downloading for offline reading");
            manager.createNotificationChannel(channel);
        }

        OfflineDownloader downloader = OfflineDownloader.get(context);
        OfflineDownloader.Job job = downloader.current();
        int waiting = downloader.waiting();
        Intent open = context.getPackageManager().getLaunchIntentForPackage(context.getPackageName());
        PendingIntent tap = PendingIntent.getActivity(context, 0, open, PendingIntent.FLAG_IMMUTABLE);

        NotificationCompat.Builder builder = new NotificationCompat.Builder(context, CHANNEL)
            .setSmallIcon(android.R.drawable.stat_sys_download)
            .setContentIntent(tap)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setPriority(NotificationCompat.PRIORITY_LOW);
        if (job == null) {
            builder.setContentTitle("Preparing downloads").setProgress(0, 0, true);
        } else {
            int total = job.pages.size();
            builder.setContentTitle(job.title)
                .setContentText(job.done.get() + " of " + total + " pages" + (waiting > 0 ? " · " + waiting + " more waiting" : ""))
                .setProgress(total, job.done.get(), false);
        }
        return builder.build();
    }
}
