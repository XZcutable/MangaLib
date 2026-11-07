package com.mymangalib.app;

import android.content.Intent;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.content.pm.Signature;
import android.net.Uri;
import android.os.Build;
import android.provider.Settings;

import androidx.core.content.FileProvider;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.security.MessageDigest;
import java.util.HashSet;
import java.util.Set;

/**
 * Downloads a new APK and hands it to Android's installer. Android always shows its own
 * confirmation screen; apps installed outside the Play Store can't update silently.
 */
@CapacitorPlugin(name = "ApkUpdater")
public class ApkUpdaterPlugin extends Plugin {

    private static final String UPDATE_FOLDER = "updates";

    /** Whether Android lets this app open the installer ("Install unknown apps" for myMangaLib). */
    @PluginMethod
    public void canInstall(PluginCall call) {
        JSObject result = new JSObject();
        boolean allowed = Build.VERSION.SDK_INT < Build.VERSION_CODES.O
            || getContext().getPackageManager().canRequestPackageInstalls();
        result.put("allowed", allowed);
        call.resolve(result);
    }

    /** Opens the system page where the user allows this app to install updates. */
    @PluginMethod
    public void openInstallSettings(PluginCall call) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            Intent intent = new Intent(
                Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                Uri.parse("package:" + getContext().getPackageName())
            );
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            getContext().startActivity(intent);
        }
        call.resolve();
    }

    /**
     * Downloads {url} into the app's cache. Sends "downloadProgress" events with {received, total}
     * and resolves with {path, sha256}.
     */
    @PluginMethod
    public void download(PluginCall call) {
        String url = call.getString("url");
        String fileName = call.getString("fileName", "update.apk");
        // GitHub downloads are https. Plain http is allowed for testing against a local server;
        // either way the APK must be signed with the installed app's key or Android refuses it.
        if (url == null || !(url.startsWith("https://") || url.startsWith("http://"))) {
            call.reject("A download link is required", "bad_url");
            return;
        }

        new Thread(() -> {
            File folder = new File(getContext().getCacheDir(), UPDATE_FOLDER);
            File[] old = folder.listFiles();
            if (old != null) {
                for (File file : old) file.delete(); // Only the newest download is kept
            }
            folder.mkdirs();
            File target = new File(folder, new File(fileName).getName());

            HttpURLConnection connection = null;
            try {
                connection = (HttpURLConnection) new URL(url).openConnection();
                connection.setInstanceFollowRedirects(true); // GitHub redirects downloads to its file host
                connection.setConnectTimeout(15000);
                connection.setReadTimeout(30000);
                connection.setRequestProperty("Accept", "application/octet-stream");
                int status = connection.getResponseCode();
                if (status != HttpURLConnection.HTTP_OK) {
                    call.reject("Download failed (" + status + ")", "download_failed");
                    return;
                }

                long total = connection.getContentLengthLong();
                MessageDigest digest = MessageDigest.getInstance("SHA-256");
                long received = 0;
                int lastPercent = -1;
                try (InputStream in = connection.getInputStream(); OutputStream out = new FileOutputStream(target)) {
                    byte[] buffer = new byte[64 * 1024];
                    int read;
                    while ((read = in.read(buffer)) != -1) {
                        out.write(buffer, 0, read);
                        digest.update(buffer, 0, read);
                        received += read;
                        int percent = total > 0 ? (int) (received * 100 / total) : -1;
                        if (percent != lastPercent) {
                            lastPercent = percent;
                            JSObject progress = new JSObject();
                            progress.put("received", received);
                            progress.put("total", total);
                            notifyListeners("downloadProgress", progress);
                        }
                    }
                }

                JSObject result = new JSObject();
                result.put("path", target.getAbsolutePath());
                result.put("sha256", toHex(digest.digest()));
                call.resolve(result);
            } catch (Exception error) {
                target.delete();
                call.reject("Download failed: " + error.getMessage(), "download_failed", error);
            } finally {
                if (connection != null) connection.disconnect();
            }
        }).start();
    }

    /**
     * Checks the downloaded APK and opens Android's install screen for it. Rejects with a clear
     * reason when it would be refused anyway: another app, not newer, or signed with a different key.
     */
    @PluginMethod
    public void install(PluginCall call) {
        String path = call.getString("path");
        File apk = path == null ? null : new File(path);
        File folder = new File(getContext().getCacheDir(), UPDATE_FOLDER);
        try {
            if (apk == null || !apk.isFile() || !apk.getCanonicalPath().startsWith(folder.getCanonicalPath())) {
                call.reject("The downloaded update is missing", "missing_file");
                return;
            }

            PackageManager packages = getContext().getPackageManager();
            String packageName = getContext().getPackageName();
            int flags = Build.VERSION.SDK_INT >= Build.VERSION_CODES.P
                ? PackageManager.GET_SIGNING_CERTIFICATES
                : PackageManager.GET_SIGNATURES;
            PackageInfo update = packages.getPackageArchiveInfo(apk.getAbsolutePath(), flags);
            PackageInfo installed = packages.getPackageInfo(packageName, flags);

            if (update == null || !packageName.equals(update.packageName)) {
                call.reject("The download isn't a myMangaLib update", "wrong_package");
                return;
            }
            if (versionCode(update) <= versionCode(installed)) {
                call.reject("The download isn't newer than this version", "not_newer");
                return;
            }
            // Some Android versions can't read signatures from a file that isn't installed yet.
            // Then the installer itself is the check, it refuses a mismatched key.
            Set<String> updateSigners = signers(update);
            if (!updateSigners.isEmpty() && !updateSigners.equals(signers(installed))) {
                call.reject(
                    "This update is signed with a different key than the installed app. Uninstall the app once, then install the update.",
                    "signature_mismatch"
                );
                return;
            }

            Uri uri = FileProvider.getUriForFile(getContext(), packageName + ".fileprovider", apk);
            Intent intent = new Intent(Intent.ACTION_VIEW);
            intent.setDataAndType(uri, "application/vnd.android.package-archive");
            intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
            getContext().startActivity(intent);
            call.resolve();
        } catch (Exception error) {
            call.reject("Couldn't start the install: " + error.getMessage(), "install_failed", error);
        }
    }

    static long versionCode(PackageInfo info) {
        return Build.VERSION.SDK_INT >= Build.VERSION_CODES.P ? info.getLongVersionCode() : info.versionCode;
    }

    static Set<String> signers(PackageInfo info) throws Exception {
        Signature[] signatures;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            signatures = info.signingInfo == null ? new Signature[0]
                : info.signingInfo.hasMultipleSigners()
                    ? info.signingInfo.getApkContentsSigners()
                    : info.signingInfo.getSigningCertificateHistory();
        } else {
            signatures = info.signatures == null ? new Signature[0] : info.signatures;
        }
        Set<String> result = new HashSet<>();
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        for (Signature signature : signatures) {
            result.add(toHex(digest.digest(signature.toByteArray())));
        }
        return result;
    }

    static String toHex(byte[] bytes) {
        StringBuilder hex = new StringBuilder();
        for (byte value : bytes) hex.append(String.format("%02x", value));
        return hex.toString();
    }
}
