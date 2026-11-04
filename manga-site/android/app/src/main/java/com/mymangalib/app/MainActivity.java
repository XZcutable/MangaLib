package com.mymangalib.app;

import android.os.Bundle;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        // Plugins that live in this app (not in npm packages) are registered here
        registerPlugin(ApkUpdaterPlugin.class);
        registerPlugin(OfflinePlugin.class);
        super.onCreate(savedInstanceState);
    }
}
