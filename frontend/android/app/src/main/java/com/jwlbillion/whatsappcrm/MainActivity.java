package com.jwlbillion.whatsappcrm;

import android.os.Bundle;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        registerPlugin(LiveChatSyncPlugin.class);
        super.onCreate(savedInstanceState);
    }
}
