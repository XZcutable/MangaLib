package com.mymangalib.app;

import android.app.Activity;
import android.content.ClipData;
import android.content.ContentResolver;
import android.content.ContentValues;
import android.content.Intent;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.database.Cursor;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.provider.DocumentsContract;
import android.provider.MediaStore;
import android.provider.OpenableColumns;

import androidx.activity.result.ActivityResult;
import androidx.core.content.FileProvider;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.ActivityCallback;
import com.getcapacitor.annotation.CapacitorPlugin;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.Set;

/**
 * Passing the app between phones without internet: share the installed APK through Android's share sheet
 * (Quick Share, Bluetooth...), check an APK someone sent before installing it, and save a backup that
 * survives uninstalling (needed when a build is signed with another key or is older). Backups go to
 * Download/myMangaLib, where files stay after the app is removed.
 * The JS side (lib/appShare.js) decides what to do with what this reports.
 */
@CapacitorPlugin(name = "AppShare")
public class AppSharePlugin extends Plugin {

    /** SHA-256 of the certificate official releases are signed with (from GitHub Releases). */
    static final String OFFICIAL_SIGNER = "2e8a19263882698d22c795f2766f7150e90f1628a945b71899cdb465bcd34fd8";

    private static final String APK_TYPE = "application/vnd.android.package-archive";
    private static final String SHARE_FOLDER = "share";
    // Inside the updater's folder, so ApkUpdater.install accepts the file
    private static final String RECEIVED_FOLDER = "updates/received";
    private static final int MAX_BACKUP_BYTES = 1024 * 1024;

    /** Opens the share sheet with a copy of the installed app. */
    @PluginMethod
    public void shareApp(PluginCall call) {
        new Thread(() -> {
            try {
                ApplicationInfo app = getContext().getApplicationInfo();
                if (app.splitSourceDirs != null && app.splitSourceDirs.length > 0) {
                    call.reject("This copy of the app is split into several files and can't be shared. Install it from GitHub Releases first.", "split_apk");
                    return;
                }
                File folder = freshFolder(SHARE_FOLDER);
                File copy = new File(folder, "myMangaLib-" + installedInfo().versionName + ".apk");
                copyFile(new File(app.sourceDir), copy);

                Uri uri = FileProvider.getUriForFile(getContext(), getContext().getPackageName() + ".fileprovider", copy);
                Intent send = new Intent(Intent.ACTION_SEND);
                send.setType(APK_TYPE);
                send.putExtra(Intent.EXTRA_STREAM, uri);
                send.setClipData(ClipData.newRawUri("", uri));
                send.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                Intent chooser = Intent.createChooser(send, "Share myMangaLib");
                chooser.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                getActivity().runOnUiThread(() -> {
                    getActivity().startActivity(chooser);
                    call.resolve();
                });
            } catch (Exception error) {
                call.reject("Couldn't share the app: " + error.getMessage(), "share_failed", error);
            }
        }).start();
    }

    /** Lets the user pick an APK, copies it into the app and reports what it is (see inspect). */
    @PluginMethod
    public void pickApk(PluginCall call) {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("*/*");
        intent.putExtra(Intent.EXTRA_MIME_TYPES, new String[] { APK_TYPE, "application/octet-stream" });
        startActivityForResult(call, intent, "apkPicked");
    }

    @ActivityCallback
    private void apkPicked(PluginCall call, ActivityResult result) {
        if (call == null) return;
        Uri uri = pickedUri(result);
        if (uri == null) {
            call.resolve(cancelled());
            return;
        }
        new Thread(() -> {
            try {
                File folder = freshFolder(RECEIVED_FOLDER);
                File apk = new File(folder, "received.apk");
                try (InputStream in = getContext().getContentResolver().openInputStream(uri);
                     OutputStream out = new FileOutputStream(apk)) {
                    copy(in, out);
                }
                JSObject info = inspect(apk);
                info.put("fileName", displayName(uri));
                call.resolve(info);
            } catch (Exception error) {
                call.reject("Couldn't read that file: " + error.getMessage(), "read_failed", error);
            }
        }).start();
    }

