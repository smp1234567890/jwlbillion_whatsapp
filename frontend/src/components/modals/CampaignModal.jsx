import React from "react";
import { Send, Calendar, Clock } from "lucide-react";
import { formatScheduleDisplay } from "../../utils/dateUtils";

export default function CampaignModal({
  isOpen,
  onClose,
  newCampaign,
  setNewCampaign,
  templates = [],
  contacts = [],
  onSubmit
}) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-gray-200">
        <div className="flex items-center justify-between pb-4 border-b border-gray-100">
          <h3 className="font-bold text-lg text-gray-900">Create New WhatsApp Broadcast</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 font-bold text-xl">✕</button>
        </div>

        <form onSubmit={onSubmit} className="mt-5 space-y-4">
          <div>
            <label className="block text-xs font-bold uppercase text-gray-700 mb-1">Campaign Title</label>
            <input
              type="text"
              required
              placeholder="e.g. Navratri Special Fafda-Jalebi Offer"
              value={newCampaign.title}
              onChange={(e) => setNewCampaign({ ...newCampaign, title: e.target.value })}
              className="w-full px-3.5 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#25D366]"
            />
          </div>

          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="block text-xs font-bold uppercase text-gray-700">WhatsApp Approved Template</label>
              {templates.length > 0 && (
                <span className="text-[11px] font-semibold text-emerald-600">
                  {templates.filter((t) => t.status === "APPROVED").length} Approved by Meta
                </span>
              )}
            </div>
            <select
              value={newCampaign.template_name}
              onChange={(e) => {
                const sel = templates.find((t) => t.template_name === e.target.value);
                setNewCampaign({
                  ...newCampaign,
                  template_name: e.target.value,
                  language: sel?.language || newCampaign.language || "en"
                });
              }}
              className="w-full px-3.5 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#25D366]"
            >
              {templates.length > 0 ? (
                [...templates]
                  .sort((a, b) => (a.status === "APPROVED" ? -1 : 1))
                  .map((t) => {
                    const isApproved = t.status === "APPROVED";
                    return (
                      <option key={t.id} value={t.template_name}>
                        {isApproved ? "🟢 [APPROVED]" : "🟡 [PENDING]"} {t.template_name} ({t.language})
                      </option>
                    );
                  })
              ) : (
                <option value="" disabled>No templates synced from Meta</option>
              )}
            </select>

            {(() => {
              const currentTmpl = templates.find((t) => t.template_name === newCampaign.template_name);
              if (!currentTmpl) return null;
              const isApproved = currentTmpl.status === "APPROVED";
              return (
                <div className={`mt-2 p-2.5 rounded-lg text-xs flex items-center justify-between border ${
                  isApproved 
                    ? "bg-emerald-50 text-emerald-800 border-emerald-200" 
                    : "bg-amber-50 text-amber-800 border-amber-200"
                }`}>
                  <div className="flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full ${isApproved ? "bg-emerald-500" : "bg-amber-500 animate-pulse"}`}></span>
                    <span className="font-semibold">
                      {isApproved ? "Approved by Meta • Ready for broadcast" : "Pending Meta Review • WhatsApp may reject broadcast"}
                    </span>
                  </div>
                  <span className="font-mono text-[11px] bg-white px-2 py-0.5 rounded border border-gray-200 font-bold text-gray-700">
                    {currentTmpl.language}
                  </span>
                </div>
              );
            })()}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-bold uppercase text-gray-700 mb-1">Language Code</label>
              <input
                type="text"
                readOnly
                value={newCampaign.language}
                className="w-full px-3.5 py-2.5 bg-gray-50 border border-gray-300 rounded-lg text-sm text-gray-800 font-mono font-semibold focus:outline-none cursor-not-allowed"
                title="Matched automatically from the selected Meta template."
              />
              <p className="text-[10px] text-gray-400 mt-0.5">Matched from Meta template</p>
            </div>

            <div>
              <label className="block text-xs font-bold uppercase text-gray-700 mb-1">Audience Segment</label>
              <select
                value={newCampaign.target_filter}
                onChange={(e) => setNewCampaign({ ...newCampaign, target_filter: e.target.value })}
                className="w-full px-3.5 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#25D366]"
              >
                <option value="ALL">All Active Contacts ({contacts.length})</option>
                <option value="INACTIVE_30_DAYS">30-Day Inactive Only</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-bold uppercase text-gray-700 mb-1 flex items-center justify-between">
                <span>Per-Day Message Limit</span>
                <span className="text-[10px] text-emerald-600 font-semibold lowercase">optional</span>
              </label>
              <input
                type="number"
                min="1"
                placeholder="e.g. 500, 1000"
                value={newCampaign.per_day_limit || ""}
                onChange={(e) => setNewCampaign({ ...newCampaign, per_day_limit: e.target.value })}
                className="w-full px-3.5 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#25D366]"
              />
              <p className="text-[10px] text-gray-400 mt-0.5">
                {newCampaign.per_day_limit 
                  ? `Sends only first ${newCampaign.per_day_limit} contacts` 
                  : "Leave empty to send all contacts"}
              </p>
            </div>

            <div>
              <label className="block text-xs font-bold uppercase text-gray-700 mb-1 flex items-center justify-between">
                <span className="flex items-center gap-1.5">
                  <Calendar className="w-3.5 h-3.5 text-gray-500" />
                  Schedule for Later
                </span>
                <span className="text-[10px] font-bold text-amber-800 bg-amber-100/90 px-1.5 py-0.5 rounded border border-amber-200">
                  IST (GMT+5:30)
                </span>
              </label>
              <input
                type="datetime-local"
                value={newCampaign.scheduled_for || ""}
                onChange={(e) => setNewCampaign({ ...newCampaign, scheduled_for: e.target.value })}
                className="w-full px-3.5 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#25D366]"
              />
              {newCampaign.scheduled_for ? (
                <div className="mt-1.5 p-2 bg-amber-50 border border-amber-200 rounded-lg flex items-center gap-2 text-xs text-amber-900 font-medium">
                  <Clock className="w-4 h-4 text-amber-600 flex-shrink-0" />
                  <span>
                    Trigger: <strong>{formatScheduleDisplay(newCampaign.scheduled_for)?.formattedDate || newCampaign.scheduled_for}</strong>
                  </span>
                </div>
              ) : (
                <p className="text-[10px] text-gray-400 mt-0.5">Indian Standard Time (IST). Leave empty to send immediately.</p>
              )}
            </div>
          </div>

          <div className="pt-4 border-t border-gray-100 flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-gray-300 rounded-lg text-sm font-semibold text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="flex items-center gap-2 bg-[#25D366] hover:bg-[#1EBE5D] text-white px-5 py-2 rounded-lg font-semibold text-sm shadow-md"
            >
              <Send className="w-4 h-4" />
              {newCampaign.scheduled_for ? "Schedule Broadcast" : "Trigger Broadcast"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
