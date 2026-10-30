import React, { useState, useEffect } from "react";
import {
  Building2,
  Phone,
  Mail,
  Globe,
  MapPin,
  CheckCircle2,
  ShieldCheck,
  Upload,
  Loader2,
  RefreshCw,
  Save,
  AlertCircle,
  ExternalLink,
  Store
} from "lucide-react";
import api from "../api";

const VERTICAL_OPTIONS = [
  { value: "RETAIL", label: "Retail & Shopping (Recommended for Jewelry)" },
  { value: "APPAREL", label: "Apparel & Accessories" },
  { value: "BEAUTY", label: "Beauty & Personal Care" },
  { value: "FOOD_BEV", label: "Restaurant / Food & Beverage" },
  { value: "GROCERY", label: "Grocery" },
  { value: "EDU", label: "Education" },
  { value: "ENTERTAIN", label: "Entertainment" },
  { value: "EVENT_PLAN", label: "Event Planning" },
  { value: "FINANCE", label: "Financial Services" },
  { value: "HOTEL", label: "Hotel & Lodging" },
  { value: "HEALTH", label: "Health & Medical" },
  { value: "NONPROFIT", label: "Non-profit" },
  { value: "PROF_SERVICES", label: "Professional Services" },
  { value: "TRAVEL", label: "Travel & Transportation" },
  { value: "AUTO", label: "Automotive" },
  { value: "OTHER", label: "Other" }
];

