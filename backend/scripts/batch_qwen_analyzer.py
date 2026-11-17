"""
Background Batch Qwen Analysis Script
Iterates through active replied leads since 2026-11-05 and classifies them with Qwen 2.5:3B,
caching the AI results into contact.custom_attributes['qwen_analysis'].
"""
import sys
import os
import time
import logging

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal
import models
from services.lead_intent_service import classify_intent_with_qwen
from sqlalchemy.orm.attributes import flag_modified
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("qwen_batch_analyzer")


def run_batch_analysis(limit: int = 250, force_reanalyze: bool = False):
    db = SessionLocal()
    try:
        from sqlalchemy import text
        # Find all leads who replied since Nov 05, 2026
        query = text("""
            SELECT DISTINCT cm.customer_phone
            FROM chat_messages cm
            WHERE cm.sender_type = 'CUSTOMER' AND cm.created_at >= '2026-11-05'
            ORDER BY cm.customer_phone
        """)
        phones = [r[0] for r in db.execute(query).fetchall()]
        logger.info(f"Found {len(phones)} candidate leads for Qwen analysis.")

        processed = 0
        success = 0

        for idx, phone in enumerate(phones[:limit], 1):
            contact = db.query(models.Contact).filter(models.Contact.phone == phone).first()
            if not contact:
                continue

            attrs = dict(contact.custom_attributes or {})
            existing = attrs.get("qwen_analysis")
            if existing and not force_reanalyze:
                logger.debug(f"[{idx}/{len(phones)}] {phone} already analyzed with Qwen. Skipping.")
                continue

            # Fetch conversation thread
            msgs = (
                db.query(models.ChatMessage.sender_type, models.ChatMessage.text, models.ChatMessage.created_at)
                .filter(models.ChatMessage.customer_phone == phone)
                .order_by(models.ChatMessage.created_at.asc())
                .all()
            )
            raw_msgs = [{"sender_type": m[0], "text": m[1], "created_at": m[2]} for m in msgs]

            t0 = time.time()
            qwen_res = classify_intent_with_qwen(raw_msgs, timeout=20.0)
            elapsed = time.time() - t0

            if qwen_res:
                attrs["qwen_analysis"] = {
                    "interest_level": qwen_res["interest_level"],
                    "interest_score": qwen_res["interest_score"],
                    "detected_signals": qwen_res["detected_signals"],
                    "summary": qwen_res["summary"],
                    "analyzed_at": datetime.utcnow().isoformat(),
                    "model": "qwen2.5:3b"
                }
                contact.custom_attributes = attrs
                flag_modified(contact, "custom_attributes")
                db.commit()
                success += 1
                logger.info(
                    f"[{idx}/{len(phones)}] {phone} -> {qwen_res['interest_level']} "
                    f"({qwen_res['interest_score']}%) in {elapsed:.1f}s: {qwen_res['summary'][:60]}"
                )
            else:
                logger.warning(f"[{idx}/{len(phones)}] {phone} Qwen call timed out or failed in {elapsed:.1f}s.")

            processed += 1
            # Brief pause to keep CPU healthy
            time.sleep(0.5)

        logger.info(f"Qwen batch analysis complete! Successfully analyzed {success}/{processed} leads.")
    finally:
        db.close()


if __name__ == "__main__":
    force = "--force" in sys.argv
    run_batch_analysis(limit=250, force_reanalyze=force)
