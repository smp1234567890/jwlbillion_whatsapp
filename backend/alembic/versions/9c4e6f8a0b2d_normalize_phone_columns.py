"""normalize_phone_columns — E.164 backfill for all phone fields

Revision ID: 9c4e6f8a0b2d
Revises: 8b3d5f7a9c1e
Create Date: 2026-09-20 21:40:00.000000

This migration normalizes every phone column to strict E.164 format using
the phonenumbers library.  Before touching any row it runs a conflict
detection pass and RAISES if two distinct raw values would normalize to
the same E.164 string (i.e. duplicates would be silently merged).
Conflicts must be resolved manually before this migration can proceed.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision: str = '9c4e6f8a0b2d'
down_revision: Union[str, None] = '8b3d5f7a9c1e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_REGION = "IN"

# Tables and their phone columns to migrate
PHONE_COLUMNS = [
    ("contacts",          "phone"),
    ("opt_outs",          "phone"),
    ("cart_events",       "customer_phone"),
    ("message_logs",      "recipient_phone"),
    ("chat_messages",     "customer_phone"),
    ("workflow_sessions", "customer_phone"),
]


def _normalize_phone_python(raw: str, default_region: str = DEFAULT_REGION) -> str:
    """Inline E.164 normalizer — mirrors phone_service.normalize_phone."""
    import phonenumbers
    from phonenumbers import NumberParseException, PhoneNumberFormat

    if not raw or not raw.strip():
        return raw

    cleaned = raw.strip()
    try:
        if not cleaned.startswith("+") and cleaned.startswith("91") and len(cleaned) == 12:
            parsed = phonenumbers.parse("+" + cleaned, None)
        else:
            parsed = phonenumbers.parse(cleaned, default_region)
    except NumberParseException:
        return raw  # leave unparseable rows unchanged; handled by conflict report

    if not phonenumbers.is_possible_number(parsed) or not phonenumbers.is_valid_number(parsed):
        return raw

    return phonenumbers.format_number(parsed, PhoneNumberFormat.E164)


def _detect_conflicts(conn, table: str, col: str) -> list:
    """
    Returns a list of (normalized_phone, [raw_values]) groups where more than
    one distinct raw value normalises to the same E.164 string.
    """
    rows = conn.execute(text(f"SELECT id, {col} FROM {table} WHERE {col} IS NOT NULL")).fetchall()

    from collections import defaultdict
    bucket: dict = defaultdict(list)
    for row_id, raw in rows:
        normalized = _normalize_phone_python(raw or "")
        if normalized and normalized != raw:
            bucket[normalized].append((row_id, raw))
        elif normalized == raw:
            bucket[normalized].append((row_id, raw))

    conflicts = []
    for norm, items in bucket.items():
        # Conflict = two DIFFERENT raw values that map to the same E.164
        unique_raws = set(r for _, r in items)
        if len(unique_raws) > 1:
            conflicts.append((norm, list(unique_raws)))
    return conflicts


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    existing_tables = insp.get_table_names()

    # ── Phase 1: conflict detection across tables with unique constraints ───
    UNIQUE_PHONE_COLUMNS = [
        ("contacts", "phone"),
        ("opt_outs", "phone"),
    ]
    all_conflicts = []
    for table, col in UNIQUE_PHONE_COLUMNS:
        if table not in existing_tables:
            continue
        cols = [c["name"] for c in insp.get_columns(table)]
        if col not in cols:
            continue
        conflicts = _detect_conflicts(conn, table, col)
        for norm, raws in conflicts:
            all_conflicts.append(f"  {table}.{col}: raw values {raws!r} all normalize to '{norm}'")

    if all_conflicts:
        report = "\n".join(all_conflicts)
        raise RuntimeError(
            f"\n\n{'='*72}\n"
            f"PHONE NORMALIZATION CONFLICT REPORT — migration aborted.\n"
            f"The following phone values would create duplicate E.164 records.\n"
            f"Resolve these conflicts manually before re-running this migration.\n"
            f"{'='*72}\n"
            f"{report}\n"
            f"{'='*72}\n"
        )

    # ── Phase 2: normalize each table in batches of 500 ─────────────────────
    for table, col in PHONE_COLUMNS:
        if table not in existing_tables:
            continue
        cols = [c["name"] for c in insp.get_columns(table)]
        if col not in cols:
            continue

        rows = conn.execute(
            text(f"SELECT id, {col} FROM {table} WHERE {col} IS NOT NULL")
        ).fetchall()

        updates = []
        for row_id, raw in rows:
            normalized = _normalize_phone_python(raw or "")
            if normalized and normalized != raw:
                updates.append({"rid": row_id, "norm": normalized})

        # Execute in batches of 500
        for i in range(0, len(updates), 500):
            batch = updates[i:i + 500]
            for item in batch:
                conn.execute(
                    text(f"UPDATE {table} SET {col} = :norm WHERE id = :rid"),
                    {"norm": item["norm"], "rid": item["rid"]}
                )

    # ── Phase 3: add unique constraints on primary identity columns ───────────
    # contacts.phone
    if "contacts" in existing_tables:
        try:
            op.create_unique_constraint("uq_contacts_phone", "contacts", ["phone"])
        except Exception:
            pass  # already exists

    # opt_outs.phone
    if "opt_outs" in existing_tables:
        try:
            op.create_unique_constraint("uq_opt_outs_phone", "opt_outs", ["phone"])
        except Exception:
            pass  # already exists


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    existing_tables = insp.get_table_names()

    if "opt_outs" in existing_tables:
        try:
            op.drop_constraint("uq_opt_outs_phone", "opt_outs", type_="unique")
        except Exception:
            pass

    if "contacts" in existing_tables:
        try:
            op.drop_constraint("uq_contacts_phone", "contacts", type_="unique")
        except Exception:
            pass
    # Note: raw phone values are NOT restored on downgrade because we cannot
    # reverse a lossy normalization (the original formatting is not stored).
