import React from "react";
import { UserPlus, Edit2 } from "lucide-react";

export default function ContactModal({
  isOpen,
  onClose,
  editingContactId,
  contactForm,
  setContactForm,
  contactSaving,
  onSave
}) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-gray-200">
        <div className="flex items-center justify-between pb-4 border-b border-gray-100">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center font-bold">
              {editingContactId ? <Edit2 className="w-4 h-4" /> : <UserPlus className="w-4 h-4" />}
            </div>
            <div>
              <h3 className="font-bold text-base text-gray-900">
                {editingContactId ? "Edit Customer Contact" : "Add New Customer Contact"}
              </h3>
              <p className="text-xs text-gray-500">
                {editingContactId ? "Update customer profile, order history, and tags" : "Add a single verified WhatsApp number"}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 font-bold text-xl"
          >
            ✕
          </button>
        </div>

        <form onSubmit={onSave} className="mt-5 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-bold uppercase text-gray-700 mb-1">
                Phone Number <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                required
                placeholder="+919876543210"
                value={contactForm.phone}
                onChange={(e) => setContactForm({ ...contactForm, phone: e.target.value })}
                className="w-full px-3.5 py-2 border border-gray-300 rounded-lg text-xs font-mono focus:outline-none focus:ring-2 focus:ring-[#25D366]"
              />
              <span className="text-[10px] text-gray-400">Include country code (+91, +1, etc.)</span>
            </div>

            <div>
              <label className="block text-xs font-bold uppercase text-gray-700 mb-1">Full Name</label>
              <input
                type="text"
                placeholder="e.g. Rutvij Dhameliya"
                value={contactForm.name}
                onChange={(e) => setContactForm({ ...contactForm, name: e.target.value })}
                className="w-full px-3.5 py-2 border border-gray-300 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-[#25D366]"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-bold uppercase text-gray-700 mb-1">Email Address</label>
              <input
                type="email"
                placeholder="customer@example.com"
                value={contactForm.email}
                onChange={(e) => setContactForm({ ...contactForm, email: e.target.value })}
                className="w-full px-3.5 py-2 border border-gray-300 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-[#25D366]"
              />
            </div>

            <div>
              <label className="block text-xs font-bold uppercase text-gray-700 mb-1">City</label>
              <input
                type="text"
                placeholder="e.g. Surat / Ahmedabad"
                value={contactForm.city}
                onChange={(e) => setContactForm({ ...contactForm, city: e.target.value })}
                className="w-full px-3.5 py-2 border border-gray-300 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-[#25D366]"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-bold uppercase text-gray-700 mb-1">
              Tags <span className="text-[11px] text-gray-400 font-normal">(comma-separated)</span>
            </label>
            <input
              type="text"
              placeholder="VIP, Wholesale, Fafda Lover, Regular"
              value={contactForm.tags}
              onChange={(e) => setContactForm({ ...contactForm, tags: e.target.value })}
              className="w-full px-3.5 py-2 border border-gray-300 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-[#25D366]"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-bold uppercase text-gray-700 mb-1">Total Orders</label>
              <input
                type="number"
                min="0"
                value={contactForm.total_orders}
                onChange={(e) => setContactForm({ ...contactForm, total_orders: e.target.value })}
                className="w-full px-3.5 py-2 border border-gray-300 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-[#25D366]"
              />
            </div>

            <div>
              <label className="block text-xs font-bold uppercase text-gray-700 mb-1">Last Order Date</label>
              <input
                type="date"
                value={contactForm.last_order_date}
                onChange={(e) => setContactForm({ ...contactForm, last_order_date: e.target.value })}
                className="w-full px-3.5 py-2 border border-gray-300 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-[#25D366]"
              />
            </div>
          </div>

          {contactForm.custom_attributes && Object.keys(contactForm.custom_attributes).length > 0 && (
            <div className="bg-blue-50/50 p-3 rounded-xl border border-blue-100">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold uppercase text-blue-900">Synced Custom Columns & Attributes</span>
                <span className="text-[10px] bg-blue-100 text-blue-800 px-2 py-0.5 rounded-full font-bold">
                  {Object.keys(contactForm.custom_attributes).length} fields
                </span>
              </div>
              <div className="grid grid-cols-2 gap-2 max-h-36 overflow-y-auto pr-1">
                {Object.entries(contactForm.custom_attributes).map(([key, val]) => (
                  <div key={key} className="bg-white p-2 rounded-lg border border-blue-100 text-xs shadow-2xs">
                    <div className="text-[10px] font-bold text-gray-400 uppercase truncate" title={key}>{key}</div>
                    <div className="text-gray-900 font-semibold truncate mt-0.5" title={typeof val === "object" ? JSON.stringify(val) : String(val)}>
                      {typeof val === "object" ? JSON.stringify(val) : String(val)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="pt-3 border-t border-gray-100 flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-gray-300 rounded-lg text-xs font-semibold text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={contactSaving || !contactForm.phone.trim()}
              className="bg-[#25D366] hover:bg-[#1EBE5D] disabled:opacity-50 text-white px-5 py-2 rounded-lg font-semibold text-xs shadow-md flex items-center gap-1.5"
            >
              {contactSaving ? "Saving..." : editingContactId ? "Update Contact" : "Save Contact"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
