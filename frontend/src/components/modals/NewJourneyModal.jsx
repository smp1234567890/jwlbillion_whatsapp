import React from "react";
import {
  GitBranch,
  ArrowRight,
  ShoppingCart,
  Clock,
  CloudRain,
  UserPlus,
  Package,
  Sparkles,
  Tag
} from "lucide-react";

export default function NewJourneyModal({
  isOpen,
  onClose,
  newJourneyForm,
  setNewJourneyForm,
  onConfirm
}) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-2xl max-w-xl w-full p-6 shadow-2xl border border-gray-200 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between pb-4 border-b border-gray-100">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-emerald-50 text-[#25D366] flex items-center justify-center font-bold">
              <GitBranch className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-bold text-lg text-gray-900 leading-tight">Create Journey Flow</h3>
              <p className="text-xs text-gray-500">Pick a starting trigger to begin building your visual automation flow</p>
            </div>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 font-bold text-xl leading-none">✕</button>
        </div>

        <form onSubmit={onConfirm} className="mt-5 space-y-4">
          <div>
            <label className="block text-xs font-bold uppercase text-gray-700 mb-1">Journey Flow Name</label>
            <input
              type="text"
              required
              placeholder="e.g. 30-Min Cart Recovery Sequence, Festive Diwali Offer"
              value={newJourneyForm.name}
              onChange={(e) => setNewJourneyForm({ ...newJourneyForm, name: e.target.value })}
              className="w-full px-3.5 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#25D366]"
            />
          </div>

          <div>
            <label className="block text-xs font-bold uppercase text-gray-700 mb-2">Select Starting Trigger Event</label>
            <div className="space-y-2">
              {[
                {
                  id: "ABANDONED_CART",
                  title: "Abandoned Cart",
                  desc: "Triggers when an abandoned cart webhook event is received from your e-commerce store.",
                  icon: ShoppingCart,
                  color: "text-amber-600 bg-amber-50 border-amber-200"
                },
                {
                  id: "INACTIVE_WINBACK",
                  title: "Customer Inactive Winback",
                  desc: "Target past customers who have had no order activity for a custom number of days.",
                  icon: Clock,
                  color: "text-blue-600 bg-blue-50 border-blue-200"
                },
                {
                  id: "WEATHER_TRIGGER",
                  title: "Weather Trigger (Rain/Winter Snack)",
                  desc: "Send weather-targeted snack cravings (e.g. Rainy day hot Jewelry in Ahmedabad).",
                  icon: CloudRain,
                  color: "text-sky-600 bg-sky-50 border-sky-200"
                },
                {
                  id: "NEW_CUSTOMER_WELCOME",
                  title: "New Customer Welcome & Double Opt-In",
                  desc: "Send a compliant double opt-in confirmation greeting upon signup, then deliver a welcome discount once confirmed.",
                  icon: UserPlus,
                  color: "text-emerald-600 bg-emerald-50 border-emerald-200"
                },
                {
                  id: "BACK_IN_STOCK",
                  title: "Back In Stock Alert",
                  desc: "Alert hungry customers the instant a bestselling snack item is restocked.",
                  icon: Package,
                  color: "text-purple-600 bg-purple-50 border-purple-200"
                },
                {
                  id: "ORDER_COMPLETED",
                  title: "Post-Purchase / Order Completed",
                  desc: "Triggers right after an order is placed/delivered for feedback or cross-sell snacks.",
                  icon: Package,
                  color: "text-indigo-600 bg-indigo-50 border-indigo-200"
                },
                {
                  id: "FESTIVAL_OFFER",
                  title: "Festival & Promotional Event",
                  desc: "Triggers an outbound promotional campaign or seasonal festive blast.",
                  icon: Sparkles,
                  color: "text-pink-600 bg-pink-50 border-pink-200"
                },
                {
                  id: "CONTACT_TAGGED",
                  title: "Contact Tagged / VIP Milestone",
                  desc: "Triggers when a customer receives a specific tag or joins VIP segment.",
                  icon: Tag,
                  color: "text-teal-600 bg-teal-50 border-teal-200"
                }
              ].map((trig) => {
                const isSelected = (newJourneyForm.trigger_type || "ABANDONED_CART") === trig.id;
                const IconComp = trig.icon;
                return (
                  <div
                    key={trig.id}
                    onClick={() => setNewJourneyForm({ ...newJourneyForm, trigger_type: trig.id })}
                    className={`cursor-pointer p-3 rounded-xl border transition-all flex items-center gap-3.5 ${
                      isSelected
                        ? "border-[#25D366] bg-emerald-50/40 ring-2 ring-[#25D366]/20 shadow-xs"
                        : "border-gray-200 hover:border-gray-300 hover:bg-gray-50/70"
                    }`}
                  >
                    <div className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 border ${trig.color}`}>
                      <IconComp className="w-5 h-5" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <div className="text-sm font-bold text-gray-900">{trig.title}</div>
                        {isSelected && (
                          <span className="text-[11px] font-bold text-emerald-700 bg-emerald-100 px-2 py-0.5 rounded-full">
                            Selected
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-gray-500 mt-0.5">{trig.desc}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* 1. Abandoned Cart Options */}
          {newJourneyForm.trigger_type === "ABANDONED_CART" && (
            <div className="bg-amber-50/50 border border-amber-200/80 rounded-xl p-3.5 space-y-2">
              <div className="flex items-center justify-between">
                <label className="block text-xs font-bold uppercase text-amber-900">
                  Minimum Cart Amount Filter (₹)
                </label>
                <span className="text-[11px] text-amber-700 font-semibold">
                  {Number(newJourneyForm.min_cart_value) > 0
                    ? `Only carts ≥ ₹${newJourneyForm.min_cart_value}`
                    : "All abandoned carts (₹0+)"}
                </span>
              </div>
              <div className="relative flex items-center">
                <span className="absolute left-3.5 text-amber-700 font-bold text-sm pointer-events-none select-none">₹</span>
                <input
                  type="number"
                  min="0"
                  value={newJourneyForm.min_cart_value !== undefined ? newJourneyForm.min_cart_value : 0}
                  onChange={(e) =>
                    setNewJourneyForm({
                      ...newJourneyForm,
                      min_cart_value: e.target.value === "" ? 0 : Number(e.target.value)
                    })
                  }
                  placeholder="0 (Trigger for all abandoned carts)"
                  className="w-full pl-9 pr-3 py-2 border border-amber-300 rounded-lg text-sm bg-white font-mono font-bold text-gray-900 focus:outline-none focus:ring-2 focus:ring-amber-500"
                />
              </div>
              <div className="flex gap-1.5 pt-1">
                {[0, 299, 499, 999, 1499].map((val) => (
                  <button
                    key={val}
                    type="button"
                    onClick={() => setNewJourneyForm({ ...newJourneyForm, min_cart_value: val })}
                    className={`px-2 py-1 rounded-md border text-[10px] font-bold transition ${
                      (Number(newJourneyForm.min_cart_value) || 0) === val
                        ? "bg-amber-500 text-white border-amber-600 shadow-xs"
                        : "bg-white text-gray-700 border-gray-200 hover:bg-amber-100"
                    }`}
                  >
                    {val === 0 ? "All (₹0)" : `≥ ₹${val}`}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* 2. Customer Inactive Winback Options */}
          {newJourneyForm.trigger_type === "INACTIVE_WINBACK" && (
            <div className="bg-blue-50/60 border border-blue-200/80 rounded-xl p-3.5 space-y-2.5">
              <div className="flex items-center justify-between">
                <label className="block text-xs font-bold uppercase text-blue-950">
                  Inactivity Threshold (Days without Order)
                </label>
                <span className="text-[11px] text-blue-700 font-semibold font-mono">
                  Target: ≥ {newJourneyForm.inactive_days || 30} days inactive
                </span>
              </div>
              <div className="relative flex items-center">
                <input
                  type="number"
                  min="1"
                  value={newJourneyForm.inactive_days !== undefined ? newJourneyForm.inactive_days : 30}
                  onChange={(e) =>
                    setNewJourneyForm({
                      ...newJourneyForm,
                      inactive_days: e.target.value === "" ? 1 : Math.max(1, Number(e.target.value))
                    })
                  }
                  placeholder="e.g. 30, 45, 60, 90"
                  className="w-full px-3.5 py-2 border border-blue-300 rounded-lg text-sm bg-white font-mono font-bold text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <span className="absolute right-3.5 text-xs text-gray-400 font-semibold pointer-events-none select-none">Days</span>
              </div>
              <p className="text-[11px] text-gray-500">
                Customers who haven't placed an order in at least {newJourneyForm.inactive_days || 30} days will be enrolled in this flow.
              </p>
              <div className="flex flex-wrap gap-1.5 pt-1">
                {[30, 45, 60, 90, 120].map((days) => (
                  <button
                    key={days}
                    type="button"
                    onClick={() => setNewJourneyForm({ ...newJourneyForm, inactive_days: days })}
                    className={`px-2.5 py-1 rounded-md border text-xs font-bold transition ${
                      (Number(newJourneyForm.inactive_days) || 30) === days
                        ? "bg-blue-600 text-white border-blue-700 shadow-xs"
                        : "bg-white text-gray-700 border-gray-200 hover:bg-blue-100"
                    }`}
                  >
                    {days} Days
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* 3. Weather Trigger Options */}
          {newJourneyForm.trigger_type === "WEATHER_TRIGGER" && (
            <div className="bg-sky-50/60 border border-sky-200/80 rounded-xl p-3.5 space-y-3">
              <div className="flex items-center justify-between">
                <label className="block text-xs font-bold uppercase text-sky-950">
                  Weather Condition & City
                </label>
                <span className="text-[11px] text-sky-700 font-semibold">Ahmedabad & Gujarat</span>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-semibold text-gray-600 mb-1">Condition</label>
                  <select
                    value={newJourneyForm.weather_condition || "RAINY"}
                    onChange={(e) => setNewJourneyForm({ ...newJourneyForm, weather_condition: e.target.value })}
                    className="w-full px-3 py-2 border border-sky-300 rounded-lg text-xs font-semibold bg-white text-gray-800"
                  >
                    <option value="RAINY">🌧️ Rainy / Monsoon</option>
                    <option value="CLOUDY">⛅ Cloudy & Overcast</option>
                    <option value="CHILLY_WINTER">❄️ Chilly Winter Morning</option>
                    <option value="HOT_SUMMER">☀️ Hot Afternoon</option>
                  </select>
                </div>
                <div>
                  <label className="block text-[11px] font-semibold text-gray-600 mb-1">Target City</label>
                  <input
                    type="text"
                    value={newJourneyForm.city || "Ahmedabad"}
                    onChange={(e) => setNewJourneyForm({ ...newJourneyForm, city: e.target.value })}
                    placeholder="e.g. Ahmedabad"
                    className="w-full px-3 py-2 border border-sky-300 rounded-lg text-xs font-semibold bg-white text-gray-800"
                  />
                </div>
              </div>
            </div>
          )}

          {/* 4. New Customer Welcome Options */}
          {newJourneyForm.trigger_type === "NEW_CUSTOMER_WELCOME" && (
            <div className="bg-emerald-50/60 border border-emerald-200/80 rounded-xl p-3.5 space-y-3">
              <div className="flex items-center gap-2 text-emerald-900 font-bold text-xs">
                <span>🛡️ Double Opt-In Flow Enabled</span>
              </div>
              <p className="text-[11px] text-emerald-700 leading-relaxed">
                Step 1 sends a friendly opt-in invitation. When the customer confirms (replies &quot;YES&quot;), marketing consent is recorded in their profile and Step 2 unlocks their welcome discount gift.
              </p>
              <div>
                <label className="block text-xs font-bold uppercase text-emerald-950 mb-1">
                  Welcome Gift Coupon Code
                </label>
                <input
                  type="text"
                  value={newJourneyForm.welcome_coupon || "WELCOME10"}
                  onChange={(e) => setNewJourneyForm({ ...newJourneyForm, welcome_coupon: e.target.value.toUpperCase() })}
                  placeholder="e.g. WELCOME10"
                  className="w-full px-3.5 py-2 border border-emerald-300 rounded-lg text-xs font-mono font-bold bg-white text-gray-900 uppercase"
                />
              </div>
            </div>
          )}

          {/* 5. Back In Stock Alert Options */}
          {newJourneyForm.trigger_type === "BACK_IN_STOCK" && (
            <div className="bg-purple-50/60 border border-purple-200/80 rounded-xl p-3.5 space-y-2">
              <label className="block text-xs font-bold uppercase text-purple-950">
                Restocked Snack Product Name
              </label>
              <input
                type="text"
                value={newJourneyForm.product_name || "Solitaire Special"}
                onChange={(e) => setNewJourneyForm({ ...newJourneyForm, product_name: e.target.value })}
                placeholder="e.g. Solitaire Special, Gold Necklace"
                className="w-full px-3.5 py-2 border border-purple-300 rounded-lg text-xs font-semibold bg-white text-gray-900"
              />
              <p className="text-[11px] text-purple-700">
                Sends automated notifications to customers who viewed or wishlisted this item.
              </p>
            </div>
          )}

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
              className="bg-[#25D366] hover:bg-[#1EBE5D] text-white px-5 py-2 rounded-lg font-semibold text-sm shadow-md flex items-center gap-2"
            >
              <span>Open Flow Builder</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
