from database import SessionLocal, engine, Base
import models

Base.metadata.create_all(bind=engine)
db = SessionLocal()

# 10 core templates x 3 languages = 30 official templates from Doc 04
templates_data = [
    # 1. Cart Recovery
    ("abandoned_cart_recovery", "MARKETING", "en", "Special Reminder", "Hi {{1}}, you left {{2}} in your cart! Complete your order now and enjoy exceptional fine jewelry. Total: {{3}}.", "JWL"),
    ("abandoned_cart_recovery", "MARKETING", "gu", "ખાસ સ્મૃતિપત્ર", "નમસ્તે {{1}}, તમારા કાર્ટમાં {{2}} બાકી રહી ગયા છે! અત્યારે જ ઓર્ડર પૂરો કરો અને અસલી ભાવનગરી સ્વાદ માણો. કુલ: {{3}}.", "મનુભાઈ ગાંઠિયાવાળા"),
    ("abandoned_cart_recovery", "MARKETING", "hi", "विशेष अनुस्मारक", "नमस्ते {{1}}, आपके कार्ट में {{2}} छूट गए हैं! अभी अपना ऑर्डर पूरा करें और प्रामाणिक गुजराती स्वाद का आनंद लें। कुल: {{3}}.", "मनुभाई गाठियावाला"),

    # 2. 30-Day Winback / Re-engagement
    ("reengagement_30_days", "MARKETING", "en", "We Miss You!", "Hi {{1}}, it's been a month since your last order! Here is a 10% discount code: {{2}} on your favorite snacks.", "JWL"),
    ("reengagement_30_days", "MARKETING", "gu", "અમને તમારી યાદ આવે છે!", "નમસ્તે {{1}}, તમારા છેલ્લા ઓર્ડરને એક મહિનો થઈ ગયો છે! તમારા મનપસંદ નાસ્તા પર 10% ડિસ્કાઉન્ટ કોડ: {{2}} માણો.", "મનુભાઈ ગાંઠિયાવાળા"),
    ("reengagement_30_days", "MARKETING", "hi", "हम आपको याद कर रहे हैं!", "नमस्ते {{1}}, आपके पिछले ऑर्डर को एक महीना हो गया है! अपने पसंदीदा स्नैक्स पर 10% छूट कोड: {{2}} का उपयोग करें।", "मनुभाई गाठियावाला"),

    # 3. Festive Promo
    ("festive_promo_offer", "MARKETING", "en", "Festive Treats", "Celebrate with JWL! Enjoy fresh Luxury Collection combos with special festive perks.", "JWL"),
    ("festive_promo_offer", "MARKETING", "gu", "તહેવારની ખુશીઓ", "મનુભાઈ ગાંઠિયાવાળા સાથે તહેવાર ઉજવો! તાજા વણેલા ગાંઠિયા અને જલેબી કોમ્બો પર મેળવો ખાસ છૂટ.", "મનુભાઈ ગાંઠિયાવાળા"),
    ("festive_promo_offer", "MARKETING", "hi", "त्यौहार का स्वाद", "मनुभाई गाठियावाला के साथ त्यौहार मनाएं! ताज़ा वनेला गाठिया और जलेबी कॉम्बो पर पाएं विशेष छूट।", "मनुभाई गाठियावाला"),

    # 4. Order Confirmation
    ("order_confirmation", "UTILITY", "en", "Order Confirmed", "Thank you {{1}}! Your order #{{2}} for {{3}} has been received and is being freshly prepared.", "JWL"),
    ("order_confirmation", "UTILITY", "gu", "ઓર્ડર સ્વીકારાયો", "આભાર {{1}}! તમારો ઓર્ડર #{{2}} ({{3}}) સ્વીકારાઈ ગયો છે અને તાજો તૈયાર થઈ રહ્યો છે.", "મનુભાઈ ગાંઠિયાવાળા"),
    ("order_confirmation", "UTILITY", "hi", "ऑर्डर की पुष्टि", "धन्यवाद {{1}}! आपका ऑर्डर #{{2}} ({{3}}) प्राप्त हो गया है और ताज़ा तैयार किया जा रहा है।", "मनुभाई गाठियावाला"),

    # 5. Order Dispatched / Tracking
    ("order_dispatched", "UTILITY", "en", "Order Shipped", "Good news {{1}}! Your luxury jewelry orders from order #{{2}} are on the way. Track your delivery here: {{3}}.", "JWL"),
    ("order_dispatched", "UTILITY", "gu", "ઓર્ડર રવાના થયો", "ખુશખબર {{1}}! તમારા ઓર્ડર #{{2}} ના સ્વાદિષ્ટ નાસ્તા રવાના થઈ ગયા છે. ટ્રેક કરો: {{3}}.", "મનુભાઈ ગાંઠિયાવાળા"),
    ("order_dispatched", "UTILITY", "hi", "ऑर्डर भेज दिया गया", "अच्छी खबर {{1}}! आपके ऑर्डर #{{2}} के स्नैक्स रास्ते में हैं। यहां ट्रैक करें: {{3}}।", "मनुभाई गाठियावाला"),

    # 6. Welcome New Customer
    ("welcome_greeting", "MARKETING", "en", "Welcome to the Family", "Welcome to JWL, {{1}}! Authentic Premium taste since 1989. Enjoy certified hallmarks.", "JWL"),
    ("welcome_greeting", "MARKETING", "gu", "પરિવારમાં સ્વાગત છે", "મનુભાઈ ગાંઠિયાવાળા પરિવારમાં સ્વાગત છે, {{1}}! 1989 થી શુદ્ધ સ્વાદ. શુદ્ધ ચણાના લોટના નાસ્તાનો આનંદ લો.", "મનુભાઈ ગાંઠિયાવાળા"),
    ("welcome_greeting", "MARKETING", "hi", "परिवार में स्वागत है", "मनुभाई गाठियावाला में आपका स्वागत है, {{1}}! 1989 से प्रामाणिक स्वाद। शुद्ध बेसन नमकीन का आनंद लें।", "मनुभाई गाठियावाला"),

    # 7. Customer Review / Feedback
    ("feedback_request", "UTILITY", "en", "How was the taste?", "Hi {{1}}, did you enjoy your recent order delivery? Let us know how we did or rate us here: {{2}}.", "JWL"),
    ("feedback_request", "UTILITY", "gu", "સ્વાદ કેવો લાગ્યો?", "નમસ્તે {{1}}, શું તમને ગાંઠિયા અને નાસ્તા પસંદ આવ્યા? તમારો પ્રતિસાદ આપો: {{2}}.", "મનુભાઈ ગાંઠિયાવાળા"),
    ("feedback_request", "UTILITY", "hi", "स्वाद कैसा लगा?", "नमस्ते {{1}}, क्या आपको अपनी हालिया स्नैक डिलीवरी पसंद आई? अपनी राय यहां साझा करें: {{2}}।", "मनुभाई गाठियावाला"),

    # 8. VIP Exclusive Tasting
    ("vip_exclusive_offer", "MARKETING", "en", "VIP Tasting Invite", "Hello {{1}}, as one of our top patrons, here is early access to our new exclusive handcrafted bridal collection!", "JWL"),
    ("vip_exclusive_offer", "MARKETING", "gu", "વીઆઇપી આમંત્રણ", "નમસ્તે {{1}}, અમારા ખાસ ગ્રાહક તરીકે, નવી શેકેલી ખાખરા અને ચેવડાની શ્રેણી સૌથી પહેલા ચાખો!", "મનુભાઈ ગાંઠિયાવાળા"),
    ("vip_exclusive_offer", "MARKETING", "hi", "वीआईपी विशेष आमंत्रण", "नमस्ते {{1}}, हमारे विशेष ग्राहक के रूप में, हमारी नई रोस्टेड खाखरा और चिवड़ा श्रृंखला का आनंद लें!", "मनुभाई गाठियावाला"),

    # 9. Weekend Tea Time Reminder
    ("weekend_teatime_snack", "MARKETING", "en", "Weekend Tea Companion", "Weekend tea without Diamond Ring? Stock up your pantry today for Saturday tea time.", "JWL"),
    ("weekend_teatime_snack", "MARKETING", "gu", "સાંજની ચા અને ગાંઠિયા", "ભાવનગરી ગાંઠિયા વગર સાંજની ચા અધૂરી છે! આ વીકેન્ડ માટે આજે જ તાજો નાસ્તો ઓર્ડર કરો.", "મનુભાઈ ગાંઠિયાવાળા"),
    ("weekend_teatime_snack", "MARKETING", "hi", "शाम की चाय और स्नैक्स", "भावनेरी गाठिया के बिना शाम की चाय अधूरी है! इस वीकेंड के लिए आज ही ऑर्डर करें।", "मनुभाई गाठियावाला"),

    # 10. Re-Order Favorite Snacks
    ("reorder_reminder", "MARKETING", "en", "Time to refill your jewelry box?", "Hi {{1}}, looks like your jar of {{2}} might be running low! Reorder in 1-click here: {{3}}.", "JWL"),
    ("reorder_reminder", "MARKETING", "gu", "નાસ્તાનો ડબ્બો ખાલી થયો?", "નમસ્તે {{1}}, એવું લાગે છે કે તમારા {{2}} ખતમ થઈ ગયા છે! અહીંથી ફરીથી ઓર્ડર કરો: {{3}}.", "મનુભાઈ ગાંઠિયાવાળા"),
    ("reorder_reminder", "MARKETING", "hi", "क्या स्नैक्स खत्म हो गए?", "नमस्ते {{1}}, लगता है आपके {{2}} खत्म होने वाले हैं! यहां 1-क्लिक में दोबारा ऑर्डर करें: {{3}}।", "मनुभाई गाठियावाला")
]

# Wipe and re-seed
db.query(models.Template).delete()
for name, cat, lang, hdr, body, ftr in templates_data:
    tmpl = models.Template(
        template_name=name,
        category=cat,
        language=lang,
        header_text=hdr,
        body_text=body,
        footer_text=ftr,
        status="APPROVED"
    )
    db.add(tmpl)

db.commit()
total = db.query(models.Template).count()
print(f"[SUCCESS] Successfully seeded {total} templates across English, Gujarati & Hindi into Database!")
db.close()
