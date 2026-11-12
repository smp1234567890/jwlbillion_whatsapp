package com.jwlbillion.whatsappcrm;

import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.media.AudioManager;
import android.os.Build;
import android.util.Log;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

@CapacitorPlugin(name = "LiveChatSync")
public class LiveChatSyncPlugin extends Plugin {
    private static final String TAG = "LiveChatSyncPlugin";

    @PluginMethod
    public void setSpeakerphoneOn(PluginCall call) {
        try {
            boolean enabled = call.getBoolean("enabled", true);
            Context ctx = getContext();
            AudioManager audioManager = (AudioManager) ctx.getSystemService(Context.AUDIO_SERVICE);
            if (audioManager != null) {
                audioManager.setMode(AudioManager.MODE_IN_COMMUNICATION);
                audioManager.setSpeakerphoneOn(enabled);
            }
            JSObject ret = new JSObject();
            ret.put("speakerphoneOn", enabled);
            call.resolve(ret);
        } catch (Exception e) {
            Log.e(TAG, "Failed to toggle speakerphone: " + e.getMessage());
            call.reject("Failed to toggle speakerphone", e);
        }
    }

    @PluginMethod
    public void startSync(PluginCall call) {
        try {
            String token = call.getString("token", "");
            if (token != null && !token.isEmpty()) {
                SharedPreferences prefs = getContext().getSharedPreferences(getContext().getPackageName() + "_preferences", Context.MODE_PRIVATE);
                prefs.edit().putString("token", token).apply();
            }

            Intent serviceIntent = new Intent(getContext(), LiveChatSyncService.class);
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                getContext().startForegroundService(serviceIntent);
            } else {
                getContext().startService(serviceIntent);
            }

            JSObject ret = new JSObject();
            ret.put("status", "running");
            call.resolve(ret);
        } catch (Exception e) {
            Log.e(TAG, "Failed to start LiveChatSyncService: " + e.getMessage());
            call.reject("Failed to start sync service", e);
        }
    }

    @PluginMethod
    public void getPendingChat(PluginCall call) {
        try {
            SharedPreferences prefs = getContext().getSharedPreferences(getContext().getPackageName() + "_preferences", Context.MODE_PRIVATE);
            String phone = prefs.getString("pending_chat_phone", "");
            prefs.edit().remove("pending_chat_phone").apply();

            JSObject ret = new JSObject();
            ret.put("phone", phone);
            call.resolve(ret);
        } catch (Exception e) {
            call.reject("Failed to get pending chat", e);
        }
    }
}
