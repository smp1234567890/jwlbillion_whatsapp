/**
 * Shared Column / Variable Field Mapping Options
 * Used across Template Creation and Template Mapping Modals.
 */
export const TEMPLATE_FIELD_OPTIONS = [
  {
    group: "Contact Field (CRM)",
    options: [
      { value: "contact_field|name", label: "Customer Name" },
      { value: "contact_field|phone", label: "Customer Phone" },
      { value: "contact_field|city", label: "City" },
      { value: "contact_field|total_orders", label: "Total Orders" },
      { value: "contact_field|last_order_date", label: "Last Order Date" }
    ]
  },
  {
    group: "Store Webhook Payload (Event Push)",
    options: [
      { value: "event_field|first_name", label: "First Name (e.g. Ramesh)" },
      { value: "event_field|products_summary", label: "Products Summary (e.g. Gold Necklace)" },
      { value: "event_field|amount", label: "Cart Amount (e.g. ₹450)" },
      { value: "event_field|delivery_address", label: "Delivery Address" },
      { value: "cart_event|cart_url", label: "Cart Recovery URL" },
      { value: "event_field|custom", label: "Custom Webhook Field..." }
    ]
  },
  {
    group: "External Live API (On-Demand Pull)",
    options: [
      { value: "external_api|delivery_address", label: "Delivery / Shipping Address" },
      { value: "external_api|tracking_number", label: "Tracking Number / AWB" },
      { value: "external_api|order_status", label: "Live Order Status" },
      { value: "external_api|estimated_delivery", label: "Estimated Delivery Date" },
      { value: "external_api|support_contact", label: "Support Contact / Helpline" },
      { value: "external_api|custom", label: "Custom API JSON Key..." }
    ]
  },
  {
    group: "Coupon (CRM)",
    options: [
      { value: "coupon|code", label: "Coupon Code" },
      { value: "coupon|discount_value", label: "Discount Value (%/₹)" },
      { value: "coupon|expires_at", label: "Coupon Expiry Date" }
    ]
  },
  {
    group: "Static Text",
    options: [
      { value: "static|", label: "Custom static text..." }
    ]
  }
];
