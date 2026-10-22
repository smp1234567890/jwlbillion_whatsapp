import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

import config

DATABASE_URL = config.DATABASE_URL
if not DATABASE_URL:
    if config.ENVIRONMENT == "production":
        raise RuntimeError("FATAL: DATABASE_URL is not configured for production.")
    DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/whatsapp_crm"

# Fix SQLAlchemy requirement: SQLAlchemy requires 'postgresql://' instead of legacy 'postgres://'
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Fail closed if production database connects to localhost or sqlite
if config.ENVIRONMENT == "production":
    url_lower = DATABASE_URL.lower()
    if "localhost" in url_lower or "127.0.0.1" in url_lower or url_lower.startswith("sqlite"):
        raise RuntimeError(
            "FATAL: Production database must be a remote PostgreSQL instance with TLS enabled. "
            "Localhost and SQLite are strictly prohibited in production."
        )

# Enable connection pooling and pre-ping to handle serverless/cloud DB reconnects gracefully
# Enable conservative connection pooling and pre-ping to handle cloud DB limits gracefully
# Aiven Starter/Free PostgreSQL has a strict max_connections limit (20-25).
# Limiting pool_size=7 with max_overflow=3 guarantees each worker process consumes at most 10 connections,
# safely below Aiven's ceiling while providing abundant concurrency for parallel requests and workflow sweeps.
#
# pool_timeout=5 (down from 30): When pool is exhausted, fail fast in 5s instead of blocking 30s.
# This prevents cascading timeouts — a blocked request frees its slot quickly so the scheduler
# and incoming webhooks can acquire a connection on the next retry instead of waiting 30 full seconds.
engine_options = {"pool_pre_ping": True, "pool_recycle": 180}
if DATABASE_URL.startswith("sqlite"):
    engine_options["connect_args"] = {"check_same_thread": False}
elif DATABASE_URL.startswith("postgresql"):
    engine_options["pool_size"] = int(os.getenv("DB_POOL_SIZE", "7"))
    engine_options["max_overflow"] = int(os.getenv("DB_MAX_OVERFLOW", "3"))
    engine_options["pool_timeout"] = int(os.getenv("DB_POOL_TIMEOUT", "5"))
    connect_args = {}
    if config.ENVIRONMENT == "production":
        sslmode = os.getenv("DB_SSLMODE", "verify-full").strip()
        if sslmode not in ("verify-full", "verify-ca", "require"):
            raise RuntimeError(f"FATAL: Insecure DB_SSLMODE='{sslmode}' in production. Must be verify-full, verify-ca, or require.")
        connect_args["sslmode"] = sslmode
        sslrootcert = os.getenv("DB_SSLROOTCERT")
        if sslrootcert:
            connect_args["sslrootcert"] = sslrootcert
        sslcert = os.getenv("DB_SSLCERT")
        if sslcert:
            connect_args["sslcert"] = sslcert
        sslkey = os.getenv("DB_SSLKEY")
        if sslkey:
            connect_args["sslkey"] = sslkey
    if connect_args:
        engine_options["connect_args"] = connect_args

engine = create_engine(DATABASE_URL, **engine_options)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
