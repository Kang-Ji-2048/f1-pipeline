"""Export ingested F1 data to Amazon S3 as CSV artifacts.

Credentials are resolved by boto3 in the usual way (environment variables, shared
config, or an EC2 instance role) — this module never handles them directly.
"""

from __future__ import annotations

import csv
import io
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


def export_to_s3(
    rows_by_table: dict[str, list[dict[str, Any]]],
    bucket: str,
    prefix: str,
    client: Any | None = None,
) -> list[str]:
    """Write each table to a CSV object under ``s3://bucket/prefix/<table>.csv``.

    Returns the list of S3 keys written. ``client`` is injectable for testing;
    when omitted a default boto3 S3 client is created (boto3 imported lazily so
    the rest of the package does not depend on it).
    """
    if client is None:
        import boto3

        client = boto3.client("s3")

    keys: list[str] = []
    for table, rows in rows_by_table.items():
        buf = io.StringIO()
        if rows:
            writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        key = f"{prefix}/{table}.csv"
        client.put_object(Bucket=bucket, Key=key, Body=buf.getvalue().encode("utf-8"))
        keys.append(key)
        logger.info("s3_exported", bucket=bucket, key=key, rows=len(rows))

    return keys
