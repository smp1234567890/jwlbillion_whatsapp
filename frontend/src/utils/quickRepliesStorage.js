// Local storage helper for quick replies with fallback to defaults
const STORAGE_KEY = "jwlbillion_quick_replies_custom";

export const DEFAULT_QUICK_REPLIES = [
  {
    id: 1,
    title: "1. Meta Ad Hook (General)",
    message: "Hey! Welcome to JWL Billion 😊 Thanks for checking out our collection!\n\nAap kuch specific jewellery dekh rahe hain ya bas collection explore kar rahe hain?"
  },
  {
    id: 2,
    title: "1. Meta Ad Hook (Product)",
    message: "Hey! 😊 Welcome to JWL Billion.\n\nAapko ye design pasand aaya tha na? Aapko iske baare mein details chahiye ya isi type ke kuch aur designs bhi dekhna chahenge?"
  },
  {
    id: 3,
    title: "2. Need: For Self (Daily/Party)",
    message: "Achha! Aap apne liye dekh rahe hain. 😊\n\nDaily wear ke liye chahiye ya parties aur special occasions ke liye?"
  },
  {
    id: 4,
    title: "2. Need: Gift Recipient",
    message: "Oh, that's lovely! 😊 Kiske liye gift dekh rahe hain — Mother, sister, wife, girlfriend ya kisi friend ke liye?\n\nUnhe usually simple jewellery pasand hai ya thode statement designs?"
  },
  {
    id: 5,
    title: "3. Direct Price & Range",
    message: "Is design ka price ₹[Price] hai. 😊\n\nHamare paas ₹300 se ₹2,000 tak ke designs hain. Aap chahein toh main aapko isi range mein aur options bhi dikha sakti hoon."
  },
  {
    id: 6,
    title: "4. Show 3 Designs",
    message: "Aapki preference ke according maine kuch designs select kiye hain. Ek baar dekhiye, inmein se kaunsa aapko sabse achha lagta hai? 😊"
  },
  {
    id: 7,
    title: "5. Objection: Color Fade?",
    message: "Aapka poochna bilkul sahi hai! 😊 Ismein multi-layer gold plating aur anti-tarnish protective coating use hui hai. Proper care (perfumes/water se door rakhne) se shine lambe time tak maintain rehti hai. Hum care guide bhi share karte hain. ❤️"
  },
  {
    id: 8,
    title: "5. Objection: Expensive / Budget",
    message: "Haan ji, samajh sakti hoon. 😊 Aap chahein toh main isi type ke kuch designs thode lower price mein dikha sakti hoon. Aap kis range (e.g. ₹500–₹800) mein comfortable rahenge?"
  },
  {
    id: 9,
    title: "5. Objection: Online Trust & COD",
    message: "Haan ji, samajh sakti hoon, online shopping mein trust important hai. Hamare yahan 100% Cash on Delivery (COD) available hai — parcel haath mein aane par hi pay karna hai, plus 7 days easy exchange policy bhi hai! ❤️"
  },
  {
    id: 10,
    title: "5. Objection: Soch Ke Batati Hoon",
    message: "Haan ji, bilkul! Aap aaram se decide kijiye. 😊 Bas ek cheez bata dijiye, aapko design ko lekar doubt hai ya price ko lekar? Agar main kuch help kar sakun toh zaroor bataiyega."
  },
  {
    id: 11,
    title: "6. Close & In-Chat COD",
    message: "Achha choice hai! 😊 Ye wala aapke liye final karein? Ji, Cash on Delivery (COD) available hai!\n\nAap please ye details share kar dijiye:\n• Name:\n• Mobile Number:\n• Full Address:\n• City, State & Pincode:\n\nDetails milte hi main aapka order confirm karwa deti hoon! ❤️"
  },
  {
    id: 12,
    title: "7. Follow-up (Next Day)",
    message: "Hey! 😊 Kal jo designs share kiye the, unhe dekh paaye aap? Unmein se koi pasand aaya ya main kuch aur options dikhaun?"
  }
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
