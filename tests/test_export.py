"""Tests for the S3 export logic (mocked boto3 client)."""

from __future__ import annotations

from unittest.mock import MagicMock

from src.pipeline.export import export_to_s3


class TestExportToS3:
    def test_uploads_one_object_per_table(self):
        client = MagicMock()
        rows_by_table = {
            "driver_standings": [
                {"driver_ref": "ver", "total_points": 25.0},
                {"driver_ref": "ham", "total_points": 18.0},
            ],
            "races": [{"round": 1, "name": "Bahrain GP"}],
        }

        keys = export_to_s3(rows_by_table, bucket="my-bucket", prefix="f1/2024", client=client)

        assert keys == ["f1/2024/driver_standings.csv", "f1/2024/races.csv"]
        assert client.put_object.call_count == 2

        first = client.put_object.call_args_list[0].kwargs
        assert first["Bucket"] == "my-bucket"
        assert first["Key"] == "f1/2024/driver_standings.csv"
        body = first["Body"].decode("utf-8")
        assert "driver_ref,total_points" in body
        assert "ver,25.0" in body

    def test_empty_table_writes_header_only_or_skips_cleanly(self):
        client = MagicMock()
        keys = export_to_s3({"empty": []}, bucket="b", prefix="p", client=client)

        assert keys == ["p/empty.csv"]
        client.put_object.assert_called_once()
        body = client.put_object.call_args.kwargs["Body"].decode("utf-8")
        assert body == ""  # no rows -> empty body
