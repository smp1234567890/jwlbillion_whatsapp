import React from "react";
import { Activity } from "lucide-react";

export default function ServerConfigModal({
  isOpen,
  onClose,
  serverInput,
  setServerInput,
  serverTestStatus,
  testServerConnection,
  onSaveServerUrl,
  renderProdUrl
}) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl p-6 w-full max-w-md shadow-2xl border border-gray-200 text-left">
        <div className="flex items-center justify-between mb-4 pb-3 border-b border-gray-100">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-emerald-100 text-emerald-700 flex items-center justify-center">
              <Activity className="w-4 h-4" />
            </div>
            <div>
              <h3 className="font-bold text-gray-900 text-sm">Configure Backend Server</h3>
              <p className="text-[11px] text-gray-500">Set API URL for Android or Remote Access</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-lg font-bold p-1 cursor-pointer"
          >
            ✕
          </button>
        </div>

        <div className="space-y-3 mb-4">
          <div>
            <label className="block text-xs font-semibold text-gray-700 mb-1">Server API URL</label>
            <input
              type="text"
              value={serverInput}
              onChange={(e) => setServerInput(e.target.value)}
              placeholder="https://your-api-domain.com or http://localhost:8000"
              className="w-full px-3 py-2 text-xs font-mono rounded-lg border border-gray-300 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
            />
          </div>

          <div>
            <p className="text-[11px] font-semibold text-gray-500 mb-1.5">Quick Presets:</p>
            <div className="space-y-1.5">
              {renderProdUrl && (
                <button
                  type="button"
                  onClick={() => setServerInput(renderProdUrl)}
                  className="w-full px-2.5 py-1.5 text-[11px] font-mono rounded bg-emerald-50 text-emerald-800 border border-emerald-300 hover:bg-emerald-100 text-left transition cursor-pointer font-semibold flex items-center justify-between"
                >
                  <span>☁️ Production Cloud API</span>
                  <span className="text-[10px] bg-emerald-200/60 px-1.5 py-0.5 rounded text-emerald-900">Default</span>
                </button>
              )}
              <div className="grid grid-cols-2 gap-1.5">
                <button
                  type="button"
                  onClick={() => setServerInput(`http://${typeof window !== 'undefined' ? (window.location?.hostname || "localhost") : "localhost"}:8000`)}
                  className="px-2.5 py-1.5 text-[11px] font-mono rounded bg-gray-50 hover:bg-gray-100 border border-gray-200 text-left transition cursor-pointer"
                >
                  📡 Local Machine<br /><span className="text-[10px] text-gray-500">{typeof window !== 'undefined' ? (window.location?.hostname || "localhost") : "localhost"}:8000</span>
                </button>
                <button
                  type="button"
                  onClick={() => setServerInput("http://10.0.2.2:8000")}
                  className="px-2.5 py-1.5 text-[11px] font-mono rounded bg-gray-50 hover:bg-gray-100 border border-gray-200 text-left transition cursor-pointer"
                >
                  📱 Android Emulator<br /><span className="text-[10px] text-gray-500">10.0.2.2:8000</span>
                </button>
              </div>
            </div>
          </div>

          {serverTestStatus && (
            <div
              className={`p-2.5 rounded-lg text-xs font-medium ${
                serverTestStatus.ok
                  ? "bg-emerald-50 text-emerald-800 border border-emerald-200"
                  : "bg-red-50 text-red-700 border border-red-200"
              }`}
            >
              {serverTestStatus.msg}
            </div>
          )}
        </div>

        <div className="flex gap-2 justify-end pt-3 border-t border-gray-100">
          <button
            type="button"
            onClick={() => testServerConnection(serverInput)}
            disabled={serverTestStatus?.loading}
            className="px-3 py-2 text-xs font-semibold rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-700 transition cursor-pointer"
          >
            {serverTestStatus?.loading ? "Testing..." : "Test Connection"}
          </button>
          <button
            type="button"
            onClick={() => onSaveServerUrl(serverInput)}
            className="px-4 py-2 text-xs font-bold rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white shadow-sm transition cursor-pointer"
          >
            Save & Apply
          </button>
        </div>
      </div>
    </div>
  );
}
