package com.jwlbillion.whatsappcrm;

import android.Manifest;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        registerPlugin(LiveChatSyncPlugin.class);
        super.onCreate(savedInstanceState);
        handleIntent(getIntent());

        // Explicitly request POST_NOTIFICATIONS on Android 13+ (API 33+)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                ActivityCompat.requestPermissions(this, new String[]{Manifest.permission.POST_NOTIFICATIONS}, 101);
            }
        }
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        handleIntent(intent);
    }

    private void handleIntent(Intent intent) {
        if (intent != null && intent.hasExtra("chat_phone")) {
            String phone = intent.getStringExtra("chat_phone");
            if (phone != null && !phone.isEmpty()) {
                SharedPreferences prefs = getSharedPreferences(getPackageName() + "_preferences", Context.MODE_PRIVATE);
                prefs.edit().putString("pending_chat_phone", phone).apply();
            }
        }
    }
}
