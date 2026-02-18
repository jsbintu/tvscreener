"""
Bubby Vision — QuestDB Backup Celery Task

Runs daily at 2:00 AM UTC via Celery Beat.
Creates a QuestDB backup snapshot and optionally uploads to Oracle Object Storage.
Falls back to local disk backup if OCI is not configured.
"""

from __future__ import annotations

import gzip
import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

BACKUP_DIR = Path("/tmp/bubby-vision-backups")


@celery_app.task(bind=True, max_retries=1, default_retry_delay=300)
def backup_questdb(self) -> dict:
    """Create a daily QuestDB backup snapshot.

    Steps:
    1. Connect to QuestDB via psycopg2
    2. Export critical tables to JSON (pattern_outcomes, ohlcv recent, alerts)
    3. Compress with gzip
    4. Upload to Oracle Object Storage if OCI config available
    5. Clean up old local backups (keep last 7 days)
    """
    try:
        import psycopg2
        from app.config import get_settings

        settings = get_settings()
        today = datetime.utcnow().strftime("%Y-%m-%d")

        # Ensure backup directory exists
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)

        conn = psycopg2.connect(settings.questdb_dsn, connect_timeout=10)
        conn.autocommit = True
        cur = conn.cursor()

        backup_data = {"date": today, "tables": {}}

        # Tables to back up
        tables_config = [
            {
                "name": "pattern_outcomes",
                "query": """
                    SELECT ticker, pattern_name, direction, outcome,
                           confidence, entry_price, target_price, stop_price,
                           exit_price, pnl_pct, max_favorable_pct, max_adverse_pct,
                           bars_held, detected_at, resolved_at
                    FROM pattern_outcomes
                    ORDER BY resolved_at DESC
                    LIMIT 10000;
                """,
            },
            {
                "name": "price_alerts",
                "query": """
                    SELECT id, user_id, ticker, threshold, direction,
                           active, created_at, triggered_at
                    FROM price_alerts
                    ORDER BY created_at DESC
                    LIMIT 5000;
                """,
            },
            {
                "name": "watchlist",
                "query": """
                    SELECT user_id, ticker, added_at
                    FROM watchlist
                    ORDER BY added_at DESC
                    LIMIT 5000;
                """,
            },
            {
                "name": "users",
                "query": """
                    SELECT id, email, display_name, is_active, created_at
                    FROM users
                    ORDER BY created_at DESC
                    LIMIT 1000;
                """,
            },
        ]

        for table_conf in tables_config:
            try:
                cur.execute(table_conf["query"])
                columns = [desc[0] for desc in cur.description]
                rows = cur.fetchall()
                backup_data["tables"][table_conf["name"]] = {
                    "columns": columns,
                    "row_count": len(rows),
                    "rows": [
                        {col: (str(val) if val is not None else None) for col, val in zip(columns, row)}
                        for row in rows
                    ],
                }
                logger.info(f"Backup: {table_conf['name']} → {len(rows)} rows")
            except Exception as e:
                logger.warning(f"Backup: {table_conf['name']} failed: {e}")
                backup_data["tables"][table_conf["name"]] = {"error": str(e)}

        cur.close()
        conn.close()

        # Write compressed backup
        backup_file = BACKUP_DIR / f"bubby-vision-{today}.json.gz"
        with gzip.open(str(backup_file), "wt", encoding="utf-8") as f:
            json.dump(backup_data, f, default=str, indent=2)

        file_size = backup_file.stat().st_size
        logger.info(f"Backup written: {backup_file} ({file_size:,} bytes)")

        # Upload to Oracle Object Storage if configured
        oci_uploaded = _upload_to_oci(backup_file, today)

        # Clean up old local backups (keep last 7)
        _cleanup_old_backups(keep=7)

        return {
            "status": "success",
            "date": today,
            "file": str(backup_file),
            "size_bytes": file_size,
            "tables_backed_up": list(backup_data["tables"].keys()),
            "oci_uploaded": oci_uploaded,
        }

    except Exception as exc:
        logger.error(f"Backup failed: {exc}")
        raise self.retry(exc=exc)


def _upload_to_oci(backup_file: Path, date_str: str) -> bool:
    """Upload backup to Oracle Object Storage (free 10GB).

    Requires OCI config at ~/.oci/config or environment variables.
    Gracefully skips if OCI is not configured.
    """
    try:
        import oci

        config = oci.config.from_file()
        object_storage = oci.object_storage.ObjectStorageClient(config)
        namespace = object_storage.get_namespace().data

        bucket_name = os.environ.get("OCI_BACKUP_BUCKET", "bubby-vision-backups")
        object_name = f"questdb/{date_str}/bubby-vision-{date_str}.json.gz"

        with open(str(backup_file), "rb") as f:
            object_storage.put_object(
                namespace_name=namespace,
                bucket_name=bucket_name,
                object_name=object_name,
                put_object_body=f,
            )

        logger.info(f"OCI upload success: {object_name}")
        return True

    except ImportError:
        logger.info("OCI SDK not installed — skipping cloud backup")
        return False
    except Exception as e:
        logger.warning(f"OCI upload failed: {e}")
        return False


def _cleanup_old_backups(keep: int = 7) -> int:
    """Remove local backup files older than `keep` days."""
    if not BACKUP_DIR.exists():
        return 0

    files = sorted(BACKUP_DIR.glob("bubby-vision-*.json.gz"))
    removed = 0
    while len(files) > keep:
        old_file = files.pop(0)
        old_file.unlink()
        removed += 1
        logger.info(f"Cleaned up old backup: {old_file.name}")

    return removed