export default function ProfileDetailsPage() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploadingPhoto, setUploadingPhoto] = useState(false);
  const [profile, setProfile] = useState({
    verified_name: "JWL Billion",
    display_phone_number: "+91 88660 22206",
    quality_rating: "GREEN",
    code_verification_status: "VERIFIED",
    about: "",
    address: "",
    description: "",
    email: "",
    profile_picture_url: "",
    websites: [""],
    vertical: "RETAIL"
  });
  const [statusMessage, setStatusMessage] = useState({ type: "", text: "" });

  const fetchProfile = async () => {
    setLoading(true);
    setStatusMessage({ type: "", text: "" });
    try {
      const res = await api.get("/api/whatsapp/profile");
      if (res.data) {
        setProfile({
          ...res.data,
          websites: res.data.websites && res.data.websites.length > 0 ? res.data.websites : [""]
        });
      }
    } catch (err) {
      setStatusMessage({
        type: "error",
        text: err.response?.data?.detail || "Failed to load WhatsApp Business profile from Meta."
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProfile();
  }, []);

  const handleSaveProfile = async (e) => {
    e.preventDefault();
    setSaving(true);
    setStatusMessage({ type: "", text: "" });

    try {
      const payload = {
        about: profile.about,
        address: profile.address,
        description: profile.description,
        email: profile.email,
        websites: profile.websites.filter((w) => w && w.trim()),
        vertical: profile.vertical
      };

      const res = await api.post("/api/whatsapp/profile", payload);
      setStatusMessage({
        type: "success",
        text: res.data?.message || "WhatsApp Business Profile updated successfully on Meta."
      });
      setTimeout(() => setStatusMessage({ type: "", text: "" }), 6000);
    } catch (err) {
      setStatusMessage({
        type: "error",
        text: err.response?.data?.detail || "Failed to save profile changes to Meta."
      });
    } finally {
      setSaving(false);
    }
  };

  const handlePhotoUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadingPhoto(true);
    setStatusMessage({ type: "", text: "" });
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await api.post("/api/whatsapp/profile/photo", formData, {
        headers: { "Content-Type": "multipart/form-data" }
      });
      setStatusMessage({
        type: "success",
        text: res.data?.message || "Profile picture updated! It may take 1-2 minutes for WhatsApp to refresh the cached image."
      });
      fetchProfile();
    } catch (err) {
      setStatusMessage({
        type: "error",
        text: err.response?.data?.detail || "Failed to upload profile photo to Meta."
      });
    } finally {
      setUploadingPhoto(false);
    }
  };

  const handleWebsiteChange = (idx, value) => {
    const newWebsites = [...profile.websites];
    newWebsites[idx] = value;
    setProfile({ ...profile, websites: newWebsites });
  };

  const addWebsiteField = () => {
    if (profile.websites.length < 2) {
      setProfile({ ...profile, websites: [...profile.websites, ""] });
    }
  };

  const removeWebsiteField = (idx) => {
    const newWebsites = profile.websites.filter((_, i) => i !== idx);
    setProfile({ ...profile, websites: newWebsites.length > 0 ? newWebsites : [""] });
  };

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="bg-white rounded-2xl border border-gray-200/80 p-6 md:p-8 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-50 text-emerald-700 text-xs font-semibold mb-2">
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
            <span>Official Meta Cloud API Business Profile</span>
          </div>
          <h2 className="text-2xl font-bold text-gray-900 tracking-tight">WhatsApp Business Profile</h2>
          <p className="text-sm text-gray-500 mt-1">
            Manage your verified business card, description, contact channels, and address visible to customers on WhatsApp.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={fetchProfile}
            disabled={loading || saving}
            className="flex items-center gap-2 px-4 py-2 border border-gray-200 rounded-xl text-xs font-semibold text-gray-700 hover:bg-gray-50 transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            Sync from Meta
          </button>
          <button
            onClick={handleSaveProfile}
            disabled={saving || loading}
            className="flex items-center gap-2 bg-[#25D366] hover:bg-[#1EBE5D] text-white px-5 py-2 rounded-xl text-xs font-bold shadow-md shadow-emerald-500/20 transition active:scale-95 disabled:opacity-50"
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            Save Changes to WhatsApp
          </button>
        </div>
      </div>

      {statusMessage.text && (
        <div
          className={`p-4 rounded-xl border flex items-center gap-3 text-sm animate-in fade-in duration-200 ${
            statusMessage.type === "success"
              ? "bg-emerald-50 border-emerald-200 text-emerald-800"
              : "bg-red-50 border-red-200 text-red-800"
          }`}
        >
          {statusMessage.type === "success" ? (
            <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0" />
          ) : (
            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0" />
          )}
          <span>{statusMessage.text}</span>
        </div>
      )}

      {/* Main Grid: Form Left, WhatsApp Device Preview Right */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left Form: 7 cols */}
        <div className="lg:col-span-7 bg-white rounded-2xl border border-gray-200/80 p-6 md:p-8 shadow-xs space-y-6">
          <form onSubmit={handleSaveProfile} className="space-y-6">
            {/* Meta Verified Status Bar */}
            <div className="p-4 rounded-xl bg-gray-50 border border-gray-100 flex items-center justify-between">
              <div>
                <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400 block mb-0.5">
                  Verified Business Name
                </span>
                <span className="text-base font-bold text-gray-900 flex items-center gap-1.5">
                  {profile.verified_name || "JWL Billion"}
                  <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                </span>
              </div>
              <div className="text-right">
                <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400 block mb-0.5">
                  Phone Number
                </span>
                <span className="text-sm font-mono font-semibold text-gray-800">
                  {profile.display_phone_number}
                </span>
              </div>
            </div>

            {/* Profile Picture */}
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-gray-700 mb-2">
                Business Profile Picture / Logo
              </label>
              <div className="flex items-center gap-5">
                <div className="relative group">
                  <img
                    src={profile.profile_picture_url || "https://jwlbillion.com/cdn/shop/files/logo.png"}
                    alt="WhatsApp Profile"
                    className="w-20 h-20 rounded-full object-cover border-2 border-emerald-500 shadow-md bg-white"
                  />
                  {uploadingPhoto && (
                    <div className="absolute inset-0 bg-black/50 rounded-full flex items-center justify-center">
                      <Loader2 className="w-6 h-6 text-white animate-spin" />
                    </div>
                  )}
                </div>

                <div className="space-y-1">
                  <label className="cursor-pointer inline-flex items-center gap-2 px-3.5 py-1.5 rounded-lg border border-gray-300 text-xs font-semibold text-gray-700 hover:bg-gray-50 shadow-xs transition">
                    <Upload className="w-3.5 h-3.5 text-emerald-600" />
                    <span>Upload New Photo</span>
                    <input
                      type="file"
                      className="hidden"
                      accept="image/jpeg,image/png"
                      disabled={uploadingPhoto}
                      onChange={handlePhotoUpload}
                    />
                  </label>
                  <p className="text-[11px] text-gray-400">
                    Square PNG or JPG (min 192×192px). Directly updates your WhatsApp Business DP.
                  </p>
                </div>
              </div>
            </div>

            {/* About (Status Bio) */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-xs font-bold uppercase tracking-wider text-gray-700">
                  About (Short Tagline)
                </label>
                <span className="text-[10px] text-gray-400 font-mono">
                  {(profile.about || "").length}/139 characters
                </span>
              </div>
              <input
                type="text"
                maxLength={139}
                placeholder="e.g. JWL Billion • Luxury Jewelry & Lifestyle"
                value={profile.about || ""}
                onChange={(e) => setProfile({ ...profile, about: e.target.value })}
                className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
              />
              <p className="text-[11px] text-gray-400 mt-1">
                Short bio shown directly beneath your phone number in WhatsApp contacts list.
              </p>
            </div>

            {/* Description */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-xs font-bold uppercase tracking-wider text-gray-700">
                  Business Description
                </label>
                <span className="text-[10px] text-gray-400 font-mono">
                  {(profile.description || "").length}/512 characters
                </span>
              </div>
              <textarea
                rows={4}
                maxLength={512}
                placeholder="Detailed description of your store, collections, craft, and mission..."
                value={profile.description || ""}
                onChange={(e) => setProfile({ ...profile, description: e.target.value })}
                className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 resize-none leading-relaxed"
              />
            </div>

            {/* Industry Category / Vertical */}
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-gray-700 mb-1.5">
                Business Category
              </label>
              <select
                value={profile.vertical || "RETAIL"}
                onChange={(e) => setProfile({ ...profile, vertical: e.target.value })}
                className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
              >
                {VERTICAL_OPTIONS.map((v) => (
                  <option key={v.value} value={v.value}>
                    {v.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Physical Address */}
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-gray-700 mb-1.5">
                Store / Office Address
              </label>
              <input
                type="text"
                placeholder="e.g. 1st Floor, Surat Diamond Bourse, Surat, Gujarat 395007"
                value={profile.address || ""}
                onChange={(e) => setProfile({ ...profile, address: e.target.value })}
                className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
              />
            </div>

            {/* Customer Support Email */}
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-gray-700 mb-1.5">
                Support Email Address
              </label>
              <input
                type="email"
                placeholder="e.g. support@jwlbillion.com"
                value={profile.email || ""}
                onChange={(e) => setProfile({ ...profile, email: e.target.value })}
                className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 font-mono"
              />
            </div>

            {/* Websites (Up to 2) */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-xs font-bold uppercase tracking-wider text-gray-700">
                  Websites (Max 2)
                </label>
                {profile.websites.length < 2 && (
                  <button
                    type="button"
                    onClick={addWebsiteField}
                    className="text-xs font-semibold text-emerald-600 hover:text-emerald-700 hover:underline"
                  >
                    + Add Secondary Website
                  </button>
                )}
              </div>
              <div className="space-y-2">
                {profile.websites.map((url, idx) => (
                  <div key={idx} className="flex items-center gap-2">
                    <input
                      type="url"
                      placeholder="https://jwlbillion.com"
                      value={url}
                      onChange={(e) => handleWebsiteChange(idx, e.target.value)}
                      className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 font-mono"
                    />
                    {profile.websites.length > 1 && (
                      <button
                        type="button"
                        onClick={() => removeWebsiteField(idx)}
                        className="px-2.5 py-2 text-xs font-bold text-red-500 hover:bg-red-50 rounded-lg transition"
                      >
                        ✕
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>

            <div className="pt-4 border-t border-gray-100 flex justify-end">
              <button
                type="submit"
                disabled={saving || loading}
                className="flex items-center gap-2 bg-[#25D366] hover:bg-[#1EBE5D] text-white px-6 py-3 rounded-xl text-sm font-bold shadow-md shadow-emerald-500/20 transition active:scale-95 disabled:opacity-50"
              >
                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                Save Changes to WhatsApp
              </button>
            </div>
          </form>
        </div>

        {/* Right Preview: 5 cols (WhatsApp Mobile Contact Info Mockup) */}
        <div className="lg:col-span-5 sticky top-6">
          <div className="bg-white rounded-[2.5rem] border-[6px] border-gray-800 shadow-2xl overflow-hidden max-w-[340px] mx-auto">
            {/* Mobile Top Bar */}
            <div className="bg-emerald-800 text-white px-4 py-3 flex items-center justify-between text-xs font-semibold">
              <span>Contact info</span>
              <div className="flex items-center gap-3">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                <span>Meta Live</span>
              </div>
            </div>

            {/* Profile Avatar & Title */}
            <div className="p-6 text-center border-b border-gray-100 bg-gradient-to-b from-gray-50/50 to-white">
              <img
                src={profile.profile_picture_url || "https://jwlbillion.com/cdn/shop/files/logo.png"}
                alt="Profile Preview"
                className="w-24 h-24 rounded-full mx-auto object-cover border-4 border-white shadow-lg bg-white"
              />
              <h3 className="font-bold text-lg text-gray-900 mt-3 flex items-center justify-center gap-1">
                {profile.verified_name || "JWL Billion"}
                <CheckCircle2 className="w-4 h-4 text-emerald-600 fill-emerald-600 text-white" />
              </h3>
              <p className="text-xs font-mono text-gray-500 mt-0.5">{profile.display_phone_number}</p>
              <span className="inline-block mt-2 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                Official Business Account
              </span>
            </div>

            {/* Details Section */}
            <div className="p-5 space-y-4 text-xs text-gray-700 divide-y divide-gray-100">
              {/* About */}
              <div className="pt-2">
                <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider block mb-1">
                  About
                </span>
                <p className="font-medium text-gray-900">
                  {profile.about || "JWL Billion • Luxury Jewelry & Lifestyle"}
                </p>
              </div>

              {/* Description */}
              {profile.description && (
                <div className="pt-3">
                  <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider block mb-1">
                    Business Description
                  </span>
                  <p className="text-gray-600 leading-relaxed whitespace-pre-line">
                    {profile.description}
                  </p>
                </div>
              )}

              {/* Category */}
              <div className="pt-3 flex items-center gap-2.5">
                <Store className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                <span className="font-medium">
                  {VERTICAL_OPTIONS.find((v) => v.value === profile.vertical)?.label || profile.vertical}
                </span>
              </div>

              {/* Address */}
              {profile.address && (
                <div className="pt-3 flex items-start gap-2.5">
                  <MapPin className="w-4 h-4 text-emerald-600 flex-shrink-0 mt-0.5" />
                  <span className="font-medium text-gray-800 leading-relaxed">{profile.address}</span>
                </div>
              )}

              {/* Email */}
              {profile.email && (
                <div className="pt-3 flex items-center gap-2.5">
                  <Mail className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                  <span className="text-emerald-700 font-mono font-medium">{profile.email}</span>
                </div>
              )}

              {/* Websites */}
              {profile.websites.filter(Boolean).length > 0 && (
                <div className="pt-3 space-y-1.5">
                  {profile.websites.filter(Boolean).map((url, i) => (
                    <div key={i} className="flex items-center gap-2.5">
                      <Globe className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                      <a
                        href={url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-emerald-700 font-mono font-medium hover:underline flex items-center gap-1 truncate"
                      >
                        <span className="truncate">{url}</span>
                        <ExternalLink className="w-3 h-3 flex-shrink-0" />
                      </a>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Mobile Bottom Footer */}
            <div className="p-3 bg-gray-50 text-center border-t border-gray-100 text-[10px] text-gray-400">
              Live WhatsApp Customer Card View
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

