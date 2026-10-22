import React, { useState } from "react";
import {
  Settings,
  ShieldCheck,
  ShieldAlert,
  UserPlus,
  RefreshCw,
  Trash2,
  Key,
  Users,
  Edit2,
  BookOpen,
  Copy,
  Check,
  Eye,
  EyeOff,
  Code,
  AlertTriangle,
  ExternalLink,
  Moon
} from "lucide-react";
import axios, { getApiBaseUrl } from "../api";
import { formatToIST } from "../utils/dateUtils";

export default function SettingsPage({
  systemSettings = {},
  setSystemSettings = () => {},
  currentUserProfile,
  setIsAddUserModalOpen = () => {},
  systemUsers = [],
  setSystemUsers = () => {},
  username,
  handleDeleteUser = () => {},
  userRoleUpdatingId,
  userDeletingId = null,
  handleUpdateUserRole = () => {},
  setAdminPasswordModal = () => {},
  admin2faUpdatingId,
  handleAdminToggle2FA = () => {},
  handleOpen2faSetup = () => {},
  handleOpen2faDisable = () => {},
  setIsRoleInfoModalOpen = () => {},
  setAddUserError = () => {}
}) {
  const [webhookCopied, setWebhookCopied] = useState(false);
  const [togglingQuietHours, setTogglingQuietHours] = useState(false);
  const [quietHoursLocal, setQuietHoursLocal] = useState(null);

  const isQuietHoursActive = quietHoursLocal !== null ? quietHoursLocal : Boolean(systemSettings?.quiet_hours_enabled);

  const handleToggleQuietHours = async () => {
    const nextState = !isQuietHoursActive;
    setTogglingQuietHours(true);
    try {
      const res = await axios.put("/api/settings/quiet-hours", { enabled: nextState });
      const updated = res.data?.quiet_hours_enabled ?? nextState;
      setQuietHoursLocal(updated);
      setSystemSettings(prev => ({ ...prev, quiet_hours_enabled: updated }));
    } catch (err) {
      console.error("Failed to toggle quiet hours:", err);
      alert("Failed to update quiet hours setting: " + (err.response?.data?.detail || err.message));
    } finally {
      setTogglingQuietHours(false);
    }
  };

  const loggedInUser = systemUsers.find(u => u.username === username) || (currentUserProfile ? { ...currentUserProfile, username } : null);
  const rawBase = getApiBaseUrl() || (typeof window !== "undefined" ? window.location.origin : "");
  const apiBaseUrl = rawBase.replace(/\/+$/, "");
  const webhookUrl = `${apiBaseUrl}/api/webhooks/cart-event`;

  const handleCopyWebhookUrl = (val) => {
    if (!val) return;
    navigator.clipboard.writeText(val);
    setWebhookCopied(true);
    setTimeout(() => setWebhookCopied(false), 2200);
  };

  return (
            <div className="space-y-6 w-full max-w-7xl">
              <div className="bg-white rounded-xl border border-gray-200 shadow-xs p-6">
                <div className="flex items-center gap-3 border-b border-gray-100 pb-4 mb-5">
                  <div className="w-10 h-10 rounded-xl bg-gray-100 flex items-center justify-center text-gray-700">
                    <Settings className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="font-bold text-gray-900 text-base">Platform & Integration Settings</h3>
                    <p className="text-xs text-gray-500">Security thresholds, webhook endpoints, and spend limit controls</p>
                  </div>
                </div>

                <div className="space-y-5 text-sm">
                  <div className="flex items-center justify-between p-4 rounded-xl bg-gray-50 border border-gray-200">
                    <div>
                      <h4 className="font-bold text-gray-900">Daily Outbound Message Limit (Spending Guardrail)</h4>
                      <p className="text-xs text-gray-500 mt-0.5">Maximum WhatsApp messages the system is allowed to send per 24 hours (Fixed)</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-bold text-base text-[#10B981] bg-white px-3 py-1 rounded-lg border border-gray-200 shadow-xs">
                        200 / Day
                      </span>
                      <span className="text-[11px] font-semibold text-gray-500 bg-gray-200/80 px-2 py-0.5 rounded-md border border-gray-300/60">
                        Fixed
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center justify-between p-4 rounded-xl bg-gray-50 border border-gray-200">
                    <div>
                      <div className="flex items-center gap-2">
                        <Moon className="w-4 h-4 text-indigo-600" />
                        <h4 className="font-bold text-gray-900">Quiet Hours Enforcement (21:00 – 09:00 IST)</h4>
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-md uppercase border ${
                          isQuietHoursActive 
                            ? "bg-amber-50 text-amber-700 border-amber-200" 
                            : "bg-blue-50 text-blue-700 border-blue-200"
                        }`}>
                          {isQuietHoursActive ? "Active (Production)" : "Lifted (Testing Mode)"}
                        </span>
                      </div>
                      <p className="text-xs text-gray-500 mt-0.5">
                        {isQuietHoursActive
                          ? "Promotional marketing messages are held during night hours (9:00 PM – 9:00 AM IST) for TRAI compliance."
                          : "Quiet hours restriction is currently LIFTED for testing. All messages and workflow automations dispatch 24/7."}
                      </p>
                    </div>
                    <div className="flex items-center gap-3">
                      <button
                        type="button"
                        disabled={togglingQuietHours}
                        onClick={handleToggleQuietHours}
                        className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                          isQuietHoursActive ? "bg-emerald-600" : "bg-gray-300"
                        }`}
                        title={isQuietHoursActive ? "Click to lift quiet hours (Testing Mode)" : "Click to enforce quiet hours (Production Mode)"}
                      >
                        <span
                          className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow-sm ring-0 transition duration-200 ease-in-out ${
                            isQuietHoursActive ? "translate-x-5" : "translate-x-0"
                          }`}
                        />
                      </button>
                    </div>
                  </div>


                  <div className="flex items-center justify-between p-4 rounded-xl bg-gray-50 border border-gray-200">
                    <div>
                      <h4 className="font-bold text-gray-900">Meta Webhook Ingress URL</h4>
                      <p className="text-xs text-gray-500 mt-0.5">The endpoint entered in Meta Business Manager for real-time delivery receipts & STOP replies</p>
                    </div>
                    <span className="font-mono text-xs text-gray-600 bg-white px-3 py-1.5 rounded-lg border border-gray-200">
                      /api/webhooks/whatsapp
                    </span>
                  </div>

                  <div className="p-4 rounded-xl bg-gray-50 border border-gray-200 space-y-2">
                    <h4 className="font-bold text-gray-900">Multilingual DND Keywords Active</h4>
                    <p className="text-xs text-gray-500">Inbound replies containing any of these keywords immediately halt all future messages:</p>
                    <div className="flex flex-wrap gap-2 pt-1">
                      {["STOP", "UNSUBSCRIBE", "DND", "બંધ કરો", "સંદેશા બંધ કરો", "રોકો", "बंद करो"].map((k) => (
                        <span key={k} className="px-2.5 py-1 rounded-md text-xs font-mono font-semibold bg-red-50 text-red-700 border border-red-200">
                          {k}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              </div>

              {/* Team & User Accounts Card */}
              <div className="bg-white rounded-xl border border-gray-200 shadow-xs p-6">
                <div className="flex items-center justify-between border-b border-gray-100 pb-4 mb-5">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-amber-50 flex items-center justify-center text-[#F5A623]">
                      <Users className="w-5 h-5" />
                    </div>
                    <div>
                      <h3 className="font-bold text-gray-900 text-base">Authorized Team Accounts</h3>
                      <p className="text-xs text-gray-500">Registered users who have access to this WhatsApp CRM</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <button
                      type="button"
                      onClick={() => setIsRoleInfoModalOpen(true)}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-gray-100 hover:bg-gray-200 text-gray-700 transition cursor-pointer border border-gray-300"
                    >
                      <BookOpen className="w-3.5 h-3.5 text-gray-500" />
                      Role Permissions Guide
                    </button>
                    <span className={`px-2.5 py-1 rounded-full text-xs font-mono font-bold ${
                      systemUsers.length >= 5 ? "bg-red-50 text-red-700 border border-red-200" : "bg-emerald-50 text-emerald-700 border border-emerald-200"
                    }`}>
                      {systemUsers.length} / 5 Users Registered
                    </span>
                    {systemUsers.length < 5 && (
                      <button
                        type="button"
                        onClick={() => {
                          setAddUserError("");
                          setIsAddUserModalOpen(true);
                        }}
                        className="flex items-center gap-1.5 bg-[#25D366] hover:bg-[#1EBE5D] text-white px-3.5 py-1.5 rounded-lg text-xs font-bold transition shadow-xs"
                      >
                        <UserPlus className="w-3.5 h-3.5" />
                        + Add User
                      </button>
                    )}
                  </div>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full min-w-[920px] table-fixed text-left text-sm text-gray-600">
                    <thead className="bg-gray-50 text-xs uppercase font-semibold text-gray-500 border-b border-gray-200">
                      <tr>
                        <th className="w-16 px-4 py-3">ID</th>
                        <th className="w-48 px-4 py-3">Username</th>
                        <th className="w-56 px-4 py-3">Email Address</th>
                        <th className="w-40 px-4 py-3">2FA Security</th>
                        <th className="w-24 px-4 py-3">Status</th>
                        <th className="w-48 px-4 py-3">
                          <div className="flex items-center gap-1">
                            <span>Access Level</span>
                            <button
                              type="button"
                              onClick={() => setIsRoleInfoModalOpen(true)}
                              className="text-gray-400 hover:text-gray-600 transition"
                              title="Click to view role access permissions"
                            >
                              <BookOpen className="w-3 h-3" />
                            </button>
                          </div>
                        </th>
                        <th className="w-72 px-4 py-3 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {(() => {
                        const isCallerAdmin = currentUserProfile?.role === "admin" || (username && username.toLowerCase().includes("admin"));
                        return systemUsers.map((u) => (
                          <tr key={u.id} className="hover:bg-gray-50/80 transition">
                            <td className="w-16 px-4 py-3.5 font-mono text-xs text-gray-400 whitespace-nowrap">#{u.id}</td>
                            <td className="w-48 px-4 py-3.5 font-bold text-gray-900 whitespace-nowrap">
                              <div className="flex items-center gap-2">
                                <span className="w-2 h-2 rounded-full bg-[#25D366] shrink-0"></span>
                                <span className="truncate">{u.username}</span>
                                {u.username === username && (
                                  <span className="text-[10px] bg-gray-100 text-gray-600 px-1.5 py-0.2 rounded font-mono font-normal shrink-0">You</span>
                                )}
                              </div>
                            </td>
                            <td className="w-56 px-4 py-3.5 text-xs text-gray-600 font-mono truncate" title={u.email}>{u.email}</td>
                            <td className="w-40 px-4 py-3.5 whitespace-nowrap">
                              {u.is_2fa_enabled ? (
                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-[#10B981] border border-emerald-200">
                                  <ShieldCheck className="w-3 h-3" /> Enabled (TOTP)
                                </span>
                              ) : (
                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-gray-100 text-gray-500 border border-gray-200">
                                  Disabled
                                </span>
                              )}
                            </td>
                            <td className="w-24 px-4 py-3.5 whitespace-nowrap">
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-[#10B981] border border-emerald-200">
                                Active
                              </span>
                            </td>
                            <td className="w-48 px-4 py-3.5 font-semibold text-xs text-gray-700 whitespace-nowrap">
                              {u.role === "admin" ? (
                                <span className="bg-amber-100 text-amber-900 px-2.5 py-1 rounded-md font-bold inline-flex items-center gap-1 border border-amber-300">
                                  <ShieldCheck className="w-3 h-3 text-amber-700" /> Admin (Full Access)
                                </span>
                              ) : u.role === "service" ? (
                                <span className="bg-purple-50 text-purple-800 px-2.5 py-1 rounded-md font-semibold inline-flex items-center gap-1 border border-purple-200">
                                  Service Account
                                </span>
                              ) : (
                                <span className="bg-blue-50 text-blue-800 px-2.5 py-1 rounded-md font-medium inline-flex items-center gap-1 border border-blue-200">
                                  Team Member
                                </span>
                              )}
                            </td>
                            <td className="w-72 px-4 py-3.5 text-right whitespace-nowrap">
                              <div className="flex items-center justify-end gap-1.5 flex-wrap">
                                {/* 1. Admin Role Management: Promote / Demote */}
                                {isCallerAdmin && (
                                  <>
                                    {u.role === "admin" ? (
                                      <button
                                        type="button"
                                        disabled={userRoleUpdatingId === u.id || (u.id === 1 && u.username === username && systemUsers.filter((x) => x.role === "admin").length <= 1)}
                                        onClick={() => handleUpdateUserRole(u, "agent")}
                                        className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-1 rounded bg-amber-50 text-amber-800 hover:bg-amber-100 border border-amber-200 transition disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
                                        title="Demote to Team Member"
                                      >
                                        {userRoleUpdatingId === u.id ? (
                                          <RefreshCw className="w-3 h-3 animate-spin" />
                                        ) : (
                                          <ShieldAlert className="w-3 h-3 text-amber-600" />
                                        )}
                                        Demote
                                      </button>
                                    ) : (
                                      <button
                                        type="button"
                                        disabled={userRoleUpdatingId === u.id}
                                        onClick={() => handleUpdateUserRole(u, "admin")}
                                        className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-1 rounded bg-emerald-50 text-emerald-800 hover:bg-emerald-100 border border-emerald-200 transition disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
                                        title="Promote to Admin"
                                      >
                                        {userRoleUpdatingId === u.id ? (
                                          <RefreshCw className="w-3 h-3 animate-spin" />
                                        ) : (
                                          <ShieldCheck className="w-3 h-3 text-emerald-600" />
                                        )}
                                        Make Admin
                                      </button>
                                    )}

                                    {/* 2. Admin Password Override Button */}
                                    <button
                                      type="button"
                                      onClick={() => {
                                        setAdminPasswordModal({
                                          isOpen: true,
                                          user: u,
                                          newPassword: "",
                                          confirmPassword: "",
                                          loading: false,
                                          error: ""
                                        });
                                      }}
                                      className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-1 rounded bg-indigo-50 text-indigo-700 hover:bg-indigo-100 border border-indigo-200 transition cursor-pointer"
                                      title={`Reset Password for ${u.username}`}
                                    >
                                      <Key className="w-3 h-3 text-indigo-600" />
                                      Reset Pass
                                    </button>

                                    {/* 3. Admin 2FA Override */}
                                    {u.username !== username && (
                                      u.is_2fa_enabled ? (
                                        <button
                                          type="button"
                                          disabled={admin2faUpdatingId === u.id}
                                          onClick={() => handleAdminToggle2FA(u, false)}
                                          className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-1 rounded bg-rose-50 text-rose-700 hover:bg-rose-100 border border-rose-200 transition disabled:opacity-40 cursor-pointer"
                                          title={`Turn OFF 2FA requirement for ${u.username}`}
                                        >
                                          {admin2faUpdatingId === u.id ? (
                                            <RefreshCw className="w-3 h-3 animate-spin" />
                                          ) : (
                                            <ShieldAlert className="w-3 h-3 text-rose-600" />
                                          )}
                                          2FA Off
                                        </button>
                                      ) : (
                                        <button
                                          type="button"
                                          disabled={admin2faUpdatingId === u.id}
                                          onClick={() => handleAdminToggle2FA(u, true)}
                                          className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-1 rounded bg-gray-50 text-gray-700 hover:bg-gray-100 border border-gray-200 transition disabled:opacity-40 cursor-pointer"
                                          title={`Turn ON 2FA requirement for ${u.username}`}
                                        >
                                          {admin2faUpdatingId === u.id ? (
                                            <RefreshCw className="w-3 h-3 animate-spin" />
                                          ) : (
                                            <ShieldCheck className="w-3 h-3 text-gray-600" />
                                          )}
                                          2FA On
                                        </button>
                                      )
                                    )}

                                    {/* 4. Delete User Button (Admins cannot delete other Admins or Self) */}
                                    {u.role !== "admin" && u.username !== username ? (
                                      <button
                                        type="button"
                                        disabled={userDeletingId === u.id}
                                        onClick={() => handleDeleteUser(u)}
                                        className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-1 rounded bg-red-50 text-red-700 hover:bg-red-100 border border-red-200 transition disabled:opacity-40 cursor-pointer"
                                        title={`Delete user account ${u.username}`}
                                      >
                                        {userDeletingId === u.id ? (
                                          <RefreshCw className="w-3 h-3 animate-spin" />
                                        ) : (
                                          <Trash2 className="w-3 h-3 text-red-600" />
                                        )}
                                        Delete
                                      </button>
                                    ) : u.role === "admin" && u.username !== username ? (
                                      <span
                                        className="text-[10px] text-gray-400 italic px-1 cursor-help"
                                        title="Security rule: Admins cannot delete other Admins. Demote them first."
                                      >
                                        Admin Lock
                                      </span>
                                    ) : null}
                                  </>
                                )}

                                {/* Self 2FA Toggle for logged-in user */}
                                {u.username === username && (
                                  u.is_2fa_enabled ? (
                                    <button
                                      type="button"
                                      onClick={handleOpen2faDisable}
                                      className="text-xs text-red-600 hover:text-red-800 font-semibold hover:underline cursor-pointer ml-1"
                                    >
                                      Disable My 2FA
                                    </button>
                                  ) : (
                                    <button
                                      type="button"
                                      onClick={handleOpen2faSetup}
                                      className="text-xs bg-[#25D366] hover:bg-[#1EBE5D] text-white px-2.5 py-1 rounded-md font-bold transition inline-flex items-center gap-1 shadow-xs cursor-pointer ml-1"
                                    >
                                      <ShieldCheck className="w-3 h-3" />
                                      Enable 2FA
                                    </button>
                                  )
                                )}
                              </div>
                            </td>
                          </tr>
                        ));
                      })()}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Permanent API Access Tokens & Webhook Integration Card */}
              <div className="bg-white rounded-xl border border-gray-200 shadow-xs p-6">
                <div className="flex items-center justify-between border-b border-gray-100 pb-4 mb-5">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-amber-50 flex items-center justify-center text-amber-600 border border-amber-200 shadow-xs">
                      <Key className="w-5 h-5" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="font-bold text-gray-900 text-base">Storefront & E-Commerce Webhooks</h3>
                        <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                          HMAC-SHA256 Authenticated
                        </span>
                      </div>
                      <p className="text-xs text-gray-500">
                        Secure, signature-verified webhook endpoints for your Shopify store. Permanent API tokens have been retired in favor of cryptographic request signing.
                      </p>
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                  {/* Left Column: Webhook Security Status */}
                  <div className="p-4 rounded-xl bg-gray-50 border border-gray-200 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold uppercase text-gray-700">Webhook Authentication Policy</span>
                      <span className="inline-flex items-center gap-1 text-[11px] font-bold text-emerald-700 bg-emerald-100/60 px-2 py-0.5 rounded-full border border-emerald-200">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                        HMAC Signature Enforced
                      </span>
                    </div>

                    <div className="space-y-2 text-xs text-gray-600">
                      <p>
                        Incoming cart and store events must be signed with your configured shared HMAC secret. Requests without a valid cryptographic signature or with timestamp drift &gt; 5 minutes are rejected.
                      </p>
                      <div className="p-3 bg-white rounded-lg border border-gray-200 font-mono text-[11px] text-gray-700 space-y-1">
                        <div><span className="text-indigo-600 font-semibold">Signature Header:</span> X-WC-Webhook-Signature</div>
                        <div><span className="text-gray-500 font-semibold">Algorithm:</span> HMAC-SHA256 (Base64 raw payload)</div>
                      </div>
                    </div>
                  </div>

                  {/* Right Column: Webhook Ingress Details */}
                  <div className="p-4 rounded-xl bg-gray-50 border border-gray-200 space-y-3">
                    <div className="flex items-center gap-1.5 text-xs font-bold text-gray-800">
                      <Code className="w-3.5 h-3.5 text-indigo-600" />
                      <span>Ingress Webhook Endpoints</span>
                    </div>

                    <div className="space-y-2 text-xs">
                      <div>
                        <label className="text-[10px] font-bold uppercase text-gray-500 block mb-1">Abandoned Cart Event URL</label>
                        <div className="flex items-center gap-2">
                          <input
                            type="text"
                            readOnly
                            value={webhookUrl}
                            className="w-full font-mono text-xs px-3 py-1.5 bg-white border border-gray-300 rounded-lg text-gray-800 focus:outline-none select-all shadow-2xs"
                          />
                          <button
                            type="button"
                            onClick={() => handleCopyWebhookUrl(webhookUrl)}
                            className={`px-2.5 py-1.5 border rounded-lg text-xs font-semibold shrink-0 cursor-pointer transition ${
                              webhookCopied
                                ? "bg-emerald-600 text-white border-emerald-600"
                                : "bg-white hover:bg-gray-100 text-gray-700 border-gray-300"
                            }`}
                            title="Copy Webhook URL"
                          >
                            {webhookCopied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                          </button>
                        </div>
                      </div>

                      <div>
                        <label className="text-[10px] font-bold uppercase text-gray-500 block mb-1">General Store Event URL</label>
                        <div className="flex items-center gap-2">
                          <input
                            type="text"
                            readOnly
                            value={`${apiBaseUrl}/api/webhooks/store-event`}
                            className="w-full font-mono text-xs px-3 py-1.5 bg-white border border-gray-300 rounded-lg text-gray-800 focus:outline-none select-all shadow-2xs"
                          />
                          <button
                            type="button"
                            onClick={() => handleCopyWebhookUrl(`${apiBaseUrl}/api/webhooks/store-event`)}
                            className="px-2.5 py-1.5 bg-white hover:bg-gray-100 text-gray-700 border border-gray-300 rounded-lg text-xs font-semibold shrink-0 cursor-pointer"
                            title="Copy Store Event URL"
                          >
                            <Copy className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
  );
}
