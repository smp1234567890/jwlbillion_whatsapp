import React, { useState, useEffect } from "react";
import axios from "axios";
import { Trash2, UserX, Plus, AlertOctagon, RefreshCw, PhoneOff, ShieldAlert } from "lucide-react";
import { formatToIST } from "../utils/dateUtils";

export default function OptOutPage({ optOuts = [], handleRemoveOptOut, handleAddOptOut }) {
  const [activeSubTab, setActiveSubTab] = useState("dnd"); // "dnd" | "permanently_failed"
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [phone, setPhone] = useState("");
  const [reason, setReason] = useState("Manual Request");
  const [loading, setLoading] = useState(false);

  // Permanently failed numbers state
  const [permFailed, setPermFailed] = useState([]);
  const [permLoading, setPermLoading] = useState(false);
  const [permError, setPermError] = useState("");

  const fetchPermFailed = async () => {
    setPermLoading(true);
    setPermError("");
    try {
      const res = await axios.get("/api/permanently-failed");
      setPermFailed(res.data || []);
    } catch (err) {
      console.error("Failed to load permanently failed contacts:", err);
      setPermError(err.response?.data?.detail || err.message || "Failed to load list");
    } finally {
      setPermLoading(false);
    }
  };

  useEffect(() => {
    if (activeSubTab === "permanently_failed") {
      fetchPermFailed();
    }
  }, [activeSubTab]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!phone.trim()) return;
    setLoading(true);
    try {
      if (handleAddOptOut) {
        await handleAddOptOut(phone.trim(), reason.trim());
      }
      setPhone("");
      setReason("Manual Request");
      setIsModalOpen(false);
    } catch (err) {
      alert("Error adding opt-out: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Top Tab Bar: DND Registry vs Permanently Failed */}
      <div className="flex items-center gap-2 border-b border-gray-200 pb-2">
        <button
          onClick={() => setActiveSubTab("dnd")}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold transition cursor-pointer ${
            activeSubTab === "dnd"
              ? "bg-red-50 text-red-700 border border-red-200 shadow-xs"
              : "text-gray-600 hover:bg-gray-100"
          }`}
        >
          <UserX className="w-4 h-4 text-red-600" />
          <span>Opt-Out (DND) Registry</span>
          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-red-100 text-red-800">
            {optOuts.length}
          </span>
        </button>

        <button
          onClick={() => setActiveSubTab("permanently_failed")}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold transition cursor-pointer ${
            activeSubTab === "permanently_failed"
              ? "bg-amber-50 text-amber-800 border border-amber-200 shadow-xs"
              : "text-gray-600 hover:bg-gray-100"
          }`}
        >
          <AlertOctagon className="w-4 h-4 text-amber-600" />
          <span>Permanently Failed</span>
          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-900">
            {permFailed.length > 0 ? permFailed.length : "54+"}
          </span>
        </button>
      </div>

      {/* TAB 1: DND Registry */}
      {activeSubTab === "dnd" && (
        <div className="bg-white rounded-xl border border-gray-200 shadow-xs overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
            <div>
              <h3 className="font-bold text-gray-900 text-base">Opt-Out & Do Not Disturb (DND) Registry</h3>
              <p className="text-xs text-gray-500 mt-0.5">
                Customers who texted STOP / બંધ કરો / रोકો. Never messaged automatically.
              </p>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={() => setIsModalOpen(true)}
                className="flex items-center gap-1.5 bg-red-600 hover:bg-red-700 text-white px-3.5 py-1.5 rounded-lg font-bold text-xs shadow-xs transition cursor-pointer"
                title="Manually add phone number to DND list"
              >
                <UserX className="w-3.5 h-3.5" />
                <span>Add to DND</span>
              </button>
              <span className="px-3 py-1 text-xs font-bold rounded-full bg-red-50 text-red-600 border border-red-200">
                {optOuts.length} Numbers Blocked
              </span>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-gray-600">
              <thead className="bg-gray-50 text-xs uppercase font-semibold text-gray-500 border-b border-gray-200">
                <tr>
                  <th className="px-6 py-3">Phone Number</th>
                  <th className="px-6 py-3">Reason / Text Trigger</th>
                  <th className="px-6 py-3">Unsubscribed At</th>
                  <th className="px-6 py-3">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {optOuts.length === 0 ? (
                  <tr>
                    <td colSpan="4" className="text-center py-8 text-gray-400 text-xs">
                      No phone numbers currently on the DND registry.
                    </td>
                  </tr>
                ) : (
                  optOuts.map((opt) => (
                    <tr key={opt.id} className="hover:bg-gray-50/80 transition">
                      <td className="px-6 py-4 font-mono font-bold text-gray-900">{opt.phone}</td>
                      <td className="px-6 py-4 text-xs font-mono text-red-600 bg-red-50/50 rounded inline-block my-2 px-2 py-1">
                        {opt.reason}
                      </td>
                      <td className="px-6 py-4 text-xs font-mono text-gray-500">
                        {formatToIST(opt.created_at)}
                      </td>
                      <td className="px-6 py-4">
                        <button
                          onClick={() => handleRemoveOptOut(opt.phone)}
                          className="text-xs text-gray-400 hover:text-red-600 transition flex items-center gap-1 cursor-pointer"
                          title="Unblock customer"
                        >
                          <Trash2 className="w-3.5 h-3.5" /> Remove
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 2: Permanently Failed (Undeliverable / Non-WhatsApp) */}
      {activeSubTab === "permanently_failed" && (
        <div className="bg-white rounded-xl border border-gray-200 shadow-xs overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-bold text-gray-900 text-base">Permanently Failed Numbers</h3>
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-900 border border-amber-200">
                  Meta 131026
                </span>
              </div>
              <p className="text-xs text-gray-500 mt-0.5">
                These numbers do not have an active WhatsApp account or are unreachable. Sending to them is permanently blocked to safeguard your Meta quality score.
              </p>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={fetchPermFailed}
                disabled={permLoading}
                className="flex items-center gap-1.5 bg-gray-100 hover:bg-gray-200 text-gray-700 px-3 py-1.5 rounded-lg font-bold text-xs transition cursor-pointer"
                title="Refresh list"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${permLoading ? "animate-spin" : ""}`} />
                <span>Refresh</span>
              </button>
              <span className="px-3 py-1 text-xs font-bold rounded-full bg-amber-50 text-amber-800 border border-amber-200">
                {permFailed.length} Undeliverable
              </span>
            </div>
          </div>

          <div className="overflow-x-auto">
            {permError && (
              <div className="p-4 m-4 bg-red-50 border border-red-200 text-red-700 text-xs rounded-xl">
                {permError}
              </div>
            )}
            {permLoading ? (
              <div className="py-16 text-center text-gray-400 flex flex-col items-center justify-center gap-2">
                <RefreshCw className="w-6 h-6 animate-spin text-amber-600" />
                <span className="text-xs">Loading permanently failed numbers...</span>
              </div>
            ) : permFailed.length === 0 ? (
              <div className="text-center py-12 text-gray-400 text-xs">
                No permanently failed contacts recorded yet.
              </div>
            ) : (
              <table className="w-full text-left text-sm text-gray-600">
                <thead className="bg-gray-50 text-xs uppercase font-semibold text-gray-500 border-b border-gray-200">
                  <tr>
                    <th className="px-6 py-3">Phone Number</th>
                    <th className="px-6 py-3">Failure Reason</th>
                    <th className="px-6 py-3">Detected At</th>
                    <th className="px-6 py-3">Delivery Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {permFailed.map((item, idx) => (
                    <tr key={idx} className="hover:bg-amber-50/40 transition">
                      <td className="px-6 py-4 font-mono font-bold text-gray-900 flex items-center gap-2">
                        <PhoneOff className="w-4 h-4 text-amber-600 shrink-0" />
                        <span>{item.phone}</span>
                      </td>
                      <td className="px-6 py-4 text-xs font-medium text-gray-700">
                        <span className="bg-amber-50 text-amber-800 px-2 py-0.5 rounded border border-amber-200 text-[11px] font-semibold">
                          {item.reason}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-xs font-mono text-gray-500">
                        {item.failed_at ? formatToIST(item.failed_at) : "Recent"}
                      </td>
                      <td className="px-6 py-4">
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full font-bold text-[11px] bg-red-50 text-red-700 border border-red-200">
                          <ShieldAlert className="w-3 h-3 text-red-600" />
                          Do Not Resend
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

      {/* Manual Opt-Out Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl border border-gray-100">
            <h3 className="font-bold text-gray-900 text-base flex items-center gap-2">
              <UserX className="w-5 h-5 text-red-600" />
              Add Customer to Opt-Out / DND
            </h3>
            <p className="text-xs text-gray-500 mt-1">
              Adding this number will revoke marketing consent and block all automated promotional messages.
            </p>
            <form onSubmit={handleSubmit} className="mt-4 space-y-4">
              <div>
                <label className="block text-xs font-bold text-gray-700 mb-1">
                  Customer WhatsApp Phone Number *
                </label>
                <input
                  type="text"
                  required
                  placeholder="+919876543210"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500 font-mono"
                />
              </div>
              <div>
                <label className="block text-xs font-bold text-gray-700 mb-1">
                  Reason / Source
                </label>
                <input
                  type="text"
                  placeholder="e.g. Requested via call, Manual Opt-Out"
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500"
                />
              </div>
              <div className="flex items-center justify-end gap-2 pt-2 border-t border-gray-100">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-3.5 py-1.5 text-xs font-semibold text-gray-600 hover:bg-gray-100 rounded-lg transition cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={loading || !phone.trim()}
                  className="px-4 py-1.5 text-xs font-bold bg-red-600 hover:bg-red-700 text-white rounded-lg transition disabled:opacity-50 cursor-pointer"
                >
                  {loading ? "Adding..." : "Add to DND List"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
