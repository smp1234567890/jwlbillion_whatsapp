import React from "react";
import { ShieldCheck, RefreshCw } from "lucide-react";

export function TwoFactorSetupModal({
  isOpen,
  onClose,
  setupData,
  verifyCode,
  setVerifyCode,
  verifyLoading,
  verifyError,
  onConfirm
}) {
  if (!isOpen || !setupData) return null;

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-gray-200">
        <div className="flex items-center justify-between pb-4 border-b border-gray-100">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-50 text-[#10B981] flex items-center justify-center">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-bold text-base text-gray-900">Set Up Google Authenticator</h3>
              <p className="text-xs text-gray-500">Scan QR code with your mobile Authenticator app</p>
            </div>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 font-bold text-xl">✕</button>
        </div>

        <div className="mt-4 space-y-4 text-center">
          <p className="text-xs text-gray-600 text-left">
            1. Open <strong>Google Authenticator</strong> (or Apple Passwords / Authy) on your phone.
            <br />
            2. Tap <strong>+</strong> and scan the QR code below:
          </p>

          <div className="inline-block p-3 bg-white rounded-xl border border-gray-200 shadow-xs">
            <img
              src={setupData.qr_code_base64}
              alt="2FA QR Code"
              className="w-48 h-48 mx-auto"
            />
          </div>

          <div className="bg-gray-50 p-2.5 rounded-lg border border-gray-200 text-left">
            <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider block">Can't scan QR code? Manual Entry Key:</span>
            <span className="font-mono font-bold text-xs text-gray-800 select-all break-all">{setupData.secret}</span>
          </div>

          <form onSubmit={onConfirm} className="pt-2 space-y-3">
            <div className="text-left">
              <label className="block text-xs font-bold uppercase text-gray-700 mb-1">
                3. Enter 6-Digit Code from App to Confirm:
              </label>
              <input
                type="text"
                inputMode="numeric"
                required
                maxLength={8}
                placeholder="123456"
                value={verifyCode}
                onChange={(e) => setVerifyCode(e.target.value.replace(/\D/g, ""))}
                className="w-full text-center tracking-[8px] font-mono text-xl font-bold py-2.5 px-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#25D366]"
              />
            </div>

            {verifyError && (
              <p className="text-xs font-semibold text-red-600 bg-red-50 p-2 rounded-lg border border-red-200">
                {verifyError}
              </p>
            )}

            <div className="flex gap-2 pt-2">
              <button
                type="button"
                onClick={onClose}
                className="flex-1 py-2 border border-gray-300 rounded-lg text-xs font-semibold text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={verifyLoading || verifyCode.length < 6}
                className="flex-1 py-2 bg-[#25D366] hover:bg-[#1EBE5D] text-white rounded-lg text-xs font-bold shadow-xs transition flex items-center justify-center gap-1.5 disabled:opacity-50"
              >
                {verifyLoading ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <ShieldCheck className="w-3.5 h-3.5" />}
                Confirm & Enable
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}

export function TwoFactorDisableModal({
  isOpen,
  onClose,
  disablePassword,
  setDisablePassword,
  disableLoading,
  onSubmit
}) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-2xl max-w-sm w-full p-6 shadow-2xl border border-gray-200">
        <div className="flex items-center justify-between pb-3 border-b border-gray-100">
          <h3 className="font-bold text-base text-gray-900">Disable 2FA</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 font-bold text-xl">✕</button>
        </div>

        <p className="text-xs text-gray-500 mt-3 mb-4">
          Enter your current account password to confirm disabling Two-Factor Authentication.
        </p>

        <form onSubmit={onSubmit} className="space-y-3">
          <div>
            <label className="block text-xs font-bold uppercase text-gray-700 mb-1">Current Password</label>
            <input
              type="password"
              required
              placeholder="Enter current password"
              value={disablePassword}
              onChange={(e) => setDisablePassword(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-red-500"
            />
          </div>

          <div className="flex gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 py-2 border border-gray-300 rounded-lg text-xs font-semibold text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={disableLoading}
              className="flex-1 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg text-xs font-bold shadow-xs transition"
            >
              {disableLoading ? "Disabling..." : "Disable 2FA"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
