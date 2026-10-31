import React, { useState, useMemo } from "react";
import {
  X,
  Search,
  Send,
  Loader2,
  CheckCircle,
  AlertCircle,
  User,
  Phone,
  FileText,
  Video,
  Image as ImageIcon
} from "lucide-react";
import api from "../../api";

export default function TemplateTestModal({
  isOpen,
  onClose,
  template,
  contacts = []
}) {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedContact, setSelectedContact] = useState(null);
  const [customPhone, setCustomPhone] = useState("");
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState(null);

  // Filter contacts by search query (always call hooks unconditionally)
  const filteredContacts = useMemo(() => {
    if (!isOpen || !template) return [];
    if (!searchQuery.trim()) return contacts.slice(0, 10);
    const q = searchQuery.toLowerCase().trim();
    return contacts.filter(
      (c) =>
        (c.name && c.name.toLowerCase().includes(q)) ||
        (c.phone && c.phone.includes(q)) ||
        (c.city && c.city.toLowerCase().includes(q))
    ).slice(0, 15);
  }, [contacts, searchQuery, isOpen, template]);

  if (!isOpen || !template) return null;

  const activePhone = selectedContact ? selectedContact.phone : customPhone.trim();

  const handleSendTest = async () => {
    if (!activePhone) {
      alert("Please select a contact or enter a valid WhatsApp phone number.");
      return;
    }

    setSending(true);
    setResult(null);

    try {
      const payload = {
        template_name: template.template_name,
        language: template.language || "en_IN",
        phone: activePhone
      };

      const res = await api.post("/api/campaigns/test-send", payload);
      setResult({
        status: "success",
        message: res.data.message || `Test message dispatched to ${activePhone} successfully!`
      });
    } catch (err) {
      const errorMsg =
        err.response?.data?.detail ||
        err.response?.data?.message ||
        err.message ||
        "Failed to send test message.";
      setResult({
        status: "error",
        message: errorMsg
      });
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-150">
      <div className="bg-white rounded-2xl shadow-2xl border border-gray-100 w-full max-w-lg overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="px-6 py-4 bg-gray-50/80 border-b border-gray-200 flex items-center justify-between">
          <div>
            <h3 className="font-bold text-gray-900 text-base flex items-center gap-2">
              <Send className="w-4 h-4 text-[#25D366]" />
              Test Send Template
            </h3>
            <p className="text-xs text-gray-500 mt-0.5">
              Send a real-time WhatsApp preview to a single contact
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-200/60 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-5">
          {/* Template Info Card */}
          <div className="p-3.5 bg-blue-50/60 border border-blue-100 rounded-xl">
            <div className="flex items-center justify-between">
              <span className="font-mono font-bold text-blue-900 text-xs">
                {template.template_name}
              </span>
              <span className="text-[10px] uppercase font-bold bg-blue-200/70 text-blue-800 px-2 py-0.5 rounded">
                {template.language}
              </span>
            </div>
            {template.header_type && template.header_type !== "NONE" && (
              <div className="mt-1.5 flex items-center gap-1.5 text-[11px] text-blue-700 font-medium">
                {template.header_type === "VIDEO" && <Video className="w-3.5 h-3.5 text-blue-600" />}
                {template.header_type === "IMAGE" && <ImageIcon className="w-3.5 h-3.5 text-blue-600" />}
                {template.header_type === "DOCUMENT" && <FileText className="w-3.5 h-3.5 text-blue-600" />}
                Header: {template.header_type}
              </div>
            )}
            <p className="mt-2 text-xs text-gray-700 whitespace-pre-wrap line-clamp-3 bg-white/80 p-2.5 rounded-lg border border-blue-100 font-sans">
              {template.body_text}
            </p>
          </div>

          {/* Contact Search & Selection */}
          <div>
            <label className="block text-xs font-bold text-gray-700 uppercase tracking-wider mb-1.5">
              Select Recipient Contact
            </label>
            <div className="relative">
              <Search className="w-4 h-4 absolute left-3 top-2.5 text-gray-400" />
              <input
                type="text"
                placeholder="Search contact by name, phone or city..."
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  setSelectedContact(null);
                }}
                className="w-full pl-9 pr-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs text-gray-800 placeholder-gray-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#25D366]/30 focus:border-[#25D366] transition"
              />
            </div>

            {/* Contact Results List */}
            <div className="mt-2 border border-gray-100 rounded-xl max-h-40 overflow-y-auto divide-y divide-gray-50 bg-gray-50/40">
              {filteredContacts.length === 0 ? (
                <div className="p-3 text-center text-xs text-gray-400">
                  No contacts found matching search query.
                </div>
              ) : (
                filteredContacts.map((c) => {
                  const isSelected = selectedContact?.id === c.id || (!selectedContact && activePhone === c.phone);
                  return (
                    <div
                      key={c.id || c.phone}
                      onClick={() => {
                        setSelectedContact(c);
                        setCustomPhone(c.phone);
                      }}
                      className={`px-3 py-2 flex items-center justify-between cursor-pointer transition text-xs ${
                        isSelected
                          ? "bg-emerald-50 text-emerald-900 font-medium"
                          : "hover:bg-gray-100/70 text-gray-700"
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <div className="w-6 h-6 rounded-full bg-gray-200 flex items-center justify-center text-gray-600 text-[10px] font-bold">
                          {(c.name || "C")[0].toUpperCase()}
                        </div>
                        <div>
                          <div className="font-medium text-gray-900">{c.name || "Unnamed"}</div>
                          <div className="text-[11px] text-gray-500 font-mono">{c.phone}</div>
                        </div>
                      </div>
                      {c.city && (
                        <span className="text-[10px] text-gray-400 bg-gray-100 px-1.5 py-0.5 rounded">
                          {c.city}
                        </span>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          </div>

          {/* Or Manual Phone Number */}
          <div>
            <label className="block text-xs font-bold text-gray-700 uppercase tracking-wider mb-1.5">
              Or Enter Phone Number (E.164)
            </label>
            <div className="relative">
              <Phone className="w-4 h-4 absolute left-3 top-2.5 text-gray-400" />
              <input
                type="text"
                placeholder="+91 98765 43210"
                value={customPhone}
                onChange={(e) => {
                  setCustomPhone(e.target.value);
                  setSelectedContact(null);
                }}
                className="w-full pl-9 pr-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs font-mono text-gray-800 placeholder-gray-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#25D366]/30 focus:border-[#25D366] transition"
              />
            </div>
          </div>

          {/* Result Alert */}
          {result && (
            <div
              className={`p-3 rounded-xl border flex items-start gap-2.5 text-xs animate-in fade-in duration-200 ${
                result.status === "success"
                  ? "bg-emerald-50 border-emerald-200 text-emerald-800"
                  : "bg-red-50 border-red-200 text-red-800"
              }`}
            >
              {result.status === "success" ? (
                <CheckCircle className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
              ) : (
                <AlertCircle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
              )}
              <div className="leading-relaxed font-medium">{result.message}</div>
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="px-6 py-3.5 bg-gray-50/80 border-t border-gray-200 flex items-center justify-end gap-2.5">
          <button
            onClick={onClose}
            disabled={sending}
            className="px-4 py-2 rounded-xl text-xs font-bold text-gray-600 hover:bg-gray-200/60 transition"
          >
            Close
          </button>
          <button
            onClick={handleSendTest}
            disabled={sending || !activePhone}
            className="flex items-center gap-1.5 bg-[#25D366] hover:bg-[#1EBE5D] text-white px-5 py-2 rounded-xl text-xs font-bold shadow-md shadow-emerald-500/20 disabled:opacity-50 disabled:cursor-not-allowed transition"
          >
            {sending ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                Sending Test...
              </>
            ) : (
              <>
                <Send className="w-3.5 h-3.5" />
                Send Test Now
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