    /**
     * What an APK is compared with the installed app: package, versions, and who signed it.
     * signatureKnown is false on Android versions that can't read signatures from a file that isn't installed.
     */
    private JSObject inspect(File apk) throws Exception {
        PackageManager packages = getContext().getPackageManager();
        int flags = Build.VERSION.SDK_INT >= Build.VERSION_CODES.P ? PackageManager.GET_SIGNING_CERTIFICATES : PackageManager.GET_SIGNATURES;
        PackageInfo file = packages.getPackageArchiveInfo(apk.getAbsolutePath(), flags);
        PackageInfo installed = packages.getPackageInfo(getContext().getPackageName(), flags);

        JSObject info = new JSObject();
        info.put("path", apk.getAbsolutePath());
        info.put("installedVersionName", installed.versionName);
        info.put("installedVersionCode", ApkUpdaterPlugin.versionCode(installed));
        Set<String> installedSigners = ApkUpdaterPlugin.signers(installed);
        info.put("installedOfficial", installedSigners.contains(OFFICIAL_SIGNER));
        if (file == null) {
            info.put("valid", false);
            return info;
        }
        long code = ApkUpdaterPlugin.versionCode(file);
        long installedCode = ApkUpdaterPlugin.versionCode(installed);
        Set<String> fileSigners = ApkUpdaterPlugin.signers(file);
        boolean known = !fileSigners.isEmpty();

        info.put("valid", true);
        info.put("packageName", file.packageName);
        info.put("samePackage", getContext().getPackageName().equals(file.packageName));
        info.put("versionName", file.versionName);
        info.put("versionCode", code);
        info.put("newer", code > installedCode);
        info.put("sameVersion", code == installedCode);
        info.put("signatureKnown", known);
        info.put("sameSigner", known && fileSigners.equals(installedSigners));
        info.put("official", known && fileSigners.size() == 1 && fileSigners.contains(OFFICIAL_SIGNER));
        return info;
    }

    /** Where backup files go: Download/myMangaLib, or (Android 9 and older) a folder the user picks. */
    private interface BackupTarget {
        void write(String type, String name, InputStream in) throws Exception;
        String folderName();
    }

