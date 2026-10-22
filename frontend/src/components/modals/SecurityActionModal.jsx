import React from "react";
import { ShieldCheck, AlertTriangle, RefreshCw, KeyRound, Clock, Lock } from "lucide-react";
import { formatScheduleDisplay } from "../../utils/dateUtils";

export default function SecurityActionModal({
  modalState,
  setModalState,
  onExecute
}) {
  if (!modalState.isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-gray-100 animate-in fade-in zoom-in duration-150">
        <div className="flex items-center justify-between pb-3 border-b border-gray-100">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-amber-100 text-amber-800 flex items-center justify-center">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-bold text-base text-gray-900">Security & 2FA Authorization</h3>
              <p className="text-[11px] text-gray-500">Step-up verification required for mass actions</p>
            </div>
          </div>
          <button
            onClick={() => setModalState((prev) => ({ ...prev, isOpen: false }))}
            className="text-gray-400 hover:text-gray-600 font-bold text-lg"
          >
            ✕
          </button>
        </div>

        {/* Target Summary Card */}
        <div className="mt-4 p-3.5 bg-gray-50 border border-gray-200 rounded-xl space-y-1.5 text-xs">
          <div className="flex items-center justify-between">
            <span className="text-gray-500 font-medium">Operation:</span>
            <span className="font-bold text-gray-900">
              {modalState.actionType === "CAMPAIGN" ? "WhatsApp Broadcast" : "High-Volume Automation"}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-gray-500 font-medium">Recipients Affected:</span>
            <span className="font-mono font-black text-red-600 bg-red-50 px-2 py-0.5 rounded border border-red-200">
              {modalState.recipientCount} Contacts
            </span>
          </div>
          {modalState.payloadData?.scheduled_for ? (
            <div className="flex items-center justify-between">
              <span className="text-gray-500 font-medium">Trigger Schedule:</span>
              <span className="font-bold text-amber-800 bg-amber-50 px-2 py-0.5 rounded border border-amber-200 flex items-center gap-1">
                <Clock className="w-3 h-3 text-amber-600" />
                {formatScheduleDisplay(modalState.payloadData.scheduled_for)?.formattedDate || modalState.payloadData.scheduled_for}
              </span>
            </div>
          ) : (
            <div className="flex items-center justify-between">
              <span className="text-gray-500 font-medium">Trigger Mode:</span>
              <span className="font-bold text-blue-700 bg-blue-50 px-2 py-0.5 rounded border border-blue-200">
                ⚡ Immediate Dispatch
              </span>
            </div>
          )}
          <div className="flex items-center justify-between">
            <span className="text-gray-500 font-medium">Safety Policy:</span>
            <span className="text-emerald-700 font-bold flex items-center gap-1">
              <Lock className="w-3 h-3" /> Mandatory Password + 2FA
            </span>
          </div>
        </div>

        {/* Error Message */}
        {modalState.error && (
          <div className="mt-3 p-3 bg-red-50 border border-red-200 text-red-700 text-xs font-semibold rounded-lg flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-red-500 flex-shrink-0" />
            <span>{modalState.error}</span>
          </div>
        )}

        {/* Verification Form */}
        <form onSubmit={onExecute} className="mt-4 space-y-3.5">
          <div>
            <label className="block text-xs font-bold uppercase text-gray-700 mb-1">
              Account Password
            </label>
            <input
              type="password"
              required
              placeholder="Enter your CRM login password"
              value={modalState.password}
              onChange={(e) =>
                setModalState((prev) => ({ ...prev, password: e.target.value }))
              }
              className="w-full px-3.5 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#25D366]"
            />
          </div>

          <div>
            <label className="block text-xs font-bold uppercase text-gray-700 mb-1 flex items-center justify-between">
              <span>6-Digit 2FA Code</span>
              <span className="text-[10px] text-gray-400 font-normal">Google Authenticator or Email OTP</span>
            </label>
            <input
              type="text"
              inputMode="numeric"
              maxLength={8}
              placeholder="000000"
              value={modalState.twoFactorCode}
              onChange={(e) =>
                setModalState((prev) => ({
                  ...prev,
                  twoFactorCode: e.target.value.replace(/\D/g, "")
                }))
              }
              className="w-full text-center tracking-[8px] font-mono text-xl font-bold px-3.5 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#25D366]"
            />
            <p className="text-[11px] text-gray-400 mt-1 text-center">
              If 2FA is not enabled on your user profile, leave empty or enter recovery code.
            </p>
          </div>

          <div className="pt-3 border-t border-gray-100 flex items-center justify-end gap-2.5">
            <button
              type="button"
              onClick={() => setModalState((prev) => ({ ...prev, isOpen: false }))}
              className="px-4 py-2 border border-gray-300 rounded-lg text-xs font-semibold text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={modalState.loading || !modalState.password}
              className="flex items-center gap-1.5 bg-[#25D366] hover:bg-[#1EBE5D] disabled:opacity-50 text-white px-5 py-2 rounded-lg font-bold text-xs shadow-md transition"
            >
              {modalState.loading ? (
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <KeyRound className="w-3.5 h-3.5" />
              )}
              Authorize & Dispatch
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
