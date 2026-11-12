import React, { useState, useEffect } from "react";
import {
  Sparkles,
  Plus,
  Trash2,
  Edit2,
  Save,
  X,
  MessageSquare,
  CheckCircle,
  AlertCircle
} from "lucide-react";
import axios from "axios";
import { getStoredQuickReplies, saveStoredQuickReplies } from "../utils/quickRepliesStorage";

export default function QuickRepliesPage({ token, onQuickRepliesUpdated }) {
  const [quickReplies, setQuickReplies] = useState(() => getStoredQuickReplies());
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [toastMsg, setToastMsg] = useState("");
  const [errorMsg, setErrorMsg] = useState("");

  // Modal / Form state
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingItem, setEditingItem] = useState(null);
  const [formTitle, setFormTitle] = useState("");
  const [formMessage, setFormMessage] = useState("");

  const fetchQuickReplies = async () => {
    try {
      if (token) {
        const res = await axios.get("/api/quick-replies", {
          headers: { Authorization: `Bearer ${token}` }
        });
        if (Array.isArray(res.data) && res.data.length > 0) {
          setQuickReplies(res.data);
          saveStoredQuickReplies(res.data);
          return;
        }
      }
    } catch (err) {
      // Server returned 404/error, seamlessly fallback to localStorage
    }
    const local = getStoredQuickReplies();
    setQuickReplies(local);
  };

  useEffect(() => {
    fetchQuickReplies();
  }, [token]);

  const showToast = (msg) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(""), 4000);
  };

  const handleOpenAdd = () => {
    setEditingItem(null);
    setFormTitle("");
    setFormMessage("");
    setIsModalOpen(true);
  };

  const handleOpenEdit = (item) => {
    setEditingItem(item);
    setFormTitle(item.title || "");
    setFormMessage(item.message || "");
    setIsModalOpen(true);
  };

  const handleSaveForm = async (e) => {
    e.preventDefault();
    if (!formMessage.trim()) {
      alert("Please enter a reply message.");
      return;
    }

    const titleToUse = formTitle.trim() || formMessage.trim().slice(0, 30);
    let updatedList = [];

    if (editingItem) {
      updatedList = quickReplies.map((qr) =>
        qr.id === editingItem.id
          ? { ...qr, title: titleToUse, message: formMessage.trim() }
          : qr
      );
    } else {
      const newEntry = {
        id: Date.now(),
        title: titleToUse,
        message: formMessage.trim()
      };
      updatedList = [...quickReplies, newEntry];
    }

    setSaving(true);
    // 1. Immediately persist locally
    saveStoredQuickReplies(updatedList);
    setQuickReplies(updatedList);

    // 2. Silently attempt server sync if backend route available
    try {
      if (token) {
        await axios.put("/api/quick-replies", updatedList, {
          headers: { Authorization: `Bearer ${token}` }
        });
      }
    } catch (err) {
      // Saved locally regardless
    } finally {
      setSaving(false);
      setIsModalOpen(false);
      showToast(editingItem ? "Quick reply updated successfully!" : "Quick reply added successfully!");
      if (onQuickRepliesUpdated) onQuickRepliesUpdated(updatedList);
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Are you sure you want to delete this quick reply?")) return;
    const updatedList = quickReplies.filter((qr) => qr.id !== id);
    setSaving(true);
    // 1. Immediately persist locally
    saveStoredQuickReplies(updatedList);
    setQuickReplies(updatedList);

    // 2. Silently attempt server sync
    try {
      if (token) {
        await axios.put("/api/quick-replies", updatedList, {
          headers: { Authorization: `Bearer ${token}` }
        });
      }
    } catch (err) {
      // Saved locally regardless
    } finally {
      setSaving(false);
      showToast("Quick reply removed.");
      if (onQuickRepliesUpdated) onQuickRepliesUpdated(updatedList);
    }
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-6 rounded-2xl border border-gray-200 shadow-xs">
        <div>
          <div className="flex items-center gap-2">
            <span className="p-2 rounded-xl bg-emerald-50 text-[#25D366]">
              <Sparkles className="w-5 h-5 text-[#25D366]" />
            </span>
            <h2 className="text-xl font-bold text-gray-900">Quick Replies Management</h2>
          </div>
          <p className="text-xs text-gray-500 mt-1">
            Create, edit, and organize canned response presets for your Live Chat team.
          </p>
        </div>

        <button
          onClick={handleOpenAdd}
          className="bg-[#25D366] hover:bg-[#1EBE5D] text-white px-4 py-2.5 rounded-xl font-bold text-xs shadow-xs inline-flex items-center gap-2 transition cursor-pointer self-start sm:self-auto"
        >
          <Plus className="w-4 h-4" /> Add Quick Reply
        </button>
      </div>

      {toastMsg && (
        <div className="bg-emerald-50 border border-emerald-200 text-emerald-800 px-4 py-3 rounded-xl text-xs font-semibold flex items-center gap-2 shadow-xs">
          <CheckCircle className="w-4 h-4 text-emerald-600" />
          <span>{toastMsg}</span>
        </div>
      )}

      {errorMsg && (
        <div className="bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded-xl text-xs font-semibold flex items-center gap-2 shadow-xs">
          <AlertCircle className="w-4 h-4 text-red-600" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Grid of Quick Replies */}
      {loading ? (
        <div className="p-12 text-center text-gray-400 text-sm">Loading quick replies...</div>
      ) : quickReplies.length === 0 ? (
        <div className="bg-white p-12 rounded-2xl border border-gray-200 text-center">
          <MessageSquare className="w-12 h-12 text-gray-300 mx-auto mb-3" />
          <h3 className="text-sm font-bold text-gray-800">No Quick Replies Found</h3>
          <p className="text-xs text-gray-500 mt-1 mb-4">
            Add reusable snippets so agents can answer inquiries with a single click.
          </p>
          <button
            onClick={handleOpenAdd}
            className="bg-[#25D366] hover:bg-[#1EBE5D] text-white px-4 py-2 rounded-xl font-bold text-xs inline-flex items-center gap-2 transition"
          >
            <Plus className="w-4 h-4" /> Add First Reply
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {quickReplies.map((qr, index) => (
            <div
              key={qr.id || index}
              className="bg-white p-5 rounded-2xl border border-gray-200 hover:border-emerald-300 transition shadow-xs flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold text-gray-900 bg-gray-100 px-2.5 py-0.5 rounded-full">
                    {qr.title || `Quick Reply #${index + 1}`}
                  </span>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => handleOpenEdit(qr)}
                      className="p-1.5 text-gray-400 hover:text-emerald-600 hover:bg-emerald-50 rounded-lg transition"
                      title="Edit"
                    >
                      <Edit2 className="w-3.5 h-3.5" />
                    </button>
                    <button
                      onClick={() => handleDelete(qr.id)}
                      className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition"
                      title="Delete"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
                <p className="text-xs text-gray-700 whitespace-pre-wrap leading-relaxed mt-2 font-mono bg-gray-50/70 p-3 rounded-xl border border-gray-100">
                  {qr.message}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add / Edit Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-xs">
          <div className="bg-white rounded-2xl border border-gray-200 shadow-2xl max-w-lg w-full p-6 animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between pb-4 border-b border-gray-100">
              <h3 className="text-sm font-bold text-gray-900 flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-[#F5A623]" />
                {editingItem ? "Edit Quick Reply" : "New Quick Reply"}
              </h3>
              <button
                onClick={() => setIsModalOpen(false)}
                className="p-1 text-gray-400 hover:text-gray-700 rounded-lg"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleSaveForm} className="space-y-4 mt-4">
              <div>
                <label className="block text-xs font-bold text-gray-700 mb-1">
                  Preset Title / Label (Optional)
                </label>
                <input
                  type="text"
                  placeholder="e.g. Website Link, Order Tracking, Welcome"
                  value={formTitle}
                  onChange={(e) => setFormTitle(e.target.value)}
                  className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#25D366]"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-gray-700 mb-1">
                  Message Content <span className="text-red-500">*</span>
                </label>
                <textarea
                  rows={4}
                  required
                  placeholder="Type the message to send to customers..."
                  value={formMessage}
                  onChange={(e) => setFormMessage(e.target.value)}
                  className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#25D366] leading-relaxed resize-none"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-gray-100">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 text-xs font-medium text-gray-600 hover:bg-gray-100 rounded-xl transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="px-4 py-2 bg-[#25D366] hover:bg-[#1EBE5D] disabled:opacity-50 text-white rounded-xl text-xs font-bold shadow-xs transition flex items-center gap-1.5"
                >
                  <Save className="w-3.5 h-3.5" />
                  {saving ? "Saving..." : "Save Quick Reply"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
