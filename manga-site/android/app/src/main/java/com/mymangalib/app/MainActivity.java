package com.mymangalib.app;

import android.os.Bundle;
import android.view.ViewGroup.MarginLayoutParams;
import android.webkit.WebView;

import androidx.core.graphics.Insets;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowInsetsCompat;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        // Plugins that live in this app (not in npm packages) are registered here
        registerPlugin(ApkUpdaterPlugin.class);
        registerPlugin(OfflinePlugin.class);
        registerPlugin(AppLockPlugin.class);
        registerPlugin(AppSharePlugin.class);
        super.onCreate(savedInstanceState);
        fitWebViewAboveKeyboard();
    }

    // Android 15 draws apps edge to edge, and the window no longer shrinks for the keyboard.
    // Capacitor's margins ("adjustMarginsForEdgeToEdge") cover only the system bars, so the
    // keyboard hid the inputs under it. This replaces its listener and also keeps the WebView
    // above the keyboard, so the page can scroll the focused field into view.
    private void fitWebViewAboveKeyboard() {
        WebView webView = getBridge().getWebView();
        ViewCompat.setOnApplyWindowInsetsListener(webView, (view, windowInsets) -> {
            Insets bars = windowInsets.getInsets(WindowInsetsCompat.Type.systemBars() | WindowInsetsCompat.Type.displayCutout());
            Insets keyboard = windowInsets.getInsets(WindowInsetsCompat.Type.ime());
            MarginLayoutParams params = (MarginLayoutParams) view.getLayoutParams();
            params.leftMargin = bars.left;
            params.topMargin = bars.top;
            params.rightMargin = bars.right;
            params.bottomMargin = Math.max(bars.bottom, keyboard.bottom);
            view.setLayoutParams(params);
            return WindowInsetsCompat.CONSUMED;
        });
        ViewCompat.requestApplyInsets(webView);
    }
}
