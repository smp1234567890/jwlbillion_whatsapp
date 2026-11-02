import React from "react";
import {
  Send,
  ShoppingCart,
  Megaphone,
  CheckCircle2,
  Clock,
  Play,
  PlayCircle,
  MessageSquare,
  IndianRupee,
  Users,
  ShieldBan,
  Sliders
} from "lucide-react";
import { formatToIST, formatScheduleDisplay } from "../utils/dateUtils";

export default function DashboardPage({
  workflowFlows = [],
  messageLogs = [],
  cartEvents = [],
  campaigns = [],
  contacts = [],
  optOuts = [],
  handleTabChange,
  setEditingWorkflow,
  handleOpenNewJourneyModal
}) {
  // Total WhatsApp Attributed Revenue (recovered carts + attributed campaign customer orders)
  // Monthly cycle window: current month 1st 00:00:01 to 1st of next month 00:00:00
  const now = new Date();
  const cycleStart = new Date(now.getFullYear(), now.getMonth(), 1, 0, 0, 1);
  const cycleEnd = new Date(now.getFullYear(), now.getMonth() + 1, 1, 0, 0, 0);

  const cartRecoveredVal = cartEvents
    .filter((c) => {
      if (c.status !== "RECOVERED") return false;
      if (!c.created_at) return true;
      const eventTime = new Date(c.created_at);
      return eventTime >= cycleStart && eventTime <= cycleEnd;
    })
    .reduce((sum, c) => sum + (c.cart_value || 0), 0);

  // Delivered contacts with their earliest message sent timestamp in current cycle
  const deliveredPhoneMsgTime = new Map();
  (messageLogs || []).forEach((l) => {
    if (["DELIVERED", "READ", "SENT", "SENT_SIMULATED"].includes(l.status) && l.recipient_phone) {
      const logTime = l.created_at ? new Date(l.created_at) : cycleStart;
      if (!deliveredPhoneMsgTime.has(l.recipient_phone) || logTime < deliveredPhoneMsgTime.get(l.recipient_phone)) {
        deliveredPhoneMsgTime.set(l.recipient_phone, logTime);
      }
    }
  });

  // Only attribute orders strictly placed AFTER the WhatsApp broadcast delivery within the monthly cycle
  const attributedOrdersVal = (contacts || [])
    .filter((c) => {
      if (!c.phone || !deliveredPhoneMsgTime.has(c.phone) || !c.total_orders || c.total_orders <= 0) {
        return false;
      }
      if (!c.last_order_date) {
        return false;
      }
      const orderDate = new Date(c.last_order_date);
      const msgDeliveredTime = deliveredPhoneMsgTime.get(c.phone);
      // Strictly in current month cycle AND strictly after WhatsApp broadcast was dispatched/delivered
      return orderDate >= cycleStart && orderDate <= cycleEnd && orderDate >= msgDeliveredTime;
    })
    .reduce((sum, c) => {
      const orderPrice = Number(c.custom_attributes?.last_order?.total_price || c.custom_attributes?.shopify_total_spent || 0);
      return sum + orderPrice;
    }, 0);

  const totalEarnedRevenue = Math.max(cartRecoveredVal, attributedOrdersVal) + (cartRecoveredVal > 0 && attributedOrdersVal > 0 ? cartRecoveredVal : 0);

  // Total messages sent across all campaigns and direct automation dispatches
  const totalCampaignDispatched = (campaigns || []).reduce(
    (sum, c) => sum + (Number(c.successful_sends) || Number(c.delivered_count) || 0),
    0
  );
  const nonCampaignLogs = messageLogs.filter((l) => !l.campaign_id).length;
  const totalMessagesSent = Math.max(messageLogs.length, totalCampaignDispatched + nonCampaignLogs);

  return (

            <>
              {/* Top 4 KPI Metric Cards */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-5">
                <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-xs flex items-center justify-between">
                  <div>
                    <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Total Messages Sent</p>
                    <h3 className="text-2xl font-black text-gray-900 mt-1">{totalMessagesSent}</h3>
                    <span className="inline-flex items-center text-xs font-semibold text-gray-500 mt-1">
                      100% Meta Compliant
                    </span>
                  </div>
                  <div className="w-12 h-12 rounded-xl bg-gray-100 flex items-center justify-center text-gray-600">
                    <MessageSquare className="w-6 h-6" />
                  </div>
                </div>

                <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-xs flex items-center justify-between">
                  <div>
                    <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Revenue Earned</p>
                    <h3 className="text-2xl font-black text-gray-900 mt-1">₹ {totalEarnedRevenue.toFixed(2)}</h3>
                    <span className="text-xs font-semibold text-emerald-700 mt-1">
                      Attributed from WhatsApp
                    </span>
                  </div>
                  <div className="w-12 h-12 rounded-xl bg-gray-100 flex items-center justify-center text-gray-600">
                    <IndianRupee className="w-6 h-6" />
                  </div>
                </div>

                <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-xs flex items-center justify-between">
                  <div>
                    <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Active Customers</p>
                    <h3 className="text-2xl font-black text-gray-900 mt-1">{contacts.length}</h3>
                    <span className="text-xs text-gray-500 mt-1">Synced from Shopify store</span>
                  </div>
                  <div className="w-12 h-12 rounded-xl bg-gray-100 flex items-center justify-center text-gray-600">
                    <Users className="w-6 h-6" />
                  </div>
                </div>

                <div className="bg-white p-5 rounded-xl border border-gray-200 shadow-xs flex items-center justify-between">
                  <div>
                    <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Opt-Out (DND)</p>
                    <h3 className="text-2xl font-black text-gray-900 mt-1">{optOuts.length}</h3>
                    <span className="text-xs font-semibold text-gray-400 mt-1">Auto STOP Handler</span>
                  </div>
                  <div className="w-12 h-12 rounded-xl bg-gray-100 flex items-center justify-center text-gray-600">
                    <ShieldBan className="w-6 h-6" />
                  </div>
                </div>
              </div>

              {/* Active Journey Automations Quick Glance */}
              <div className="bg-white rounded-xl border border-gray-200 shadow-xs p-6">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h3 className="font-bold text-gray-900 text-base">Active Journey Automations</h3>
                    <p className="text-xs text-gray-500 mt-0.5">Multi-step flowchart workflows and triggers</p>
                  </div>
                  <button
                    onClick={() => handleTabChange("automations")}
                    className="text-xs font-bold text-[#25D366] hover:underline"
                  >
                    View All Journeys ({workflowFlows.length}) →
                  </button>
                </div>
                {workflowFlows.length > 0 ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                    {workflowFlows.map((flow) => (
                      <div key={flow.id} className="p-4 rounded-xl border border-gray-200 bg-gray-50/50 flex flex-col justify-between hover:border-gray-300 transition">
                        <div>
                          <div className="flex items-center justify-between">
                            <span className={`w-2 h-2 rounded-full ${flow.is_active ? "bg-emerald-500" : "bg-gray-400"}`}></span>
                            <span className="text-[10px] font-bold font-mono text-gray-600 bg-white px-2 py-0.5 rounded border border-gray-200">
                              {(flow.nodes || []).length} steps
                            </span>
                          </div>
                          <h4 className="font-bold text-sm text-gray-900 mt-2 truncate" title={flow.name}>{flow.name}</h4>
                          <p className="text-xs text-gray-500 mt-1">Trigger: <span className="font-semibold text-gray-700">{flow.trigger_type}</span></p>
                        </div>
                        <div className="mt-4 pt-3 border-t border-gray-200 flex items-center justify-between text-xs">
                          <span className={`font-semibold ${flow.is_active ? "text-emerald-600" : "text-gray-400"}`}>
                            {flow.is_active ? "Active" : "Paused"}
                          </span>
                          <button
                            onClick={() => {
                              handleTabChange("automations");
                              setEditingWorkflow(flow);
                            }}
                            className="font-bold text-[#25D366] hover:text-[#1EBE5D] flex items-center gap-1"
                          >
                            <Sliders className="w-3.5 h-3.5" /> Open Flow
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="py-8 text-center bg-gray-50 rounded-xl border border-dashed border-gray-200">
                    <p className="text-xs text-gray-500 mb-2">No visual journey automations created yet.</p>
                    <button
                      onClick={() => {
                        handleTabChange("automations");
                        handleOpenNewJourneyModal();
                      }}
                      className="text-xs font-bold text-[#25D366] hover:underline"
                    >
                      + Create First Journey Flow
                    </button>
                  </div>
                )}
              </div>

              {/* Recent Campaigns Table */}
              <div className="bg-white rounded-xl border border-gray-200 shadow-xs overflow-hidden">
                <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
                  <h3 className="font-bold text-gray-900 text-base">Broadcast Campaigns</h3>
                  <span className="text-xs text-gray-500">Auto-batches & DND filtered</span>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm text-gray-600">
                    <thead className="bg-gray-50 text-xs uppercase font-semibold text-gray-500 border-b border-gray-200">
                      <tr>
                        <th className="px-6 py-3">Campaign Title</th>
                        <th className="px-6 py-3">Template</th>
                        <th className="px-6 py-3">Target</th>
                        <th className="px-6 py-3">Language</th>
                        <th className="px-6 py-3">Recipients</th>
                        <th className="px-6 py-3">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {campaigns.map((c) => (
                        <tr key={c.id} className="hover:bg-gray-50/80 transition">
                          <td className="px-6 py-4 font-semibold text-gray-900">{c.title}</td>
                          <td className="px-6 py-4 font-mono text-xs text-gray-600">{c.template_name}</td>
                          <td className="px-6 py-4">{c.target_filter}</td>
                          <td className="px-6 py-4 uppercase font-semibold text-xs">{c.language}</td>
                          <td className="px-6 py-4 font-bold text-gray-900">{c.successful_sends} / {c.total_recipients}</td>
                          <td className="px-6 py-4">
                            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-green-50 text-[#10B981] border border-green-200">
                              <CheckCircle2 className="w-3.5 h-3.5" /> {c.status}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>

  );
}
