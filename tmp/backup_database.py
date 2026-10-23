"""Save a consistent, read-only JSONL snapshot without logging credentials."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from psycopg2 import sql
from ml.utils.db import connect

destination = Path.home() / "Desktop" / "Neuroscope-backups"
destination.mkdir(exist_ok=True)
stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
archive = destination / f"database-data-{stamp}.zip"
manifest = {
    "created_utc": stamp,
    "format": "JSONL table data, not a pg_dump restore archive",
    "tables": [],
    "skipped_tables": [],
}
with connect() as connection:
    connection.set_session(isolation_level="REPEATABLE READ", readonly=True)
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_timestamp, version()")
        timestamp, version = cursor.fetchone()
        manifest.update(snapshot_timestamp=str(timestamp), server_version=version)
        cursor.execute("""
            SELECT n.nspname, c.relname, has_table_privilege(c.oid, 'SELECT')
            FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE c.relkind IN ('r', 'p') AND NOT c.relispartition
              AND n.nspname NOT LIKE 'pg_%' AND n.nspname <> 'information_schema'
            ORDER BY n.nspname, c.relname
        """)
        tables = cursor.fetchall()
        cursor.execute("""SELECT table_schema, table_name, column_name, ordinal_position,
            data_type, udt_schema, udt_name, is_nullable, column_default,
            is_identity, identity_generation
            FROM information_schema.columns
            WHERE table_schema NOT LIKE 'pg_%' AND table_schema <> 'information_schema'
            ORDER BY table_schema, table_name, ordinal_position""")
        columns = [
            dict(zip([d.name for d in cursor.description], row)) for row in cursor.fetchall()
        ]
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
        output.writestr("columns.json", json.dumps(columns, indent=2, default=str))
        for index, (schema, table, readable) in enumerate(tables):
            if not readable:
                manifest["skipped_tables"].append(f"{schema}.{table}")
                continue
            count = 0
            digest = hashlib.sha256()
            filename = f"tables/{schema}.{table}.jsonl"
            with connection.cursor(name=f"backup_{index}") as cursor:
                cursor.execute(
                    sql.SQL("SELECT row_to_json(t)::text FROM {}.{} AS t").format(
                        sql.Identifier(schema), sql.Identifier(table)
                    )
                )
                with output.open(filename, "w") as target:
                    for row in cursor:
                        data = (row[0] + "\n").encode("utf-8")
                        target.write(data)
                        digest.update(data)
                        count += 1
            manifest["tables"].append(
                {
                    "schema": schema,
                    "table": table,
                    "rows": count,
                    "file": filename,
                    "sha256": digest.hexdigest(),
                }
            )
            print(f"[backup] {schema}.{table}: {count} rows", flush=True)
        output.writestr("manifest.json", json.dumps(manifest, indent=2))

with zipfile.ZipFile(archive) as saved:
    assert saved.testzip() is None, "Backup ZIP integrity check failed"
    for table in manifest["tables"]:
        digest = hashlib.sha256()
        count = 0
        with saved.open(table["file"]) as source:
            for line in source:
                json.loads(line)
                digest.update(line)
                count += 1
        assert count == table["rows"] and digest.hexdigest() == table["sha256"]
print(f"[backup] VERIFIED {archive}", flush=True)
print(
    f"[backup] {len(manifest['tables'])} tables, {sum(t['rows'] for t in manifest['tables'])} rows",
    flush=True,
)
print(f"[backup] inaccessible tables: {manifest['skipped_tables']}", flush=True)
