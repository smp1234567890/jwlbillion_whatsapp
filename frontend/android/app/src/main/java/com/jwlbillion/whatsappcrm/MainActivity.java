package com.jwlbillion.whatsappcrm;

import android.Manifest;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.content.ContentResolver;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.media.AudioAttributes;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    public static final String CHANNEL_MESSAGES = "jwl_incoming_messages_v4";

    @Override
    public void onCreate(Bundle savedInstanceState) {
        registerPlugin(LiveChatSyncPlugin.class);
        super.onCreate(savedInstanceState);
        createNotificationChannels();
        handleIntent(getIntent());

        // Explicitly request permissions (POST_NOTIFICATIONS on Android 13+, RECORD_AUDIO for voice notes)
        java.util.List<String> perms = new java.util.ArrayList<>();
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                perms.add(Manifest.permission.POST_NOTIFICATIONS);
            }
        }
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            perms.add(Manifest.permission.RECORD_AUDIO);
        }
        if (!perms.isEmpty()) {
            ActivityCompat.requestPermissions(this, perms.toArray(new String[0]), 101);
        }
    }

    private void createNotificationChannels() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationManager manager = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
            if (manager == null) return;

            Uri soundUri = Uri.parse(ContentResolver.SCHEME_ANDROID_RESOURCE + "://" + getPackageName() + "/" + R.raw.notification);

            AudioAttributes audioAttributes = new AudioAttributes.Builder()
                    .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                    .setUsage(AudioAttributes.USAGE_NOTIFICATION_COMMUNICATION_INSTANT)
                    .build();

            NotificationChannel msgChannel = new NotificationChannel(
                    CHANNEL_MESSAGES,
                    "WhatsApp Conversations",
                    NotificationManager.IMPORTANCE_HIGH
            );
            msgChannel.setDescription("Incoming WhatsApp customer messages");
            msgChannel.enableVibration(true);
            msgChannel.enableLights(true);
            msgChannel.setLockscreenVisibility(Notification.VISIBILITY_PUBLIC);
            msgChannel.setSound(soundUri, audioAttributes);
            manager.createNotificationChannel(msgChannel);
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
