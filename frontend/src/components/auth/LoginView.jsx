import React from "react";
import {
  Activity,
  Settings,
  ShieldCheck,
  RefreshCw,
  KeyRound,
  Eye,
  EyeOff,
  Lock
} from "lucide-react";
import ServerConfigModal from "./ServerConfigModal";

export default function LoginView({
  serverUrl,
  loginError,
  authSuccess,
  twoFactorRequired,
  twoFactorMethod,
  twoFactorEmailPreview,
  twoFactorCode,
  setTwoFactorCode,
  twoFactorLoading,
  handleVerify2FA,
  handleCancel2FA,
  loginForm,
  setLoginForm,
  showPassword,
  setShowPassword,
  handleLogin,
  showServerModal,
  setShowServerModal,
  serverInput,
  setServerInput,
  serverTestStatus,
  setServerTestStatus,
  testServerConnection,
  handleSaveServerUrl,
  renderProdUrl
}) {
  return (
    <div className="flex items-center justify-center min-h-screen bg-[#111827] px-4">
      <div className="w-full max-w-md bg-white rounded-2xl p-8 shadow-2xl border border-gray-800">
        <div className="flex flex-col items-center mb-6">
          <div className="w-14 h-14 rounded-2xl bg-[#F5A623] flex items-center justify-center font-black text-black text-2xl shadow-lg mb-3">
            S
          </div>
          <h2 className="text-2xl font-black text-gray-900">WhatsApp CRM</h2>
          <p className="text-xs text-gray-500 mt-0.5">Scalifts • Portal Access</p>
          <button
            type="button"
            onClick={() => {
              setServerInput(serverUrl);
              if (setServerTestStatus) setServerTestStatus(null);
              setShowServerModal(true);
            }}
            className="mt-3 inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-medium bg-emerald-50 hover:bg-emerald-100 text-emerald-800 transition-colors border border-emerald-200 cursor-pointer shadow-xs"
          >
            <Activity className="w-3.5 h-3.5 text-emerald-600 animate-pulse" />
            <span>Server: <span className="font-mono font-semibold">{serverUrl || "Local Relative"}</span></span>
            <Settings className="w-3 h-3 text-emerald-500 ml-0.5" />
          </button>
        </div>

        {loginError && (
          <div className="mb-4 p-3 rounded-lg bg-red-50 border border-red-200 text-red-600 text-xs font-semibold">
            {loginError}
          </div>
        )}

        {authSuccess && (
          <div className="mb-4 p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs font-semibold">
            {authSuccess}
          </div>
        )}

        {twoFactorRequired ? (
          /* 2FA Challenge View */
          <div className="space-y-4">
            <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-center space-y-1">
              <div className="w-10 h-10 rounded-full bg-emerald-100 flex items-center justify-center mx-auto text-emerald-600 mb-2">
                <ShieldCheck className="w-6 h-6" />
              </div>
              <h3 className="font-bold text-gray-900 text-sm">Two-Factor Authentication</h3>
              <p className="text-xs text-gray-600">
                {twoFactorMethod === "email"
                  ? `Enter the emergency 6-digit code sent to ${twoFactorEmailPreview || "your email"}`
                  : "Enter the 6-digit code from Google Authenticator"}
              </p>
            </div>

            <form onSubmit={handleVerify2FA} className="space-y-4">
              <div>
                <label className="block text-xs font-bold uppercase text-gray-700 mb-1 text-center">
                  6-Digit Security Code
                </label>
                <input
                  type="text"
                  inputMode="numeric"
                  autoFocus
                  required
                  maxLength={8}
                  placeholder="000000"
                  value={twoFactorCode}
                  onChange={(e) => setTwoFactorCode(e.target.value.replace(/\D/g, ""))}
                  className="w-full text-center tracking-[12px] font-mono text-2xl font-bold py-3 px-4 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#25D366]"
                />
              </div>

              <button
                type="submit"
                disabled={twoFactorLoading || twoFactorCode.length < 6}
                className="w-full flex items-center justify-center gap-2 bg-[#25D366] hover:bg-[#1EBE5D] text-white font-bold py-2.5 rounded-lg text-sm shadow-md transition disabled:opacity-50"
              >
                {twoFactorLoading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <KeyRound className="w-4 h-4" />}
                Verify & Sign In
              </button>
            </form>

            <div className="pt-2 border-t border-gray-100 flex flex-col items-center gap-2 text-xs">
              <div className="p-2.5 rounded-lg bg-amber-50 border border-amber-200 text-center">
                <p className="text-xs text-amber-800">
                  Lost access to your Authenticator device?
                </p>
                <p className="text-[11px] text-amber-900 font-semibold mt-0.5">
                  Contact your System Admin to disable 2FA for your account so you can log in.
                </p>
              </div>

              <button
                type="button"
                onClick={handleCancel2FA}
                className="text-gray-400 hover:text-gray-600 text-[11px] pt-1"
              >
                ← Cancel and return to sign in
              </button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-xs font-bold uppercase text-gray-700 mb-1">
                Username
              </label>
              <input
                type="text"
                required
                placeholder="Enter username"
                value={loginForm.username}
                onChange={(e) => setLoginForm({ ...loginForm, username: e.target.value })}
                className="w-full px-3.5 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#25D366]"
              />
            </div>

            <div>
              <label className="block text-xs font-bold uppercase text-gray-700 mb-1">
                Password
              </label>
              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"}
                  required
                  placeholder="Enter password"
                  value={loginForm.password}
                  onChange={(e) => setLoginForm({ ...loginForm, password: e.target.value })}
                  className="w-full pl-3.5 pr-10 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#25D366]"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-700 focus:outline-none p-0.5"
                  title={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? (
                    <EyeOff className="w-4 h-4" />
                  ) : (
                    <Eye className="w-4 h-4" />
                  )}
                </button>
              </div>
            </div>

            <button
              type="submit"
              className="w-full flex items-center justify-center gap-2 bg-[#25D366] hover:bg-[#1EBE5D] text-white font-bold py-2.5 rounded-lg text-sm shadow-md transition"
            >
              <Lock className="w-4 h-4" />
              Sign In Securely
            </button>

            <div className="text-center pt-2">
              <p className="text-xs text-gray-500">
                Forgot password or lost 2FA?{" "}
                <span className="text-gray-700 font-semibold">Contact your Administrator</span> to reset credentials.
              </p>
            </div>
          </form>
        )}

        <div className="mt-5 pt-3 border-t border-gray-100 text-center">
          <span className="text-[11px] text-gray-400 font-medium">Protected by End-to-End Bcrypt & JWT Security • Admin-Managed Access</span>
        </div>
      </div>

      <ServerConfigModal
        isOpen={showServerModal}
        onClose={() => setShowServerModal(false)}
        serverInput={serverInput}
        setServerInput={setServerInput}
        serverTestStatus={serverTestStatus}
        testServerConnection={testServerConnection}
        onSaveServerUrl={handleSaveServerUrl}
        renderProdUrl={renderProdUrl}
      />
    </div>
  );
}
