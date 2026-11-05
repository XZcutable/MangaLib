package com.mymangalib.app;

import android.content.Context;
import android.content.Intent;
import android.os.Build;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * Downloads chapters for offline reading, one chapter at a time with a few pages in parallel.
 * Files go to filesDir/offline/{folder}/{page}.{ext}. Pages already on disk are skipped, so a
 * chapter that was interrupted (app closed, network lost) picks up where it stopped.
 * While anything is queued, DownloadService keeps the app alive and shows the progress notification.
 */
public class OfflineDownloader {

    public interface Listener {
        void onProgress(Job job);
        void onComplete(Job job, List<String> files);
        void onFailed(Job job, String message);
    }

    public static class Job {
        public final String id;
        public final String folder;
        public final String title;
        public final List<String[]> pages; // {page number, url}
        public final AtomicInteger done = new AtomicInteger();
        volatile boolean cancelled;

        Job(String id, String folder, String title, List<String[]> pages) {
            this.id = id;
            this.folder = folder;
            this.title = title;
            this.pages = pages;
        }
    }

    private static final int PARALLEL_PAGES = 3;
    private static OfflineDownloader instance;

    private final Context context;
    private final Deque<Job> queue = new ArrayDeque<>();
    private final ExecutorService chapterThread = Executors.newSingleThreadExecutor();
    private final ExecutorService pageThreads = Executors.newFixedThreadPool(PARALLEL_PAGES);
    private Job current;
    private Listener listener;

    private OfflineDownloader(Context context) {
        this.context = context.getApplicationContext();
    }

    public static synchronized OfflineDownloader get(Context context) {
        if (instance == null) instance = new OfflineDownloader(context);
        return instance;
    }

    public void setListener(Listener listener) {
        this.listener = listener;
    }

    public File root() {
        return new File(context.getFilesDir(), "offline");
    }

    /** A folder inside root(), or null if the name tries to leave it. */
    public File folder(String relative) throws IOException {
        File folder = new File(root(), relative);
        String rootPath = root().getCanonicalPath() + File.separator;
        return folder.getCanonicalPath().startsWith(rootPath) ? folder : null;
    }

    public synchronized void enqueue(Job job) {
        for (Job queued : queue) {
            if (queued.id.equals(job.id)) return; // Already waiting
        }
        if (current != null && current.id.equals(job.id)) return;
        queue.add(job);
        startService();
        chapterThread.execute(this::runNext);
    }

    public synchronized void cancel(String id) {
        queue.removeIf(job -> job.id.equals(id));
        if (current != null && current.id.equals(id)) current.cancelled = true;
        if (queue.isEmpty() && current == null) stopService();
    }

    public synchronized Job current() {
        return current;
    }

    public synchronized boolean idle() {
        return queue.isEmpty() && current == null;
    }

    public synchronized int waiting() {
        return queue.size();
    }

    public synchronized List<Job> jobs() {
        List<Job> all = new ArrayList<>();
        if (current != null) all.add(current);
        all.addAll(queue);
        return all;
    }

    private void runNext() {
        Job job;
        synchronized (this) {
            job = queue.poll();
            current = job;
        }
        if (job == null) return;
        try {
            List<String> files = download(job);
            if (!job.cancelled && listener != null) listener.onComplete(job, files);
        } catch (Exception error) {
            if (!job.cancelled && listener != null) {
                String message = error.getMessage();
                listener.onFailed(job, message == null ? error.getClass().getSimpleName() : message);
            }
        } finally {
            synchronized (this) {
                current = null;
                if (queue.isEmpty()) stopService();
            }
            DownloadService.update(context);
        }
    }

    private List<String> download(Job job) throws Exception {
        File folder = folder(job.folder);
        if (folder == null) throw new IOException("Bad folder");
        if (!folder.isDirectory() && !folder.mkdirs()) throw new IOException("Can't create " + folder);

        List<Future<?>> pending = new ArrayList<>();
        final Exception[] failure = {null};
        for (String[] page : job.pages) {
            pending.add(pageThreads.submit(() -> {
                if (job.cancelled || failure[0] != null) return;
                try {
                    downloadPage(folder, page[0], page[1]);
                    job.done.incrementAndGet();
                    if (listener != null) listener.onProgress(job);
                    DownloadService.update(context);
                } catch (Exception error) {
                    synchronized (failure) {
                        if (failure[0] == null) failure[0] = error;
                    }
                }
            }));
        }
        for (Future<?> future : pending) future.get();
        if (failure[0] != null) throw failure[0];

        List<String> files = new ArrayList<>();
        File[] onDisk = folder.listFiles();
        if (onDisk != null) {
            for (File file : onDisk) {
                if (!file.getName().endsWith(".part")) files.add(file.getName());
            }
        }
        return files;
    }

    private static File existing(File folder, String name) {
        File[] matches = folder.listFiles((dir, file) -> file.startsWith(name + ".") && !file.endsWith(".part"));
        return matches != null && matches.length > 0 && matches[0].length() > 0 ? matches[0] : null;
    }

    private static String extension(String contentType) {
        if (contentType == null) return "img";
        String type = contentType.toLowerCase().split(";")[0].trim();
        switch (type) {
            case "image/jpeg": return "jpg";
            case "image/png": return "png";
            case "image/webp": return "webp";
            case "image/gif": return "gif";
            case "image/avif": return "avif";
            default: return "img";
        }
    }

    private static void downloadPage(File folder, String name, String url) throws IOException {
        if (existing(folder, name) != null) return;
        HttpURLConnection connection = null;
        File part = new File(folder, name + ".part");
        try {
            connection = (HttpURLConnection) new URL(url).openConnection();
            connection.setConnectTimeout(15000);
            connection.setReadTimeout(30000);
            int status = connection.getResponseCode();
            if (status != HttpURLConnection.HTTP_OK) {
                throw new IOException("The server answered " + status + " for page " + name);
            }
            try (InputStream in = connection.getInputStream(); OutputStream out = new FileOutputStream(part)) {
                byte[] buffer = new byte[64 * 1024];
                int read;
                while ((read = in.read(buffer)) != -1) out.write(buffer, 0, read);
            }
            File target = new File(folder, name + "." + extension(connection.getContentType()));
            if (!part.renameTo(target)) throw new IOException("Can't save page " + name);
        } finally {
            part.delete();
            if (connection != null) connection.disconnect();
        }
    }

    private void startService() {
        Intent intent = new Intent(context, DownloadService.class);
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) context.startForegroundService(intent);
            else context.startService(intent);
        } catch (Exception ignored) {
            // Android refuses when the app is in the background; the download still runs while the app is alive
        }
    }

    private void stopService() {
        DownloadService.stopWhenIdle(context);
    }

    /** Bytes used by everything under the folder. */
    public static long size(File file) {
        if (file.isFile()) return file.length();
        long total = 0;
        File[] children = file.listFiles();
        if (children != null) for (File child : children) total += size(child);
        return total;
    }

    public static void delete(File file) {
        File[] children = file.listFiles();
        if (children != null) for (File child : children) delete(child);
        file.delete();
    }
}