    /**
     * Saves a backup that survives uninstalling the app: {data} as JSON, a copy of the installed app
     * (to go back to), and optionally the APK about to be installed ({newApkPath}).
     * Android 10+ writes to Download/myMangaLib without asking. Older versions ask for a folder, since
     * writing to Download directly would need the storage permission there.
     */
    @PluginMethod
    public void backup(PluginCall call) {
        if (call.getString("data") == null) {
            call.reject("Nothing to back up", "bad_request");
            return;
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            new Thread(() -> writeBackup(call, downloadsTarget())).start();
        } else {
            startActivityForResult(call, new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE), "backupFolderPicked");
        }
    }

    @ActivityCallback
    private void backupFolderPicked(PluginCall call, ActivityResult result) {
        if (call == null) return;
        Uri tree = pickedUri(result);
        if (tree == null) {
            call.resolve(cancelled());
            return;
        }
        new Thread(() -> writeBackup(call, treeTarget(tree))).start();
    }

    private BackupTarget downloadsTarget() {
        String folder = Environment.DIRECTORY_DOWNLOADS + "/myMangaLib";
        return new BackupTarget() {
            public void write(String type, String name, InputStream in) throws Exception {
                ContentResolver resolver = getContext().getContentResolver();
                ContentValues values = new ContentValues();
                values.put(MediaStore.MediaColumns.DISPLAY_NAME, name);
                values.put(MediaStore.MediaColumns.MIME_TYPE, type);
                values.put(MediaStore.MediaColumns.RELATIVE_PATH, folder);
                values.put(MediaStore.MediaColumns.IS_PENDING, 1);
                Uri file = resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values);
                if (file == null) throw new Exception("couldn't create " + name);
                try (OutputStream out = resolver.openOutputStream(file)) {
                    if (out == null) throw new Exception("couldn't write " + name);
                    copy(in, out);
                } catch (Exception error) {
                    resolver.delete(file, null, null);
                    throw error;
                }
                values.clear();
                values.put(MediaStore.MediaColumns.IS_PENDING, 0);
                resolver.update(file, values, null, null);
            }

            public String folderName() {
                return folder;
            }
        };
    }

    private BackupTarget treeTarget(Uri tree) {
        ContentResolver resolver = getContext().getContentResolver();
        Uri folder = DocumentsContract.buildDocumentUriUsingTree(tree, DocumentsContract.getTreeDocumentId(tree));
        return new BackupTarget() {
            public void write(String type, String name, InputStream in) throws Exception {
                writeDocument(resolver, folder, type, name, in);
            }

            public String folderName() {
                return displayName(folder);
            }
        };
    }

    private void writeBackup(PluginCall call, BackupTarget target) {
        try {
            String stamp = new SimpleDateFormat("yyyy-MM-dd-HHmm", Locale.US).format(new Date());
            String installedVersion = installedInfo().versionName;

            String backupName = "myMangaLib-backup-" + stamp + ".json";
            target.write("application/json", backupName,
                new java.io.ByteArrayInputStream(call.getString("data").getBytes(StandardCharsets.UTF_8)));

            String currentName = "myMangaLib-" + installedVersion + ".apk";
            try (InputStream in = new FileInputStream(getContext().getApplicationInfo().sourceDir)) {
                target.write(APK_TYPE, currentName, in);
            }

            String newName = null;
            String newPath = call.getString("newApkPath");
            if (newPath != null) {
                File apk = new File(newPath);
                File received = new File(getContext().getCacheDir(), RECEIVED_FOLDER);
                if (!apk.getCanonicalPath().startsWith(received.getCanonicalPath())) throw new Exception("unknown file");
                String newVersion = call.getString("newVersion");
                newName = "myMangaLib-" + (newVersion == null ? "new" : newVersion) + "-to-install.apk";
                try (InputStream in = new FileInputStream(apk)) {
                    target.write(APK_TYPE, newName, in);
                }
            }

            JSObject saved = new JSObject();
            saved.put("folder", target.folderName());
            saved.put("backup", backupName);
            saved.put("currentApk", currentName);
            saved.put("newApk", newName);
            call.resolve(saved);
        } catch (Exception error) {
            call.reject("Couldn't save the backup: " + error.getMessage(), "backup_failed", error);
        }
    }

    /** Lets the user pick a backup file and returns its text. */
    @PluginMethod
    public void pickBackup(PluginCall call) {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("*/*");
        intent.putExtra(Intent.EXTRA_MIME_TYPES, new String[] { "application/json", "text/plain", "application/octet-stream" });
        startActivityForResult(call, intent, "backupPicked");
    }

    @ActivityCallback
    private void backupPicked(PluginCall call, ActivityResult result) {
        if (call == null) return;
        Uri uri = pickedUri(result);
        if (uri == null) {
            call.resolve(cancelled());
            return;
        }
        new Thread(() -> {
            try (InputStream in = getContext().getContentResolver().openInputStream(uri)) {
                ByteArrayOutputStream bytes = new ByteArrayOutputStream();
                byte[] buffer = new byte[16 * 1024];
                int read;
                while ((read = in.read(buffer)) != -1) {
                    bytes.write(buffer, 0, read);
                    if (bytes.size() > MAX_BACKUP_BYTES) throw new Exception("the file is too big to be a backup");
                }
                JSObject text = new JSObject();
                text.put("text", bytes.toString("UTF-8"));
                call.resolve(text);
            } catch (Exception error) {
                call.reject("Couldn't read that file: " + error.getMessage(), "read_failed", error);
            }
        }).start();
    }

    /** Opens Android's "uninstall this app?" screen for myMangaLib. */
    @PluginMethod
    public void uninstall(PluginCall call) {
        Intent intent = new Intent(Intent.ACTION_DELETE, Uri.parse("package:" + getContext().getPackageName()));
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        getContext().startActivity(intent);
        call.resolve();
    }

    // --- Helpers ---

    private PackageInfo installedInfo() throws PackageManager.NameNotFoundException {
        return getContext().getPackageManager().getPackageInfo(getContext().getPackageName(), 0);
    }

    private static Uri pickedUri(ActivityResult result) {
        if (result.getResultCode() != Activity.RESULT_OK || result.getData() == null) return null;
        return result.getData().getData();
    }

    private static JSObject cancelled() {
        JSObject result = new JSObject();
        result.put("cancelled", true);
        return result;
    }

    private File freshFolder(String name) {
        File folder = new File(getContext().getCacheDir(), name);
        File[] old = folder.listFiles();
        if (old != null) {
            for (File file : old) {
                if (file.isFile()) file.delete();
            }
        }
        folder.mkdirs();
        return folder;
    }

    private String displayName(Uri uri) {
        try (Cursor cursor = getContext().getContentResolver().query(uri, new String[] { OpenableColumns.DISPLAY_NAME }, null, null, null)) {
            if (cursor != null && cursor.moveToFirst()) return cursor.getString(0);
        } catch (Exception ignored) {
            // Some providers don't report names
        }
        return null;
    }

    private static void writeDocument(ContentResolver resolver, Uri folder, String type, String name, InputStream in) throws Exception {
        Uri document = DocumentsContract.createDocument(resolver, folder, type, name);
        if (document == null) throw new Exception("couldn't create " + name);
        try (OutputStream out = resolver.openOutputStream(document)) {
            if (out == null) throw new Exception("couldn't write " + name);
            copy(in, out);
        }
    }

    private static void copyFile(File from, File to) throws Exception {
        try (InputStream in = new FileInputStream(from); OutputStream out = new FileOutputStream(to)) {
            copy(in, out);
        }
    }

    private static void copy(InputStream in, OutputStream out) throws Exception {
        byte[] buffer = new byte[64 * 1024];
        int read;
        while ((read = in.read(buffer)) != -1) out.write(buffer, 0, read);
    }
}
