import React, { useState } from "react";
import {
  UserPlus,
  RefreshCw,
  Key,
  Eye,
  EyeOff,
  ShieldCheck,
  Users,
  Zap,
  Copy,
  Check,
  AlertTriangle,
  Code,
  Trash2,
  ExternalLink
} from "lucide-react";
import axios, { getApiBaseUrl } from "../../api";
import { formatToIST } from "../../utils/dateUtils";

export function AddUserModal({
  isOpen,
  onClose,
  systemUsers = [],
  newUserForm,
  setNewUserForm,
  addUserLoading,
  addUserError,
  onSubmit
}) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-gray-200">
        <div className="flex items-center justify-between pb-4 border-b border-gray-100">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-emerald-50 text-[#25D366] flex items-center justify-center">
              <UserPlus className="w-4 h-4" />
            </div>
            <div>
              <h3 className="font-bold text-base text-gray-900">Add Team Account</h3>
              <p className="text-[11px] text-gray-400">Grant authorized CRM access ({systemUsers.length}/5 used)</p>
            </div>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 font-bold text-xl leading-none">✕</button>
        </div>

        {addUserError && (
          <div className="mt-4 p-3 rounded-lg bg-red-50 border border-red-200 text-red-600 text-xs font-semibold">
            {addUserError}
          </div>
        )}

        <form onSubmit={onSubmit} className="mt-4 space-y-4">
          <div>
            <label className="block text-xs font-bold uppercase text-gray-700 mb-1">Username</label>
            <input
              type="text"
              required
              placeholder="e.g. rahul_manager"
              value={newUserForm.username}
              onChange={(e) => setNewUserForm({ ...newUserForm, username: e.target.value })}
              className="w-full px-3.5 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#25D366]"
            />
          </div>

          <div>
            <label className="block text-xs font-bold uppercase text-gray-700 mb-1">Email Address</label>
            <input
              type="email"
              required
              placeholder="rahul@jwl-billion.com"
              value={newUserForm.email}
              onChange={(e) => setNewUserForm({ ...newUserForm, email: e.target.value })}
              className="w-full px-3.5 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#25D366]"
            />
          </div>

          <div>
            <label className="block text-xs font-bold uppercase text-gray-700 mb-1">Password</label>
            <input
              type="password"
              required
              minLength={6}
              placeholder="At least 6 characters"
              value={newUserForm.password}
              onChange={(e) => setNewUserForm({ ...newUserForm, password: e.target.value })}
              className="w-full px-3.5 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#25D366]"
            />
          </div>

          <div>
            <label className="block text-xs font-bold uppercase text-gray-700 mb-1">Access Level (Role)</label>
            <select
              value={newUserForm.role || "agent"}
              onChange={(e) => setNewUserForm({ ...newUserForm, role: e.target.value })}
              className="w-full px-3.5 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#25D366] bg-white cursor-pointer"
            >
              <option value="agent">Team Member (Standard Access)</option>
              <option value="admin">Admin (Full Access & User Management)</option>
            </select>
          </div>

          <div className="pt-2 flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-gray-300 rounded-lg text-xs font-bold text-gray-700 hover:bg-gray-50 transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={addUserLoading}
              className="flex items-center gap-1.5 bg-[#25D366] hover:bg-[#1EBE5D] text-white px-5 py-2 rounded-lg font-bold text-xs shadow-xs transition disabled:opacity-50"
            >
              {addUserLoading ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <UserPlus className="w-3.5 h-3.5" />}
              {addUserLoading ? "Creating..." : "Create Team Member"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export function AdminPasswordModal({
  modalState,
  setModalState,
  onSubmit
}) {
  if (!modalState.isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-2xl max-w-sm w-full p-6 shadow-2xl border border-gray-200">
        <div className="flex items-center justify-between pb-3 border-b border-gray-100">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-indigo-100 text-indigo-700 flex items-center justify-center">
              <Key className="w-4 h-4" />
            </div>
            <div>
              <h3 className="font-bold text-base text-gray-900">Reset User Password</h3>
              <p className="text-xs text-gray-500">Admin credential override</p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setModalState({ isOpen: false, user: null, newPassword: "", confirmPassword: "", loading: false, error: "" })}
            className="text-gray-400 hover:text-gray-600 font-bold text-xl cursor-pointer"
          >
            ✕
          </button>
        </div>

        <p className="text-xs text-gray-600 mt-3 mb-4 bg-indigo-50 border border-indigo-100 p-2.5 rounded-lg">
          Set a new secure password for account: <strong className="text-indigo-900 font-mono">{modalState.user?.username}</strong>.
        </p>

        {modalState.error && (
          <div className="mb-3 p-2.5 bg-red-50 border border-red-200 text-red-700 text-xs rounded-lg font-medium">
            {modalState.error}
          </div>
        )}

        <form onSubmit={onSubmit} className="space-y-3">
          <div>
            <label className="block text-xs font-bold uppercase text-gray-700 mb-1">New Password</label>
            <div className="relative">
              <input
                type={modalState.showPassword ? "text" : "password"}
                required
                minLength={6}
                placeholder="Minimum 6 characters"
                value={modalState.newPassword}
                onChange={(e) => setModalState((prev) => ({ ...prev, newPassword: e.target.value }))}
                className="w-full pl-3 pr-8 py-2 border border-gray-300 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
              <button
                type="button"
                onClick={() => setModalState((prev) => ({ ...prev, showPassword: !prev.showPassword }))}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 focus:outline-none cursor-pointer"
              >
                {modalState.showPassword ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
              </button>
            </div>
          </div>

          <div>
            <label className="block text-xs font-bold uppercase text-gray-700 mb-1">Confirm New Password</label>
            <div className="relative">
              <input
                type={modalState.showPassword ? "text" : "password"}
                required
                minLength={6}
                placeholder="Repeat new password"
                value={modalState.confirmPassword}
                onChange={(e) => setModalState((prev) => ({ ...prev, confirmPassword: e.target.value }))}
                className="w-full pl-3 pr-8 py-2 border border-gray-300 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
          </div>

          <div className="flex gap-2 pt-2">
            <button
              type="button"
              onClick={() => setModalState({ isOpen: false, user: null, newPassword: "", confirmPassword: "", loading: false, error: "" })}
              className="flex-1 py-2 border border-gray-300 rounded-lg text-xs font-semibold text-gray-700 hover:bg-gray-50 cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={modalState.loading}
              className="flex-1 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-bold shadow-xs transition flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-50"
            >
              {modalState.loading ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Key className="w-3.5 h-3.5" />}
              Save Password
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export function RoleInfoModal({ isOpen, onClose }) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-2xl max-w-xl w-full p-6 shadow-2xl border border-gray-200">
        <div className="flex items-center justify-between pb-4 border-b border-gray-100">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-amber-50 text-[#F5A623] flex items-center justify-center font-bold">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-bold text-base text-gray-900">System Role & Access Privileges</h3>
              <p className="text-xs text-gray-500">Overview of what each account type is permitted to do</p>
            </div>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 font-bold text-xl cursor-pointer">✕</button>
        </div>

        <div className="mt-4 space-y-3.5 text-sm">
          {/* Admin Card */}
          <div className="p-3.5 rounded-xl border border-amber-200 bg-amber-50/50">
            <div className="flex items-center justify-between mb-1.5">
              <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs font-bold bg-amber-100 text-amber-900 border border-amber-300">
                <ShieldCheck className="w-3.5 h-3.5 text-amber-700" />
                Admin (Full System & Security Control)
              </span>
              <span className="text-[10px] font-bold text-amber-800 bg-amber-200/60 px-2 py-0.5 rounded">Highest Clearance</span>
            </div>
            <ul className="text-xs text-amber-950 space-y-1 list-disc pl-4 mt-2">
              <li>Can create, edit, approve, and send all WhatsApp campaigns.</li>
              <li>Can build and activate multi-step automation journeys & visual flows.</li>
              <li>Can register team accounts, promote/demote members, and delete non-admin users.</li>
              <li>Can reset passwords and enable/disable 2FA for locked-out accounts.</li>
              <li>Full financial access (Meta budget thresholds, spend guardrails, webhook secrets).</li>
            </ul>
          </div>

          {/* Team Member Card */}
          <div className="p-3.5 rounded-xl border border-blue-200 bg-blue-50/50">
            <div className="flex items-center justify-between mb-1.5">
              <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs font-bold bg-blue-100 text-blue-900 border border-blue-300">
                <Users className="w-3.5 h-3.5 text-blue-700" />
                Team Member (Customer Operations)
              </span>
              <span className="text-[10px] font-bold text-blue-800 bg-blue-200/60 px-2 py-0.5 rounded">Operational Access</span>
            </div>
            <ul className="text-xs text-blue-950 space-y-1 list-disc pl-4 mt-2">
              <li>2-way live chat with customers in the WhatsApp Live Inbox.</li>
              <li>View customer directory, order history, tags, and conversation transcripts.</li>
              <li>Inspect approved WhatsApp templates and verify campaign delivery logs.</li>
              <li>Manage their own account 2FA security.</li>
            </ul>
          </div>

          {/* Service Account Card */}
          <div className="p-3.5 rounded-xl border border-purple-200 bg-purple-50/50">
            <div className="flex items-center justify-between mb-1.5">
              <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs font-bold bg-purple-100 text-purple-900 border border-purple-300">
                <Zap className="w-3.5 h-3.5 text-purple-700" />
                Service Account (Automated API System)
              </span>
              <span className="text-[10px] font-bold text-purple-800 bg-purple-200/60 px-2 py-0.5 rounded">Machine & Webhooks</span>
            </div>
            <ul className="text-xs text-purple-950 space-y-1 list-disc pl-4 mt-2">
              <li>Machine-to-machine account for e-commerce website webhooks.</li>
              <li>Automated synchronization for abandoned carts, placed orders, and contact sync.</li>
            </ul>
          </div>
        </div>

        <div className="pt-4 mt-4 border-t border-gray-100 flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 bg-gray-900 hover:bg-black text-white text-xs font-bold rounded-lg transition cursor-pointer"
          >
            Got it
          </button>
        </div>
      </div>
    </div>
  );
}
