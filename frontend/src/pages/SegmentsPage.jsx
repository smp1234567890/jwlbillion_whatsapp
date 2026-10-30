import React, { useState, useEffect } from "react";
import axios from "axios";
import {
  Users,
  UserCheck,
  Plus,
  Trash2,
  RefreshCw,
  Search,
  Filter,
  Sparkles,
  Crown,
  ShoppingBag,
  Clock,
  ArrowRight,
  UserPlus,
  CheckCircle2,
  Layers,
  ChevronRight,
  ExternalLink,
  X,
  Phone,
  Mail,
  MapPin,
  Calendar
} from "lucide-react";
import { formatToISTDate } from "../utils/dateUtils";

const ICON_MAP = {
  Users: Users,
  Crown: Crown,
  Sparkles: Sparkles,
  ShoppingBag: ShoppingBag,
  UserPlus: UserPlus,
  Clock: Clock,
  Layers: Layers
};

export default function SegmentsPage({ onSelectSegmentForCampaign }) {
  const [segments, setSegments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedSegment, setSelectedSegment] = useState(null);
  const [segmentContacts, setSegmentContacts] = useState([]);
  const [contactsLoading, setContactsLoading] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);

  // Form state for creating a new custom segment
  const [newSegment, setNewSegment] = useState({
    name: "",
    description: "",
    icon: "Users",
    criteriaType: "orders", // orders, inactivity, city, tag
    min_orders: "",
    max_orders: "",
    inactivity_days: "",
    city: "",
    tag: ""
  });
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");

  const fetchSegments = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem("token");
      const res = await axios.get("/api/segments", {
        headers: token ? { Authorization: `Bearer ${token}` } : {}
      });
      setSegments(res.data || []);
      // If none selected or selected was updated, select first
      if (res.data && res.data.length > 0 && !selectedSegment) {
        handleSelectSegment(res.data[0]);
      }
    } catch (err) {
      console.error("Failed to load segments:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSegments();
  }, []);

  const handleSelectSegment = async (seg) => {
    setSelectedSegment(seg);
    setContactsLoading(true);
    try {
      const token = localStorage.getItem("token");
      const res = await axios.get(`/api/segments/${seg.id}/contacts`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {}
      });
      setSegmentContacts(res.data?.contacts || []);
    } catch (err) {
      console.error("Failed to load segment contacts:", err);
      setSegmentContacts([]);
    } finally {
      setContactsLoading(false);
    }
  };

  const handleCreateSegment = async (e) => {
    e.preventDefault();
    if (!newSegment.name.trim()) return;

    setCreating(true);
    setCreateError("");

    const criteria = {};
    if (newSegment.criteriaType === "orders") {
      if (newSegment.min_orders !== "") criteria.min_orders = parseInt(newSegment.min_orders);
      if (newSegment.max_orders !== "") criteria.max_orders = parseInt(newSegment.max_orders);
    } else if (newSegment.criteriaType === "inactivity") {
      if (newSegment.inactivity_days !== "") criteria.inactivity_days = parseInt(newSegment.inactivity_days);
    } else if (newSegment.criteriaType === "city") {
      if (newSegment.city.trim()) criteria.city = newSegment.city.trim();
    } else if (newSegment.criteriaType === "tag") {
      if (newSegment.tag.trim()) criteria.tag = newSegment.tag.trim();
    }

    try {
      const token = localStorage.getItem("token");
      const res = await axios.post(
        "/api/segments",
        {
          name: newSegment.name.trim(),
          description: newSegment.description.trim() || undefined,
          icon: newSegment.icon || "Users",
          criteria
        },
        { headers: token ? { Authorization: `Bearer ${token}` } : {} }
      );

      setShowCreateModal(false);
      setNewSegment({
        name: "",
        description: "",
        icon: "Users",
        criteriaType: "orders",
        min_orders: "",
        max_orders: "",
        inactivity_days: "",
        city: "",
        tag: ""
      });
      await fetchSegments();
      handleSelectSegment(res.data);
    } catch (err) {
      setCreateError(err.response?.data?.detail || err.message || "Failed to create segment.");
    } finally {
      setCreating(false);
    }
  };

  const handleDeleteSegment = async (segId, segName, e) => {
    e?.stopPropagation();
    if (!window.confirm(`Delete the custom segment "${segName}"? This will not affect the actual contacts.`)) {
      return;
    }
    try {
      const token = localStorage.getItem("token");
      await axios.delete(`/api/segments/${segId}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {}
      });
      if (selectedSegment?.id === segId) {
        setSelectedSegment(null);
      }
      fetchSegments();
    } catch (err) {
      alert("Error deleting segment: " + (err.response?.data?.detail || err.message));
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white rounded-2xl p-6 border border-gray-100 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 text-white flex items-center justify-center shadow-sm">
            <Layers className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold text-gray-900">Contact Segmentation</h1>
              <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-100 text-indigo-800">
                Smart Cohorts
              </span>
            </div>
            <p className="text-xs text-gray-500 mt-0.5">
              Segment your customers by order volume, purchase recency, city, or tags to target WhatsApp broadcasts with precision.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={fetchSegments}
            disabled={loading}
            className="flex items-center gap-2 px-3.5 py-2 text-sm font-semibold text-gray-700 bg-gray-50 hover:bg-gray-100 border border-gray-200 rounded-xl transition cursor-pointer"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin text-indigo-600" : ""}`} />
            <span>Refresh</span>
          </button>
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-2 px-4 py-2 text-sm font-bold text-white bg-indigo-600 hover:bg-indigo-700 rounded-xl transition shadow-xs cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            <span>New Custom Segment</span>
          </button>
        </div>
      </div>

      {/* Main Two-Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Segments List */}
        <div className="lg:col-span-5 space-y-3">
          <div className="flex items-center justify-between px-1">
            <span className="text-xs font-bold uppercase tracking-wider text-gray-500">
              Active Segments ({segments.length})
            </span>
          </div>

          <div className="space-y-2.5">
            {segments.map((seg) => {
              const IconComp = ICON_MAP[seg.icon] || Users;
              const isSelected = selectedSegment?.id === seg.id;
              return (
                <div
                  key={seg.id}
                  onClick={() => handleSelectSegment(seg)}
                  className={`p-4 rounded-2xl border transition-all cursor-pointer relative group flex items-start justify-between gap-3 ${
                    isSelected
                      ? "bg-white border-indigo-500 ring-2 ring-indigo-500/10 shadow-sm"
                      : "bg-white border-gray-100 hover:border-gray-200 hover:shadow-xs"
                  }`}
                >
                  <div className="flex items-start gap-3 min-w-0">
                    <div
                      className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 transition ${
                        isSelected
                          ? "bg-indigo-600 text-white"
                          : "bg-indigo-50 text-indigo-600 group-hover:bg-indigo-100"
                      }`}
                    >
                      <IconComp className="w-5 h-5" />
                    </div>

                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <h3 className="text-sm font-bold text-gray-900 truncate">
                          {seg.name}
                        </h3>
                        {seg.is_predefined && (
                          <span className="text-[10px] font-bold text-gray-500 bg-gray-100 px-1.5 py-0.2 rounded shrink-0">
                            Predefined
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-gray-500 line-clamp-2 mt-0.5">
                        {seg.description || "Custom targeted filter rule"}
                      </p>
                    </div>
                  </div>

                  <div className="flex flex-col items-end shrink-0 gap-2">
                    <span className="text-xs font-bold text-indigo-700 bg-indigo-50 px-2.5 py-1 rounded-full">
                      {seg.matching_contacts_count} contacts
                    </span>
                    {!seg.is_predefined && (
                      <button
                        type="button"
                        onClick={(e) => handleDeleteSegment(seg.id, seg.name, e)}
                        className="opacity-0 group-hover:opacity-100 p-1 text-gray-400 hover:text-rose-600 rounded-md transition"
                        title="Delete segment"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right: Segment Details & Contact Roster */}
        <div className="lg:col-span-7 space-y-4">
          {selectedSegment ? (
            <div className="bg-white rounded-2xl border border-gray-100 shadow-xs overflow-hidden">
              {/* Segment Banner */}
              <div className="p-5 border-b border-gray-100 bg-gradient-to-r from-gray-50/50 to-white flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-base font-bold text-gray-900">
                      {selectedSegment.name}
                    </h2>
                    <span className="text-xs font-bold text-indigo-700 bg-indigo-50 px-2.5 py-0.5 rounded-full">
                      {selectedSegment.matching_contacts_count} matches
                    </span>
                  </div>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {selectedSegment.description}
                  </p>
                </div>
              </div>

              {/* Contacts Table / List */}
              <div className="p-4">
                {contactsLoading ? (
                  <div className="p-12 text-center text-gray-400 text-sm">
                    <RefreshCw className="w-6 h-6 animate-spin mx-auto text-indigo-600 mb-2" />
                    Filtering segment contacts...
                  </div>
                ) : segmentContacts.length === 0 ? (
                  <div className="p-12 text-center text-gray-400 text-sm">
                    <Users className="w-10 h-10 mx-auto text-gray-300 mb-2" />
                    No contacts currently match this segment's criteria.
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead>
                        <tr className="border-b border-gray-100 text-gray-400 uppercase font-semibold">
                          <th className="pb-3 pl-2">Customer</th>
                          <th className="pb-3">Phone</th>
                          <th className="pb-3">Orders</th>
                          <th className="pb-3">City</th>
                          <th className="pb-3 pr-2">Tags</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-50">
                        {segmentContacts.map((c) => (
                          <tr key={c.id} className="hover:bg-gray-50/60 transition">
                            <td className="py-3 pl-2 font-bold text-gray-900">
                              {c.name}
                            </td>
                            <td className="py-3 text-gray-700 font-mono">
                              {c.phone}
                            </td>
                            <td className="py-3">
                              <span className="font-bold text-gray-900">
                                {c.total_orders || 0}
                              </span>
                            </td>
                            <td className="py-3 text-gray-500">
                              {c.city || "—"}
                            </td>
                            <td className="py-3 pr-2">
                              {c.tags ? (
                                <span className="inline-block bg-gray-100 text-gray-700 px-2 py-0.5 rounded text-[11px] font-medium">
                                  {c.tags}
                                </span>
                              ) : (
                                "—"
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="bg-white rounded-2xl border border-gray-100 p-12 text-center text-gray-400 shadow-xs">
              <Layers className="w-12 h-12 mx-auto text-gray-300 mb-3" />
              <p className="text-sm font-semibold text-gray-700">Select a segment</p>
              <p className="text-xs text-gray-400 mt-1">
                Choose a cohort on the left to view matching customer details.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Create Custom Segment Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full shadow-2xl border border-gray-100 overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center">
                  <Layers className="w-4 h-4" />
                </div>
                <h3 className="text-base font-bold text-gray-900">Create Custom Segment</h3>
              </div>
              <button
                type="button"
                onClick={() => setShowCreateModal(false)}
                className="text-gray-400 hover:text-gray-600 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateSegment} className="p-6 space-y-4">
              {createError && (
                <div className="p-3 bg-rose-50 border border-rose-200 text-rose-700 text-xs rounded-xl">
                  {createError}
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider mb-1.5">
                  Segment Name *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Surat High Value, Wholesale Club"
                  value={newSegment.name}
                  onChange={(e) => setNewSegment({ ...newSegment, name: e.target.value })}
                  className="w-full px-3.5 py-2 text-sm bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:border-indigo-500 focus:bg-white transition"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider mb-1.5">
                  Description
                </label>
                <input
                  type="text"
                  placeholder="Short note about who this segment targets"
                  value={newSegment.description}
                  onChange={(e) => setNewSegment({ ...newSegment, description: e.target.value })}
                  className="w-full px-3.5 py-2 text-sm bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:border-indigo-500 focus:bg-white transition"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider mb-1.5">
                  Segmentation Rule Type
                </label>
                <select
                  value={newSegment.criteriaType}
                  onChange={(e) => setNewSegment({ ...newSegment, criteriaType: e.target.value })}
                  className="w-full px-3.5 py-2 text-sm bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:border-indigo-500 focus:bg-white transition"
                >
                  <option value="orders">Total Orders Range (Purchase Volume)</option>
                  <option value="inactivity">Days Since Last Order (Inactivity)</option>
                  <option value="city">Customer City / Location</option>
                  <option value="tag">Customer Tag / Label</option>
                </select>
              </div>

              {/* Dynamic criteria fields */}
              {newSegment.criteriaType === "orders" && (
                <div className="grid grid-cols-2 gap-3 p-3.5 bg-gray-50 rounded-xl border border-gray-200/60">
                  <div>
                    <label className="block text-[11px] font-bold text-gray-600 mb-1">
                      Min Orders (&ge;)
                    </label>
                    <input
                      type="number"
                      min="0"
                      placeholder="e.g. 1 or 5"
                      value={newSegment.min_orders}
                      onChange={(e) => setNewSegment({ ...newSegment, min_orders: e.target.value })}
                      className="w-full px-3 py-1.5 text-xs bg-white border border-gray-200 rounded-lg focus:outline-none focus:border-indigo-500"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-bold text-gray-600 mb-1">
                      Max Orders (&lt;=)
                    </label>
                    <input
                      type="number"
                      min="0"
                      placeholder="e.g. 10 (optional)"
                      value={newSegment.max_orders}
                      onChange={(e) => setNewSegment({ ...newSegment, max_orders: e.target.value })}
                      className="w-full px-3 py-1.5 text-xs bg-white border border-gray-200 rounded-lg focus:outline-none focus:border-indigo-500"
                    />
                  </div>
                </div>
              )}

              {newSegment.criteriaType === "inactivity" && (
                <div className="p-3.5 bg-gray-50 rounded-xl border border-gray-200/60">
                  <label className="block text-[11px] font-bold text-gray-600 mb-1">
                    Inactive For At Least (Days)
                  </label>
                  <input
                    type="number"
                    min="1"
                    placeholder="e.g. 30, 60, or 90 days"
                    value={newSegment.inactivity_days}
                    onChange={(e) => setNewSegment({ ...newSegment, inactivity_days: e.target.value })}
                    className="w-full px-3 py-1.5 text-xs bg-white border border-gray-200 rounded-lg focus:outline-none focus:border-indigo-500"
                  />
                </div>
              )}

              {newSegment.criteriaType === "city" && (
                <div className="p-3.5 bg-gray-50 rounded-xl border border-gray-200/60">
                  <label className="block text-[11px] font-bold text-gray-600 mb-1">
                    City Name (Contains)
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. Surat, Mumbai, Ahmedabad"
                    value={newSegment.city}
                    onChange={(e) => setNewSegment({ ...newSegment, city: e.target.value })}
                    className="w-full px-3 py-1.5 text-xs bg-white border border-gray-200 rounded-lg focus:outline-none focus:border-indigo-500"
                  />
                </div>
              )}

              {newSegment.criteriaType === "tag" && (
                <div className="p-3.5 bg-gray-50 rounded-xl border border-gray-200/60">
                  <label className="block text-[11px] font-bold text-gray-600 mb-1">
                    Customer Tag (Contains)
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. VIP, Wholesale, Lead"
                    value={newSegment.tag}
                    onChange={(e) => setNewSegment({ ...newSegment, tag: e.target.value })}
                    className="w-full px-3 py-1.5 text-xs bg-white border border-gray-200 rounded-lg focus:outline-none focus:border-indigo-500"
                  />
                </div>
              )}

              <div className="pt-2 flex items-center justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 text-xs font-semibold text-gray-600 hover:bg-gray-100 rounded-xl transition cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creating}
                  className="px-5 py-2 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 rounded-xl shadow-xs transition cursor-pointer disabled:opacity-50"
                >
                  {creating ? "Creating..." : "Save Segment"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
