// Local storage helper for quick replies with fallback to defaults
const STORAGE_KEY = "jwlbillion_quick_replies_custom";

export const DEFAULT_QUICK_REPLIES = [
  { id: 1, title: "Welcome & Website", message: "Hello! Welcome to JWL Billion. How can we assist you today?\nVisit our website: https://jwlbillion.com/" },
  { id: 2, title: "Order Processing", message: "Your order has been confirmed and is being processed for dispatch." },
  { id: 3, title: "Representative Connect", message: "Thank you for reaching out! A representative will connect with you shortly." },
  { id: 4, title: "Welcome Discount", message: "Here is your special discount code: WELCOME (7% OFF)" },
  { id: 5, title: "Order ID Inquiry", message: "Could you please share your Order ID so we can check the status?" }
];

export function getStoredQuickReplies() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw !== null) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) return parsed;
    }
  } catch {}
  return DEFAULT_QUICK_REPLIES;
}

export function saveStoredQuickReplies(list) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
  } catch {}
}
