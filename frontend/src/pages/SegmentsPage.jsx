import React, { useState, useEffect, useMemo } from "react";
import axios from "axios";
import {
  Users,
  Plus,
  Trash2,
  RefreshCw,
  Search,
  Filter,
  Layers,
  ArrowRight,
  X,
  Phone,
  Mail,
  MapPin,
  Calendar,
  CheckCircle2,
  Clock,
  Sparkles,
  ShoppingBag,
  UserPlus,
  Crown,
  LayoutGrid,
  Table as TableIcon
} from "lucide-react";
import { formatToISTDate } from "../utils/dateUtils";

export default function SegmentsPage() {
  const [segments, setSegments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedSegmentId, setSelectedSegmentId] = useState(null);
  const [segmentContacts, setSegmentContacts] = useState([]);
  const [contactsLoading, setContactsLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [viewMode, setViewMode] = useState("cards"); // "cards" or "table"
  const [showCreateModal, setShowCreateModal] = useState(false);

  // Form state for creating a custom segment
  const [newSegment, setNewSegment] = useState({
    name: "",
    description: "",
    criteriaType: "orders",
    min_orders: "",
    max_orders: "",
    inactivity_days: "",
    city: "",
    state: "",
    tag: "",
    created_mode: "single", // "single" or "range"
    created_date: "",
    created_from: "",
    created_to: ""
  });
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");

  const fetchSegments = async (preserveSelectedId = null) => {
    setLoading(true);
    try {
      const token = localStorage.getItem("token");
      const res = await axios.get("/api/segments", {
        headers: token ? { Authorization: `Bearer ${token}` } : {}
      });
      const data = res.data || [];
      setSegments(data);
      if (data.length > 0) {
        const idToSelect = preserveSelectedId || selectedSegmentId || data[0].id;
        const target = data.find((s) => s.id === idToSelect) || data[0];
        setSelectedSegmentId(target.id);
        fetchSegmentContacts(target.id);
      }
    } catch (err) {
      console.error("Failed to load segments:", err);
    } finally {
      setLoading(false);
    }
  };

  const fetchSegmentContacts = async (segId) => {
    setContactsLoading(true);
    try {
      const token = localStorage.getItem("token");
      const res = await axios.get(`/api/segments/${segId}/contacts`, {
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

  useEffect(() => {
    fetchSegments();
  }, []);

  const handleSelectSegment = (segId) => {
    setSelectedSegmentId(segId);
    fetchSegmentContacts(segId);
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
    } else if (newSegment.criteriaType === "state") {
      if (newSegment.state.trim()) criteria.state = newSegment.state.trim();
    } else if (newSegment.criteriaType === "tag") {
      if (newSegment.tag.trim()) criteria.tag = newSegment.tag.trim();
    } else if (newSegment.criteriaType === "created_date") {
      if (newSegment.created_mode === "single") {
        if (!newSegment.created_date) {
          setCreateError("Please select a valid date for contact creation.");
          setCreating(false);
          return;
        }
        criteria.created_date = newSegment.created_date;
      } else {
        if (!newSegment.created_from && !newSegment.created_to) {
          setCreateError("Please select at least a From or To date for the range.");
          setCreating(false);
          return;
        }
        if (newSegment.created_from) criteria.created_from = newSegment.created_from;
        if (newSegment.created_to) criteria.created_to = newSegment.created_to;
      }
    }

    try {
      const token = localStorage.getItem("token");
      const res = await axios.post(
        "/api/segments",
        {
          name: newSegment.name.trim(),
          description: newSegment.description.trim() || undefined,
          icon: "Users",
          criteria
        },
        { headers: token ? { Authorization: `Bearer ${token}` } : {} }
      );

      setShowCreateModal(false);
      setNewSegment({
        name: "",
        description: "",
        criteriaType: "orders",
        min_orders: "",
        max_orders: "",
        inactivity_days: "",
        city: "",
        state: "",
        tag: "",
        created_mode: "single",
        created_date: "",
        created_from: "",
        created_to: ""
      });
      fetchSegments(res.data.id);
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
      fetchSegments();
    } catch (err) {
      alert("Error deleting segment: " + (err.response?.data?.detail || err.message));
    }
  };

  const activeSegment = segments.find((s) => s.id === selectedSegmentId) || segments[0];

  const filteredContacts = useMemo(() => {
    if (!searchTerm.trim()) return segmentContacts;
    const term = searchTerm.toLowerCase();
    return segmentContacts.filter(
      (c) =>
        (c.name && c.name.toLowerCase().includes(term)) ||
        (c.phone && c.phone.includes(term)) ||
        (c.city && c.city.toLowerCase().includes(term)) ||
        (c.tags && c.tags.toLowerCase().includes(term))
    );
  }, [segmentContacts, searchTerm]);

  return (
    <>
      <div className="bg-white rounded-xl border border-gray-200 shadow-xs overflow-hidden">
        {/* Main Header Bar */}
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between flex-wrap gap-3">
          <div>
            <div className="flex items-center gap-2.5">
              <h3 className="font-bold text-gray-900 text-base">Contact Segments</h3>
              <span className="text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 px-2 py-0.5 rounded-full">
                {segments.length} Segments
              </span>
            </div>
            <p className="text-xs text-gray-500 mt-0.5">
              Targeted customer cohorts for promotional broadcasts, re-engagement, and VIP flows
            </p>
          </div>
          <div className="flex items-center gap-3">
            {/* View Mode Toggle: Cards Overview vs Detailed Contacts Table */}
            <div className="flex items-center bg-gray-100 p-0.5 rounded-lg border border-gray-200">
              <button
                type="button"
                onClick={() => setViewMode("cards")}
                className={`flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-semibold transition cursor-pointer ${
                  viewMode === "cards"
                    ? "bg-white text-gray-900 shadow-xs"
                    : "text-gray-500 hover:text-gray-900"
                }`}
                title="View All Segments as Cards"
              >
                <LayoutGrid className="w-3.5 h-3.5" />
                <span>Segment Cards</span>
              </button>
              <button
                type="button"
                onClick={() => setViewMode("table")}
                className={`flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-semibold transition cursor-pointer ${
                  viewMode === "table"
                    ? "bg-white text-gray-900 shadow-xs"
                    : "text-gray-500 hover:text-gray-900"
                }`}
                title="View Contacts Roster"
              >
                <TableIcon className="w-3.5 h-3.5" />
                <span>Contacts Roster</span>
              </button>
            </div>

            <button
              onClick={() => fetchSegments(selectedSegmentId)}
              disabled={loading}
              className="flex items-center gap-1.5 bg-gray-100 hover:bg-gray-200 text-gray-800 border border-gray-300 px-3.5 py-1.5 rounded-lg text-xs font-semibold shadow-xs transition cursor-pointer disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 text-gray-600 ${loading ? "animate-spin" : ""}`} />
              Refresh
            </button>
            <button
              onClick={() => setShowCreateModal(true)}
              className="flex items-center gap-1.5 bg-[#25D366] hover:bg-[#1EBE5D] text-white px-3.5 py-1.5 rounded-lg font-semibold text-xs shadow-sm transition cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5" />
              New Segment
            </button>
          </div>
        </div>

        {/* Segments Pill Filter Row */}
        <div className="px-6 py-3 border-b border-gray-200 bg-gray-50/70 flex items-center gap-2 overflow-x-auto">
          {segments.map((seg) => {
            const isSelected = seg.id === selectedSegmentId;
            return (
              <div
                key={seg.id}
                onClick={() => handleSelectSegment(seg.id)}
                className={`group/pill flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition cursor-pointer border ${
                  isSelected
                    ? "bg-white text-gray-900 border-gray-300 shadow-xs ring-1 ring-gray-200"
                    : "bg-transparent text-gray-600 border-transparent hover:bg-gray-200/60 hover:text-gray-900"
                }`}
              >
                <span>{seg.name}</span>
                <span
                  className={`text-[10px] font-bold px-1.5 py-0.2 rounded-full ${
                    isSelected ? "bg-[#25D366]/20 text-emerald-800" : "bg-gray-200 text-gray-700"
                  }`}
                >
                  {seg.matching_contacts_count}
                </span>
                {!seg.is_predefined && (
                  <button
                    type="button"
                    onClick={(e) => handleDeleteSegment(seg.id, seg.name, e)}
                    className="ml-1 text-gray-400 hover:text-rose-600 hover:bg-rose-50 p-0.5 rounded transition cursor-pointer"
                    title="Delete custom segment"
                  >
                    <Trash2 className="w-3 h-3" />
                  </button>
                )}
              </div>
            );
          })}
        </div>

        {/* View 1: Segments Cards Directory View */}
        {viewMode === "cards" && (
          <div className="p-6 bg-gray-50/50">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h4 className="text-sm font-bold text-gray-900">All Audiences & Segments</h4>
                <p className="text-xs text-gray-500">
                  Manage your dynamic contact segments, delete duplicates, or explore cohort members
                </p>
              </div>
              <div className="text-xs font-semibold text-gray-500">
                {segments.filter((s) => !s.is_predefined).length} Custom • {segments.filter((s) => s.is_predefined).length} System
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {segments.map((seg) => {
                const isSelected = seg.id === selectedSegmentId;
                const criteria = seg.criteria || {};
                let ruleDesc = "All contacts with active opt-in status";
                if (criteria.city) ruleDesc = `City contains: "${criteria.city}"`;
                else if (criteria.state) ruleDesc = `State/Region: "${criteria.state}"`;
                else if (criteria.min_orders !== undefined && criteria.max_orders !== undefined) ruleDesc = `Orders between ${criteria.min_orders} and ${criteria.max_orders}`;
                else if (criteria.min_orders !== undefined) ruleDesc = `Orders: ${criteria.min_orders}+`;
                else if (criteria.order_eq !== undefined) ruleDesc = `Exact orders: ${criteria.order_eq}`;
                else if (criteria.inactivity_days) ruleDesc = `Inactive for ≥ ${criteria.inactivity_days} days`;
                else if (criteria.tag) ruleDesc = `Tag contains: "${criteria.tag}"`;
                else if (criteria.created_date) ruleDesc = `Imported on: ${criteria.created_date}`;
                else if (criteria.created_from && criteria.created_to) ruleDesc = `Imported between: ${criteria.created_from} to ${criteria.created_to}`;
                else if (criteria.created_from) ruleDesc = `Imported from: ${criteria.created_from}`;
                else if (criteria.created_to) ruleDesc = `Imported up to: ${criteria.created_to}`;

                return (
                  <div
                    key={seg.id}
                    className={`bg-white rounded-xl border p-4.5 transition-all shadow-xs flex flex-col justify-between ${
                      isSelected
                        ? "border-[#25D366] ring-2 ring-[#25D366]/15 shadow-sm"
                        : "border-gray-200 hover:border-gray-300 hover:shadow-md"
                    }`}
                  >
                    <div>
                      {/* Top Bar of Card */}
                      <div className="flex items-start justify-between gap-2 mb-2">
                        <div className="flex items-center gap-2">
                          <div
                            className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${
                              seg.is_predefined
                                ? "bg-emerald-50 text-emerald-700"
                                : "bg-purple-50 text-purple-700"
                            }`}
                          >
                            <Users className="w-4 h-4" />
                          </div>
                          <div>
                            <h5 className="font-bold text-gray-900 text-sm leading-tight flex items-center gap-1.5">
                              {seg.name}
                            </h5>
                            <span
                              className={`inline-block text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.2 rounded mt-0.5 ${
                                seg.is_predefined
                                  ? "bg-gray-100 text-gray-600"
                                  : "bg-purple-100/70 text-purple-800"
                              }`}
                            >
                              {seg.is_predefined ? "System Default" : "Custom Rule"}
                            </span>
                          </div>
                        </div>

                        {/* Direct Delete Button on Card for custom segments */}
                        {!seg.is_predefined && (
                          <button
                            type="button"
                            onClick={(e) => handleDeleteSegment(seg.id, seg.name, e)}
                            className="text-gray-400 hover:text-rose-600 hover:bg-rose-50 p-1.5 rounded-md transition cursor-pointer"
                            title={`Delete segment "${seg.name}"`}
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        )}
                      </div>

                      {/* Rule Description */}
                      <div className="my-3 bg-gray-50 border border-gray-100 rounded-lg p-2.5">
                        <div className="text-[10px] font-bold uppercase tracking-wider text-gray-400 mb-0.5">
                          Filter Criteria
                        </div>
                        <div className="text-xs font-semibold text-gray-700 font-mono break-all">
                          {ruleDesc}
                        </div>
                      </div>
                    </div>

                    {/* Bottom metrics and Action Bar */}
                    <div className="pt-3 border-t border-gray-100 flex items-center justify-between">
                      <div className="flex items-center gap-1.5">
                        <span className="text-lg font-black text-gray-900">
                          {seg.matching_contacts_count}
                        </span>
                        <span className="text-xs text-gray-500 font-medium">contacts</span>
                      </div>

                      <button
                        type="button"
                        onClick={() => {
                          handleSelectSegment(seg.id);
                          setViewMode("table");
                        }}
                        className="flex items-center gap-1 text-xs font-bold text-[#25D366] hover:text-[#1EBE5D] hover:underline cursor-pointer"
                      >
                        <span>View Roster</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* View 2: Detailed Contacts Roster Table */}
        {viewMode === "table" && (
          <>
            {/* Sub-header: Current Segment Overview & Search */}
            <div className="px-6 py-3.5 bg-white border-b border-gray-100 flex items-center justify-between flex-wrap gap-3">
              <div className="flex items-center gap-2">
                <span className="font-bold text-gray-900 text-sm">{activeSegment?.name || "Segment"}</span>
                <span className="text-xs text-gray-400">•</span>
                <span className="text-xs text-gray-500">{activeSegment?.description || "Dynamic customer cohort"}</span>
                {!activeSegment?.is_predefined && (
                  <button
                    type="button"
                    onClick={(e) => handleDeleteSegment(activeSegment.id, activeSegment.name, e)}
                    className="ml-2 flex items-center gap-1 text-xs font-semibold text-rose-600 hover:text-rose-700 bg-rose-50 hover:bg-rose-100 px-2 py-0.5 rounded transition cursor-pointer"
                  >
                    <Trash2 className="w-3 h-3" />
                    <span>Delete Segment</span>
                  </button>
                )}
              </div>

              <div className="relative w-64">
                <Search className="w-3.5 h-3.5 text-gray-400 absolute left-3 top-2.5" />
                <input
                  type="text"
                  placeholder="Search in this segment..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full pl-9 pr-3.5 py-1.5 border border-gray-200 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-[#25D366]"
                />
              </div>
            </div>

            {/* Contacts Table */}
            <div className="overflow-x-auto">
              {contactsLoading ? (
                <div className="py-16 text-center text-xs text-gray-400">
                  <RefreshCw className="w-5 h-5 animate-spin mx-auto text-gray-500 mb-2" />
                  Loading segment contacts...
                </div>
              ) : filteredContacts.length === 0 ? (
                <div className="py-16 text-center text-gray-400 text-xs">
                  <Users className="w-8 h-8 mx-auto text-gray-300 mb-2" />
                  No contacts found in this segment.
                </div>
              ) : (
                <table className="w-full text-left text-sm text-gray-600">
                  <thead className="bg-gray-50 text-xs uppercase font-semibold text-gray-500 border-b border-gray-200">
                    <tr>
                      <th className="px-5 py-3">ID</th>
                      <th className="px-5 py-3">Customer Name</th>
                      <th className="px-5 py-3">Phone</th>
                      <th className="px-5 py-3">Orders</th>
                      <th className="px-5 py-3">City</th>
                      <th className="px-5 py-3">Tags</th>
                      <th className="px-5 py-3">Imported Date</th>
                      <th className="px-5 py-3 text-right">Last Order</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 text-xs">
                    {filteredContacts.map((c) => (
                      <tr key={c.id} className="hover:bg-gray-50/80 transition">
                        <td className="px-5 py-3.5 font-mono text-gray-400">#{c.id}</td>
                        <td className="px-5 py-3.5 font-bold text-gray-900">{c.name || "Customer"}</td>
                        <td className="px-5 py-3.5 font-mono text-gray-700">{c.phone}</td>
                        <td className="px-5 py-3.5 font-semibold text-gray-900">{c.total_orders || 0}</td>
                        <td className="px-5 py-3.5 text-gray-600">{c.city || "—"}</td>
                        <td className="px-5 py-3.5">
                          {c.tags ? (
                            <span className="inline-block bg-gray-100 text-gray-700 px-2 py-0.5 rounded text-[11px] font-medium border border-gray-200/60">
                              {c.tags}
                            </span>
                          ) : (
                            <span className="text-gray-400">—</span>
                          )}
                        </td>
                        <td className="px-5 py-3.5 text-gray-600 whitespace-nowrap">
                          {c.created_at ? (
                            <div className="flex items-center gap-1.5">
                              <Clock className="w-3.5 h-3.5 text-gray-400" />
                              <span>{formatToISTDate(c.created_at)}</span>
                            </div>
                          ) : (
                            <span className="text-gray-400">—</span>
                          )}
                        </td>
                        <td className="px-5 py-3.5 text-right text-gray-500">
                          {c.last_order_date ? formatToISTDate(c.last_order_date) : "No orders yet"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

            {/* Table Footer */}
            <div className="px-6 py-3 border-t border-gray-200 bg-gray-50 text-xs text-gray-500 flex items-center justify-between">
              <span>
                Showing <strong className="text-gray-800">{filteredContacts.length}</strong> matching contacts
              </span>
              <span className="text-[11px] text-gray-400">
                Contacts update automatically based on order and engagement activity
              </span>
            </div>
          </>
        )}
      </div>

      {/* Modal: Create Custom Segment */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-xl max-w-lg w-full shadow-2xl border border-gray-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
              <h3 className="font-bold text-gray-900 text-base">Create Custom Segment</h3>
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
                <div className="p-3 bg-rose-50 border border-rose-200 text-rose-700 text-xs rounded-lg">
                  {createError}
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wide mb-1.5">
                  Segment Name *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Surat High Value, Wholesale Club"
                  value={newSegment.name}
                  onChange={(e) => setNewSegment({ ...newSegment, name: e.target.value })}
                  className="w-full px-3.5 py-2 border border-gray-200 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-[#25D366]"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wide mb-1.5">
                  Description
                </label>
                <input
                  type="text"
                  placeholder="Short note about who this segment targets"
                  value={newSegment.description}
                  onChange={(e) => setNewSegment({ ...newSegment, description: e.target.value })}
                  className="w-full px-3.5 py-2 border border-gray-200 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-[#25D366]"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wide mb-1.5">
                  Segmentation Rule Type
                </label>
                <select
                  value={newSegment.criteriaType}
                  onChange={(e) => setNewSegment({ ...newSegment, criteriaType: e.target.value })}
                  className="w-full px-3.5 py-2 border border-gray-200 rounded-lg text-xs font-medium focus:outline-none focus:ring-2 focus:ring-[#25D366]"
                >
                  <option value="city">Customer City / Location</option>
                  <option value="state">Customer State / Region</option>
                  <option value="orders">Total Orders Range (Purchase Volume)</option>
                  <option value="inactivity">Days Since Last Order (Inactivity)</option>
                  <option value="tag">Customer Tag / Label</option>
                  <option value="created_date">Contact Created / Imported Date</option>
                </select>
              </div>

              {/* Dynamic rule fields */}
              {newSegment.criteriaType === "orders" && (
                <div className="grid grid-cols-2 gap-3 p-3.5 bg-gray-50 rounded-lg border border-gray-200">
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
                      className="w-full px-3 py-1.5 text-xs bg-white border border-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-[#25D366]"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-bold text-gray-600 mb-1">
                      Max Orders (&le;)
                    </label>
                    <input
                      type="number"
                      min="0"
                      placeholder="e.g. 10 (optional)"
                      value={newSegment.max_orders}
                      onChange={(e) => setNewSegment({ ...newSegment, max_orders: e.target.value })}
                      className="w-full px-3 py-1.5 text-xs bg-white border border-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-[#25D366]"
                    />
                  </div>
                </div>
              )}

              {newSegment.criteriaType === "inactivity" && (
                <div className="p-3.5 bg-gray-50 rounded-lg border border-gray-200">
                  <label className="block text-[11px] font-bold text-gray-600 mb-1">
                    Inactive For At Least (Days)
                  </label>
                  <input
                    type="number"
                    min="1"
                    placeholder="e.g. 30, 60, or 90 days"
                    value={newSegment.inactivity_days}
                    onChange={(e) => setNewSegment({ ...newSegment, inactivity_days: e.target.value })}
                    className="w-full px-3 py-1.5 text-xs bg-white border border-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-[#25D366]"
                  />
                </div>
              )}

              {newSegment.criteriaType === "city" && (
                <div className="p-3.5 bg-gray-50 rounded-lg border border-gray-200">
                  <label className="block text-[11px] font-bold text-gray-600 mb-1">
                    City Name (Contains)
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Surat, Mumbai, Bhavnagar, Ahmedabad"
                    value={newSegment.city}
                    onChange={(e) => setNewSegment({ ...newSegment, city: e.target.value })}
                    className="w-full px-3 py-1.5 text-xs bg-white border border-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-[#25D366]"
                  />
                </div>
              )}

              {newSegment.criteriaType === "state" && (
                <div className="p-3.5 bg-gray-50 rounded-lg border border-gray-200">
                  <label className="block text-[11px] font-bold text-gray-600 mb-1">
                    State / Region Name (Contains)
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Gujarat, Maharashtra, Rajasthan"
                    value={newSegment.state}
                    onChange={(e) => setNewSegment({ ...newSegment, state: e.target.value })}
                    className="w-full px-3 py-1.5 text-xs bg-white border border-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-[#25D366]"
                  />
                </div>
              )}

              {newSegment.criteriaType === "tag" && (
                <div className="p-3.5 bg-gray-50 rounded-lg border border-gray-200">
                  <label className="block text-[11px] font-bold text-gray-600 mb-1">
                    Customer Tag (Contains)
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. VIP, Wholesale, Lead"
                    value={newSegment.tag}
                    onChange={(e) => setNewSegment({ ...newSegment, tag: e.target.value })}
                    className="w-full px-3 py-1.5 text-xs bg-white border border-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-[#25D366]"
                  />
                </div>
              )}

              {newSegment.criteriaType === "created_date" && (
                <div className="p-3.5 bg-gray-50 rounded-lg border border-gray-200 space-y-3">
                  <div>
                    <label className="block text-[11px] font-bold text-gray-600 mb-1.5">
                      Target Mode
                    </label>
                    <div className="flex items-center gap-4 text-xs">
                      <label className="inline-flex items-center gap-1.5 cursor-pointer font-medium text-gray-700">
                        <input
                          type="radio"
                          name="created_mode"
                          value="single"
                          checked={newSegment.created_mode === "single"}
                          onChange={() => setNewSegment({ ...newSegment, created_mode: "single" })}
                          className="text-[#25D366] focus:ring-[#25D366]"
                        />
                        <span>Specific Single Date</span>
                      </label>
                      <label className="inline-flex items-center gap-1.5 cursor-pointer font-medium text-gray-700">
                        <input
                          type="radio"
                          name="created_mode"
                          value="range"
                          checked={newSegment.created_mode === "range"}
                          onChange={() => setNewSegment({ ...newSegment, created_mode: "range" })}
                          className="text-[#25D366] focus:ring-[#25D366]"
                        />
                        <span>Date Range Group</span>
                      </label>
                    </div>
                  </div>

                  {newSegment.created_mode === "single" ? (
                    <div>
                      <label className="block text-[11px] font-bold text-gray-600 mb-1">
                        Select Exact Created Date
                      </label>
                      <input
                        type="date"
                        required
                        value={newSegment.created_date}
                        onChange={(e) => setNewSegment({ ...newSegment, created_date: e.target.value })}
                        className="w-full px-3 py-1.5 text-xs bg-white border border-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-[#25D366]"
                      />
                      <p className="text-[10px] text-gray-400 mt-1">
                        Targets all customers imported/created on this exact calendar day (00:00 to 23:59).
                      </p>
                    </div>
                  ) : (
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-[11px] font-bold text-gray-600 mb-1">
                          From (Start Date)
                        </label>
                        <input
                          type="date"
                          value={newSegment.created_from}
                          onChange={(e) => setNewSegment({ ...newSegment, created_from: e.target.value })}
                          className="w-full px-3 py-1.5 text-xs bg-white border border-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-[#25D366]"
                        />
                      </div>
                      <div>
                        <label className="block text-[11px] font-bold text-gray-600 mb-1">
                          To (End Date)
                        </label>
                        <input
                          type="date"
                          value={newSegment.created_to}
                          onChange={(e) => setNewSegment({ ...newSegment, created_to: e.target.value })}
                          className="w-full px-3 py-1.5 text-xs bg-white border border-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-[#25D366]"
                        />
                      </div>
                    </div>
                  )}
                </div>
              )}

              <div className="pt-2 flex items-center justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-3.5 py-1.5 text-xs font-semibold text-gray-600 hover:bg-gray-100 rounded-lg transition cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creating}
                  className="px-4 py-1.5 text-xs font-semibold text-white bg-[#25D366] hover:bg-[#1EBE5D] rounded-lg shadow-sm transition cursor-pointer disabled:opacity-50"
                >
                  {creating ? "Creating..." : "Save Segment"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
