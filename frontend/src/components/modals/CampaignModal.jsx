import React, { useState, useMemo, useRef, useEffect } from "react";
import {
  Send,
  Calendar,
  Clock,
  Upload,
  Loader2,
  Search,
  Check,
  ChevronDown,
  X,
  Sparkles,
  FileText,
  Image as ImageIcon,
  Video,
  FileSpreadsheet,
  MapPin
} from "lucide-react";
import { formatScheduleDisplay } from "../../utils/dateUtils";
import api from "../../api";

export default function CampaignModal({
  isOpen,
  onClose,
  newCampaign,
  setNewCampaign,
  templates = [],
  contacts = [],
  onSubmit
}) {
  const [uploadingMedia, setUploadingMedia] = useState(false);
  const [templateSearch, setTemplateSearch] = useState("");
  const [isTemplateDropdownOpen, setIsTemplateDropdownOpen] = useState(false);
  const [segmentsList, setSegmentsList] = useState([]);
  const [testPhone, setTestPhone] = useState("");
  const [showTestInput, setShowTestInput] = useState(false);
  const [sendingTest, setSendingTest] = useState(false);
  const [testStatus, setTestStatus] = useState(null);
  const dropdownRef = useRef(null);

  const handleSendTestMessage = async () => {
    if (!testPhone.trim()) {
      alert("Please enter a WhatsApp phone number to test.");
      return;
    }
    if (!newCampaign.template_name) {
      alert("Please select a template first.");
      return;
    }
    setSendingTest(true);
    setTestStatus(null);
    try {
      const res = await api.post("/api/campaigns/test-send", {
        phone: testPhone.trim(),
        template_name: newCampaign.template_name,
        language: newCampaign.language || "en_IN",
        header_media: newCampaign.header_media
      });
      setTestStatus({ success: true, message: res.data.message || "Test message sent!" });
    } catch (err) {
      const errDetail = err.response?.data?.detail || err.message || "Failed to send test message";
      setTestStatus({ success: false, message: errDetail });
    } finally {
      setSendingTest(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      api.get("/api/segments")
        .then(res => setSegmentsList(res.data || []))
        .catch(err => console.error("Failed to load segments in CampaignModal:", err));
    }
  }, [isOpen]);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(event) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsTemplateDropdownOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const filteredTemplates = useMemo(() => {
    const q = templateSearch.toLowerCase().trim();
    const sorted = [...templates].sort((a, b) => (a.status === "APPROVED" ? -1 : 1));
    if (!q) return sorted;
    return sorted.filter(
      (t) =>
        t.template_name.toLowerCase().includes(q) ||
        (t.category || "").toLowerCase().includes(q) ||
        (t.header_type || "").toLowerCase().includes(q) ||
        (t.body_text || "").toLowerCase().includes(q) ||
        (t.language || "").toLowerCase().includes(q)
    );
  }, [templates, templateSearch]);

  const currentTmpl = useMemo(() => {
    return templates.find((t) => t.template_name === newCampaign.template_name) || templates[0];
  }, [templates, newCampaign.template_name]);

  if (!isOpen) return null;

  const handleCampaignMediaUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadingMedia(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const token = localStorage.getItem("token") || localStorage.getItem("access_token");
      const res = await api.post("/api/templates/upload-media", formData, {
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          "Content-Type": "multipart/form-data"
        }
      });
      if (res.data?.url) {
        setNewCampaign((prev) => ({
          ...prev,
          header_media: {
            ...(prev.header_media || {}),
            url: res.data.url
          }
        }));
      }
    } catch (err) {
      alert("Error uploading media file: " + (err.response?.data?.detail || err.message));
    } finally {
      setUploadingMedia(false);
    }
  };

  const getHeaderIcon = (type) => {
    switch ((type || "").toUpperCase()) {
      case "IMAGE":
        return <ImageIcon className="w-3.5 h-3.5 text-blue-500" />;
      case "VIDEO":
        return <Video className="w-3.5 h-3.5 text-purple-500" />;
      case "DOCUMENT":
        return <FileSpreadsheet className="w-3.5 h-3.5 text-amber-500" />;
      case "LOCATION":
        return <MapPin className="w-3.5 h-3.5 text-red-500" />;
      default:
        return <FileText className="w-3.5 h-3.5 text-gray-400" />;
    }
  };

  const headerType = (currentTmpl?.header_type || "NONE").toUpperCase();
  const needsMedia = ["IMAGE", "VIDEO", "DOCUMENT", "LOCATION"].includes(headerType);
  const isApproved = currentTmpl?.status === "APPROVED";

  return (
    <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4 md:p-6 z-50 animate-in fade-in duration-200">
      <div className="bg-white rounded-3xl max-w-2xl w-full p-7 md:p-8 shadow-2xl border border-gray-100 max-h-[92vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-start justify-between pb-5 border-b border-gray-100">
          <div>
            <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-700 text-xs font-semibold mb-2">
              <Sparkles className="w-3.5 h-3.5" />
              <span>Broadcast Campaign</span>
            </div>
            <h3 className="font-bold text-2xl text-gray-900 tracking-tight">Create WhatsApp Broadcast</h3>
            <p className="text-xs text-gray-500 mt-1">
              Configure parameters, select your Meta template, and dispatch or schedule a high-converting blast.
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-gray-400 hover:text-gray-600 rounded-full hover:bg-gray-100 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={onSubmit} className="mt-6 space-y-6">
          {/* Campaign Title */}
          <div>
            <label className="block text-xs font-semibold text-gray-700 tracking-wide mb-2">
              CAMPAIGN TITLE <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              required
              placeholder="e.g. Navratri Special Jewelry Festive Drop"
              value={newCampaign.title}
              onChange={(e) => setNewCampaign({ ...newCampaign, title: e.target.value })}
              className="w-full px-4 py-3 bg-gray-50/70 border border-gray-200 rounded-xl text-sm text-gray-800 placeholder-gray-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 transition"
            />
          </div>

          {/* Message Type Toggle */}
          <div>
            <label className="block text-xs font-semibold text-gray-700 tracking-wide mb-2">
              MESSAGE CATEGORY & COMPLIANCE
            </label>
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setNewCampaign({ ...newCampaign, message_type: "marketing" })}
                className={`p-3.5 rounded-2xl border text-left transition relative ${
                  newCampaign.message_type !== "utility"
                    ? "bg-emerald-50/50 border-emerald-500 ring-2 ring-emerald-500/20"
                    : "bg-white border-gray-200 hover:bg-gray-50"
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="font-bold text-sm text-gray-900">Marketing</span>
                  {newCampaign.message_type !== "utility" && (
                    <div className="w-4 h-4 rounded-full bg-emerald-500 text-white flex items-center justify-center">
                      <Check className="w-3 h-3 stroke-3" />
                    </div>
                  )}
                </div>
                <p className="text-[11px] text-gray-500 leading-relaxed">
                  Promotions, drops & offers. Requires active customer opt-in.
                </p>
              </button>

              <button
                type="button"
                onClick={() => setNewCampaign({ ...newCampaign, message_type: "utility" })}
                className={`p-3.5 rounded-2xl border text-left transition relative ${
                  newCampaign.message_type === "utility"
                    ? "bg-blue-50/50 border-blue-500 ring-2 ring-blue-500/20"
                    : "bg-white border-gray-200 hover:bg-gray-50"
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="font-bold text-sm text-gray-900">Utility</span>
                  {newCampaign.message_type === "utility" && (
                    <div className="w-4 h-4 rounded-full bg-blue-500 text-white flex items-center justify-center">
                      <Check className="w-3 h-3 stroke-3" />
                    </div>
                  )}
                </div>
                <p className="text-[11px] text-gray-500 leading-relaxed">
                  Order updates, transactional alerts. Delivered regardless of promo opt-out.
                </p>
              </button>
            </div>
          </div>

          {/* Searchable Template Selector */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs font-semibold text-gray-700 tracking-wide">
                WHATSAPP APPROVED TEMPLATE <span className="text-red-500">*</span>
              </label>
              {templates.length > 0 && (
                <span className="text-xs font-medium text-emerald-600">
                  {templates.filter((t) => t.status === "APPROVED").length} Approved by Meta
                </span>
              )}
            </div>

            {/* Dropdown Container */}
            <div className="relative" ref={dropdownRef}>
              <div
                onClick={() => setIsTemplateDropdownOpen(!isTemplateDropdownOpen)}
                className={`w-full px-4 py-3 bg-gray-50/70 border rounded-xl text-sm flex items-center justify-between cursor-pointer transition ${
                  isTemplateDropdownOpen
                    ? "bg-white border-emerald-500 ring-2 ring-emerald-500/20"
                    : "border-gray-200 hover:border-gray-300"
                }`}
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  {getHeaderIcon(currentTmpl?.header_type)}
                  <span className="font-mono font-medium text-gray-900 truncate">
                    {currentTmpl ? currentTmpl.template_name : "Select a template..."}
                  </span>
                  {currentTmpl && (
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded-md bg-gray-100 text-gray-600 font-mono">
                      {currentTmpl.language}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <span
                    className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                      isApproved ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"
                    }`}
                  >
                    {isApproved ? "APPROVED" : "PENDING"}
                  </span>
                  <ChevronDown className="w-4 h-4 text-gray-400" />
                </div>
              </div>

              {/* Expandable Dropdown Menu with Search */}
              {isTemplateDropdownOpen && (
                <div className="absolute top-full left-0 right-0 mt-2 bg-white rounded-2xl shadow-xl border border-gray-100 p-2 z-50 animate-in fade-in slide-in-from-top-1 duration-150">
                  {/* Search Input */}
                  <div className="relative mb-2">
                    <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
                    <input
                      type="text"
                      autoFocus
                      placeholder="Search templates by name, keyword, or language..."
                      value={templateSearch}
                      onChange={(e) => setTemplateSearch(e.target.value)}
                      className="w-full pl-9 pr-8 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs focus:bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
                    />
                    {templateSearch && (
                      <button
                        type="button"
                        onClick={() => setTemplateSearch("")}
                        className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>

                  {/* List of Templates */}
                  <div className="max-h-56 overflow-y-auto space-y-1 pr-1">
                    {filteredTemplates.length > 0 ? (
                      filteredTemplates.map((t) => {
                        const approved = t.status === "APPROVED";
                        const isSelected = t.template_name === newCampaign.template_name;
                        return (
                          <div
                            key={t.id}
                            onClick={() => {
                              setNewCampaign({
                                ...newCampaign,
                                template_name: t.template_name,
                                language: t.language || newCampaign.language || "en"
                              });
                              setIsTemplateDropdownOpen(false);
                            }}
                            className={`p-2.5 rounded-xl flex items-center justify-between cursor-pointer transition ${
                              isSelected
                                ? "bg-emerald-50/80 text-emerald-950 font-semibold"
                                : "hover:bg-gray-50 text-gray-700"
                            }`}
                          >
                            <div className="flex items-center gap-2 min-w-0">
                              {getHeaderIcon(t.header_type)}
                              <span className="font-mono text-xs truncate">{t.template_name}</span>
                              <span className="text-[10px] text-gray-400 font-mono">({t.language})</span>
                            </div>
                            <div className="flex items-center gap-1.5 flex-shrink-0">
                              {t.header_type && t.header_type !== "NONE" && (
                                <span className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded bg-purple-50 text-purple-700 border border-purple-100">
                                  {t.header_type}
                                </span>
                              )}
                              <span
                                className={`text-[10px] font-bold px-2 py-0.5 rounded-md ${
                                  approved
                                    ? "bg-emerald-100/80 text-emerald-800"
                                    : "bg-amber-100/80 text-amber-800"
                                }`}
                              >
                                {approved ? "APPROVED" : "PENDING"}
                              </span>
                              {isSelected && <Check className="w-3.5 h-3.5 text-emerald-600 ml-1" />}
                            </div>
                          </div>
                        );
                      })
                    ) : (
                      <div className="py-6 text-center text-xs text-gray-400">
                        No templates found matching "{templateSearch}"
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Template Preview Card */}
            {currentTmpl && (
              <div className="mt-3 p-4 bg-gray-50/60 rounded-2xl border border-gray-100 space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-gray-700">Template Preview</span>
                  <span className="text-[11px] font-mono text-gray-500 uppercase">{currentTmpl.category}</span>
                </div>
                <p className="text-xs text-gray-600 bg-white p-3 rounded-xl border border-gray-100 leading-relaxed font-sans">
                  {currentTmpl.body_text || "No preview available."}
                </p>
              </div>
            )}

            {/* Dynamic Media Attachment if Required */}
            {needsMedia && (
              <div className="mt-4 p-4 bg-purple-50/50 border border-purple-200/80 rounded-2xl space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {getHeaderIcon(headerType)}
                    <span className="text-xs font-bold text-purple-900 uppercase">
                      {headerType} Header Media
                    </span>
                  </div>
                  <span className="text-[10px] font-semibold text-purple-700 bg-purple-100/80 px-2 py-0.5 rounded-full">
                    Required by Meta Template
                  </span>
                </div>

                {headerType === "LOCATION" ? (
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <span className="text-[10px] font-bold text-purple-900 block mb-1">Latitude</span>
                      <input
                        type="text"
                        placeholder="e.g. 21.1702"
                        value={newCampaign.header_media?.latitude || ""}
                        onChange={(e) =>
                          setNewCampaign({
                            ...newCampaign,
                            header_media: { ...(newCampaign.header_media || {}), latitude: e.target.value }
                          })
                        }
                        className="w-full px-3 py-2 border border-purple-200 rounded-xl text-xs bg-white font-mono"
                      />
                    </div>
                    <div>
                      <span className="text-[10px] font-bold text-purple-900 block mb-1">Longitude</span>
                      <input
                        type="text"
                        placeholder="e.g. 72.8311"
                        value={newCampaign.header_media?.longitude || ""}
                        onChange={(e) =>
                          setNewCampaign({
                            ...newCampaign,
                            header_media: { ...(newCampaign.header_media || {}), longitude: e.target.value }
                          })
                        }
                        className="w-full px-3 py-2 border border-purple-200 rounded-xl text-xs bg-white font-mono"
                      />
                    </div>
                  </div>
                ) : (
                  <div className="space-y-2.5">
                    <div className="flex items-center gap-2">
                      <label
                        className={`cursor-pointer inline-flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold shadow-xs border transition ${
                          uploadingMedia
                            ? "bg-gray-100 text-gray-400 border-gray-200 cursor-not-allowed"
                            : "bg-white text-purple-800 border-purple-300 hover:bg-purple-100/50"
                        }`}
                      >
                        {uploadingMedia ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin text-purple-600" />
                        ) : (
                          <Upload className="w-3.5 h-3.5 text-purple-600" />
                        )}
                        <span>{uploadingMedia ? "Uploading to Server..." : `Upload ${headerType} File`}</span>
                        <input
                          type="file"
                          className="hidden"
                          disabled={uploadingMedia}
                          accept={
                            headerType === "IMAGE"
                              ? "image/*"
                              : headerType === "VIDEO"
                              ? "video/*"
                              : ".pdf,.doc,.docx"
                          }
                          onChange={handleCampaignMediaUpload}
                        />
                      </label>
                      <span className="text-xs text-gray-400 font-semibold">OR paste URL</span>
                    </div>

                    <input
                      type="text"
                      placeholder={
                        currentTmpl?.sample_values?.header_url ||
                        (headerType === "IMAGE"
                          ? "https://yourcdn.com/jewelry-banner.jpg"
                          : headerType === "VIDEO"
                          ? "https://yourcdn.com/product-video.mp4"
                          : "https://yourcdn.com/brochure.pdf")
                      }
                      value={newCampaign.header_media?.url || ""}
                      onChange={(e) =>
                        setNewCampaign({
                          ...newCampaign,
                          header_media: { ...(newCampaign.header_media || {}), url: e.target.value }
                        })
                      }
                      className="w-full px-3.5 py-2.5 border border-purple-200 rounded-xl text-xs bg-white font-mono focus:outline-none focus:ring-2 focus:ring-purple-400"
                    />
                    <p className="text-[10px] text-purple-700">
                      {newCampaign.header_media?.url
                        ? "Custom campaign media attached."
                        : currentTmpl?.sample_values?.header_url
                        ? `Will default to template sample: ${currentTmpl.sample_values.header_url}`
                        : `Upload or enter a public HTTPS URL for the broadcast ${headerType.toLowerCase()}.`}
                    </p>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Audience & Per-Day Limit */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-gray-700 tracking-wide mb-2">
                AUDIENCE SEGMENT
              </label>
              <select
                value={newCampaign.target_filter}
                onChange={(e) => setNewCampaign({ ...newCampaign, target_filter: e.target.value })}
                className="w-full px-3.5 py-2.5 bg-gray-50/70 border border-gray-200 rounded-xl text-sm focus:bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
              >
                <option value="ALL">All Active Contacts ({contacts.length})</option>
                {segmentsList.filter(s => s.name !== "All Active Customers").map(s => (
                  <option key={s.id} value={`SEGMENT:${s.id}`}>
                    {s.name} ({s.matching_contacts_count})
                  </option>
                ))}
                <option value="INACTIVE_30_DAYS">30-Day Inactive Only</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-700 tracking-wide mb-2 flex items-center justify-between">
                <span>PER-DAY MESSAGE LIMIT</span>
                <span className="text-[10px] text-gray-400 font-normal lowercase">optional</span>
              </label>
              <input
                type="number"
                min="1"
                placeholder="e.g. 500, 1000"
                value={newCampaign.per_day_limit || ""}
                onChange={(e) => setNewCampaign({ ...newCampaign, per_day_limit: e.target.value })}
                className="w-full px-3.5 py-2.5 bg-gray-50/70 border border-gray-200 rounded-xl text-sm focus:bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
              />
            </div>
          </div>

          {/* Schedule */}
          <div>
            <label className="block text-xs font-semibold text-gray-700 tracking-wide mb-2 flex items-center justify-between">
              <span className="flex items-center gap-1.5">
                <Calendar className="w-3.5 h-3.5 text-gray-400" />
                SCHEDULE BROADCAST FOR LATER
              </span>
              <span className="text-[10px] font-bold text-amber-800 bg-amber-50 px-2 py-0.5 rounded-full border border-amber-200/60">
                IST (GMT+5:30)
              </span>
            </label>
            <input
              type="datetime-local"
              value={newCampaign.scheduled_for || ""}
              onChange={(e) => setNewCampaign({ ...newCampaign, scheduled_for: e.target.value })}
              className="w-full px-3.5 py-2.5 bg-gray-50/70 border border-gray-200 rounded-xl text-sm focus:bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
            />
            {newCampaign.scheduled_for ? (
              <div className="mt-2 p-2.5 bg-amber-50/70 border border-amber-200/80 rounded-xl flex items-center gap-2 text-xs text-amber-900 font-medium">
                <Clock className="w-4 h-4 text-amber-600 shrink-0" />
                <span>
                  Scheduled Trigger:{" "}
                  <strong>
                    {formatScheduleDisplay(newCampaign.scheduled_for)?.formattedDate || newCampaign.scheduled_for}
                  </strong>
                </span>
              </div>
            ) : (
              <p className="text-[11px] text-gray-400 mt-1">Leave empty to dispatch broadcast immediately.</p>
            )}
          </div>

          {/* Test Send Section */}
          <div className="p-3.5 bg-blue-50/60 border border-blue-200/70 rounded-xl space-y-2.5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-blue-600" />
                <span className="text-xs font-bold text-blue-900">Send Test Message</span>
              </div>
              <button
                type="button"
                onClick={() => {
                  setShowTestInput(!showTestInput);
                  setTestStatus(null);
                }}
                className="text-xs font-semibold text-blue-600 hover:text-blue-800 transition"
              >
                {showTestInput ? "Hide Test" : "Test Template Before Broadcast"}
              </button>
            </div>

            {showTestInput && (
              <div className="space-y-2 pt-1 border-t border-blue-200/40">
                <p className="text-[11px] text-blue-800">
                  Send a single preview message to your phone to verify video playback, text rendering, and links.
                </p>
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    value={testPhone}
                    onChange={(e) => setTestPhone(e.target.value)}
                    placeholder="e.g. +919876543210"
                    className="flex-1 px-3 py-1.5 bg-white border border-blue-200 rounded-lg text-xs font-mono focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                  />
                  <button
                    type="button"
                    disabled={sendingTest || !testPhone.trim() || !newCampaign.template_name}
                    onClick={handleSendTestMessage}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-semibold text-xs rounded-lg transition shadow-xs"
                  >
                    {sendingTest ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        <span>Sending...</span>
                      </>
                    ) : (
                      <>
                        <Send className="w-3.5 h-3.5" />
                        <span>Send Test</span>
                      </>
                    )}
                  </button>
                </div>
                {testStatus && (
                  <div
                    className={`p-2 rounded-lg text-[11px] font-medium ${
                      testStatus.success
                        ? "bg-emerald-100/90 text-emerald-900 border border-emerald-300"
                        : "bg-red-100/90 text-red-900 border border-red-300"
                    }`}
                  >
                    {testStatus.message}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Footer Actions */}
          <div className="pt-5 border-t border-gray-100 flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              className="px-5 py-2.5 rounded-xl border border-gray-200 text-sm font-semibold text-gray-600 hover:bg-gray-50 transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="flex items-center gap-2 bg-[#25D366] hover:bg-[#1EBE5D] text-white px-6 py-2.5 rounded-xl font-semibold text-sm shadow-md shadow-emerald-500/20 transition transform active:scale-95"
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
