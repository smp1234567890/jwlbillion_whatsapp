package com.jwlbillion.whatsappcrm;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.ContentResolver;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.media.AudioAttributes;
import android.net.Uri;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.util.Log;

import androidx.annotation.Nullable;
import androidx.core.app.NotificationCompat;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;

public class LiveChatSyncService extends Service {
    private static final String TAG = "JWL_ChatSync";
    private static final String CHANNEL_FOREGROUND = "jwl_sync_channel";
    private static final String CHANNEL_MESSAGES = "jwl_incoming_messages_v2";
    private static final int FOREGROUND_NOTIFICATION_ID = 1001;

    private Handler handler;
    private Runnable pollRunnable;
    private boolean isRunning = false;
    private String lastKnownSignature = "";

    @Override
    public void onCreate() {
        super.onCreate();
        createNotificationChannels();
        handler = new Handler(Looper.getMainLooper());

        pollRunnable = new Runnable() {
            @Override
            public void run() {
                if (isRunning) {
                    new Thread(() -> checkIncomingMessages()).start();
                    // Poll backend every 3.5 seconds
                    handler.postDelayed(this, 3500);
                }
            }
        };
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (!isRunning) {
            isRunning = true;
            startForeground(FOREGROUND_NOTIFICATION_ID, buildForegroundNotification());
            handler.post(pollRunnable);
            Log.i(TAG, "LiveChatSyncService started in foreground");
        }
        return START_STICKY;
    }

    private void createNotificationChannels() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationManager manager = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
            if (manager == null) return;

            // Low-priority silent channel for background sync indicator
            NotificationChannel fgChannel = new NotificationChannel(
                    CHANNEL_FOREGROUND,
                    "Live Sync Service",
                    NotificationManager.IMPORTANCE_LOW
            );
            fgChannel.setDescription("Keeps JWL Whatsapp connected to receive messages when closed");
            fgChannel.setShowBadge(false);
            manager.createNotificationChannel(fgChannel);

            // Custom sound uri from raw resources
            Uri soundUri = Uri.parse(ContentResolver.SCHEME_ANDROID_RESOURCE + "://" + getPackageName() + "/" + R.raw.notification);

            AudioAttributes audioAttributes = new AudioAttributes.Builder()
                    .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                    .setUsage(AudioAttributes.USAGE_NOTIFICATION_COMMUNICATION_INSTANT)
                    .build();

            // High-priority channel with custom sound and vibration for new messages
            NotificationChannel msgChannel = new NotificationChannel(
                    CHANNEL_MESSAGES,
                    "Incoming WhatsApp Messages",
                    NotificationManager.IMPORTANCE_HIGH
            );
            msgChannel.setDescription("Alerts for customer WhatsApp replies");
            msgChannel.enableVibration(true);
            msgChannel.enableLights(true);
            msgChannel.setSound(soundUri, audioAttributes);
            manager.createNotificationChannel(msgChannel);
        }
    }

    private Notification buildForegroundNotification() {
        Intent notificationIntent = new Intent(this, MainActivity.class);
        PendingIntent pendingIntent = PendingIntent.getActivity(
                this, 0, notificationIntent,
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT
        );

        return new NotificationCompat.Builder(this, CHANNEL_FOREGROUND)
                .setContentTitle("JWL Whatsapp Active")
                .setContentText("Connected & listening for customer WhatsApp messages")
                .setSmallIcon(R.mipmap.ic_launcher)
                .setContentIntent(pendingIntent)
                .setOngoing(true)
                .setPriority(NotificationCompat.PRIORITY_LOW)
                .build();
    }

    private void checkIncomingMessages() {
        try {
            // Retrieve JWT token stored by webview localStorage (Bridge/Capacitor storage or fallback endpoint)
            SharedPreferences prefs = getSharedPreferences("CapacitorStorage", Context.MODE_PRIVATE);
            String token = prefs.getString("token", "");
            if (token == null || token.isEmpty()) {
                // Also check default preferences
                SharedPreferences defaultPrefs = getSharedPreferences(getPackageName() + "_preferences", Context.MODE_PRIVATE);
                token = defaultPrefs.getString("token", "");
            }

            URL url = new URL("https://jwl-whatsapp-crm.onrender.com/api/chat/conversations?limit=10");
            HttpURLConnection conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("GET");
            conn.setConnectTimeout(5000);
            conn.setReadTimeout(5000);
            if (token != null && !token.isEmpty()) {
                conn.setRequestProperty("Authorization", "Bearer " + token);
            }

            int responseCode = conn.getResponseCode();
            if (responseCode == 200) {
                BufferedReader reader = new BufferedReader(new InputStreamReader(conn.getInputStream()));
                StringBuilder sb = new StringBuilder();
                String line;
                while ((line = reader.readLine()) != null) {
                    sb.append(line);
                }
                reader.close();

                JSONArray convs = new JSONArray(sb.toString());
                if (convs.length() > 0) {
                    for (int i = 0; i < convs.length(); i++) {
                        JSONObject conv = convs.getJSONObject(i);
                        String sender = conv.optString("last_sender", "");
                        if ("CUSTOMER".equalsIgnoreCase(sender)) {
                            String phone = conv.optString("customer_phone", "");
                            String name = conv.optString("customer_name", phone);
                            String text = conv.optString("last_message_text", "Sent a message");
                            String time = conv.optString("last_message_time", "");
                            String sig = phone + ":" + time + ":" + text;

                            if (!lastKnownSignature.isEmpty() && !lastKnownSignature.equals(sig)) {
                                showIncomingMessageNotification(name, text, phone);
                            }
                            lastKnownSignature = sig;
                            break;
                        }
                    }
                }
            }
            conn.disconnect();
        } catch (Exception e) {
            Log.d(TAG, "Sync check: " + e.getMessage());
        }
    }

    private void showIncomingMessageNotification(String customerName, String messageText, String phone) {
        Intent intent = new Intent(this, MainActivity.class);
        intent.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        PendingIntent pendingIntent = PendingIntent.getActivity(
                this, (int) System.currentTimeMillis(), intent,
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT
        );

        Uri soundUri = Uri.parse(ContentResolver.SCHEME_ANDROID_RESOURCE + "://" + getPackageName() + "/" + R.raw.notification);

        Notification notification = new NotificationCompat.Builder(this, CHANNEL_MESSAGES)
                .setContentTitle(customerName)
                .setContentText(messageText)
                .setStyle(new NotificationCompat.BigTextStyle().bigText(messageText))
                .setSmallIcon(R.mipmap.ic_launcher)
                .setAutoCancel(true)
                .setContentIntent(pendingIntent)
                .setSound(soundUri)
                .setPriority(NotificationCompat.PRIORITY_HIGH)
                .setVibrate(new long[]{0, 200, 100, 200})
                .build();

        NotificationManager manager = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
        if (manager != null) {
            manager.notify((int) System.currentTimeMillis(), notification);
        }
    }

    @Override
    public void onDestroy() {
        isRunning = false;
        if (handler != null && pollRunnable != null) {
            handler.removeCallbacks(pollRunnable);
        }
        super.onDestroy();
    }

    @Nullable
    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
