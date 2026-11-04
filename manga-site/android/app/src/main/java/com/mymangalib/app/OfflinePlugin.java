package com.mymangalib.app;

import android.Manifest;

import com.getcapacitor.JSArray;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.getcapacitor.annotation.Permission;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.util.ArrayList;
import java.util.List;

/**
 * Offline downloads for the web app (lib/offline.js). The app decides what to download and keeps
 * the list of downloaded chapters; this plugin only fetches page images into app storage.
 * Events: "progress" {id, done, total}, "complete" {id, files}, "failed" {id, message}.
 */
@CapacitorPlugin(
    name = "Offline",
    permissions = { @Permission(strings = { Manifest.permission.POST_NOTIFICATIONS }, alias = "notifications") }
)
public class OfflinePlugin extends Plugin {

    @Override
    public void load() {
        OfflineDownloader.get(getContext()).setListener(new OfflineDownloader.Listener() {
            @Override
            public void onProgress(OfflineDownloader.Job job) {
                JSObject event = new JSObject();
                event.put("id", job.id);
                event.put("done", job.done.get());
                event.put("total", job.pages.size());
                notifyListeners("progress", event);
            }

            @Override
            public void onComplete(OfflineDownloader.Job job, List<String> files) {
                JSObject event = new JSObject();
                event.put("id", job.id);
                event.put("files", new JSArray(files));
                notifyListeners("complete", event, true);
            }

            @Override
            public void onFailed(OfflineDownloader.Job job, String message) {
                JSObject event = new JSObject();
                event.put("id", job.id);
                event.put("message", message);
                notifyListeners("failed", event, true);
            }
        });
    }

    /** Where downloads live, for building file URLs with Capacitor.convertFileSrc. */
    @PluginMethod
    public void info(PluginCall call) {
        JSObject result = new JSObject();
        File root = OfflineDownloader.get(getContext()).root();
        result.put("root", root.getAbsolutePath());
        JSArray active = new JSArray();
        for (OfflineDownloader.Job job : OfflineDownloader.get(getContext()).jobs()) active.put(job.id);
        result.put("active", active);
        call.resolve(result);
    }

    /** {id, folder, title, pages: [{name, url}]} queues a chapter. */
    @PluginMethod
    public void enqueue(PluginCall call) {
        String id = call.getString("id");
        String folder = call.getString("folder");
        String title = call.getString("title", "Downloading");
        JSArray pages = call.getArray("pages");
        if (id == null || folder == null || pages == null) {
            call.reject("id, folder and pages are required", "bad_request");
            return;
        }
        try {
            if (OfflineDownloader.get(getContext()).folder(folder) == null) {
                call.reject("Bad folder", "bad_request");
                return;
            }
            List<String[]> list = new ArrayList<>();
            JSONArray array = pages;
            for (int i = 0; i < array.length(); i++) {
                JSONObject page = array.getJSONObject(i);
                String url = page.getString("url");
                String name = page.getString("name");
                if (!(url.startsWith("http://") || url.startsWith("https://")) || !name.matches("[A-Za-z0-9_-]+")) {
                    call.reject("Bad page " + name, "bad_request");
                    return;
                }
                list.add(new String[] { name, url });
            }
            OfflineDownloader.get(getContext()).enqueue(new OfflineDownloader.Job(id, folder, title, list));
            call.resolve();
        } catch (Exception error) {
            call.reject(error.getMessage(), "bad_request", error);
        }
    }

    @PluginMethod
    public void cancel(PluginCall call) {
        OfflineDownloader.get(getContext()).cancel(call.getString("id", ""));
        call.resolve();
    }

    /** Deletes a folder of downloads (a chapter, a manga, or a server). */
    @PluginMethod
    public void remove(PluginCall call) {
        try {
            File folder = OfflineDownloader.get(getContext()).folder(call.getString("folder", ""));
            if (folder == null || folder.equals(OfflineDownloader.get(getContext()).root())) {
                call.reject("Bad folder", "bad_request");
                return;
            }
            OfflineDownloader.delete(folder);
            call.resolve();
        } catch (Exception error) {
            call.reject(error.getMessage(), "remove_failed", error);
        }
    }

    /** Bytes used, for {folder} or for all downloads. */
    @PluginMethod
    public void usage(PluginCall call) {
        new Thread(() -> {
            try {
                String relative = call.getString("folder");
                File folder = relative == null ? OfflineDownloader.get(getContext()).root() : OfflineDownloader.get(getContext()).folder(relative);
                JSObject result = new JSObject();
                result.put("bytes", folder == null ? 0 : OfflineDownloader.size(folder));
                call.resolve(result);
            } catch (Exception error) {
                call.reject(error.getMessage(), "usage_failed", error);
            }
        }).start();
    }
}
