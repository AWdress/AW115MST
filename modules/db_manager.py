"""
数据库管理模块
使用 SQLite 替代 recheck.json / checkpoint.json，提供原子写入和并发安全
"""

import sqlite3
import json
import time
from pathlib import Path
from typing import Optional, Dict, Any, Set


class DBManager:
    """SQLite 数据库管理器（file_records + processed_files 两张表）"""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ─── Internal ───────────────────────────────────────────────

    def _get_conn(self) -> sqlite3.Connection:
        """创建一个新连接（WAL 模式支持并发读写）"""
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS file_records (
                    file_key             TEXT PRIMARY KEY,
                    sha1                 TEXT,
                    size                 INTEGER,
                    last_status          TEXT,
                    check_count          INTEGER DEFAULT 0,
                    first_check_time     REAL,
                    last_check_time      REAL,
                    location             TEXT DEFAULT 'input',
                    non_rapid_dispatched INTEGER DEFAULT 0,
                    non_rapid_path       TEXT,
                    uploaded             INTEGER DEFAULT 0,
                    processed            INTEGER DEFAULT 0,
                    processed_time       REAL,
                    target_path          TEXT,
                    source_input_key     TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS processed_files (
                    file_key   TEXT PRIMARY KEY,
                    created_at REAL
                )
            """)

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        """将 Row 转为 dict，布尔列转为 Python bool（与旧 JSON 行为一致）"""
        d = dict(row)
        for col in ('non_rapid_dispatched', 'uploaded', 'processed'):
            d[col] = bool(d.get(col, 0))
        return d

    # ─── file_records ───────────────────────────────────────────

    def get_record(self, file_key: str) -> Optional[Dict[str, Any]]:
        """查询单条记录，不存在返回 None"""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM file_records WHERE file_key = ?", (file_key,)
            ).fetchone()
            return self._row_to_dict(row) if row else None

    def get_all_records(self) -> Dict[str, Dict[str, Any]]:
        """返回所有记录 {file_key: dict}"""
        with self._get_conn() as conn:
            rows = conn.execute("SELECT * FROM file_records").fetchall()
            return {row['file_key']: self._row_to_dict(row) for row in rows}

    def upsert_record(self, file_key: str, **fields) -> None:
        """INSERT 或 UPDATE 一条记录（并发安全）"""
        with self._get_conn() as conn:
            # 保证行存在（区别于 INSERT OR REPLACE ，后者会删除再重建丢失未传入字段）
            conn.execute(
                "INSERT OR IGNORE INTO file_records (file_key) VALUES (?)",
                (file_key,)
            )
            if fields:
                set_clause = ', '.join([f"{k} = ?" for k in fields])
                conn.execute(
                    f"UPDATE file_records SET {set_clause} WHERE file_key = ?",
                    list(fields.values()) + [file_key]
                )

    def delete_record(self, file_key: str) -> None:
        with self._get_conn() as conn:
            conn.execute("DELETE FROM file_records WHERE file_key = ?", (file_key,))

    def rename_record(self, old_key: str, new_key: str, **extra_fields) -> None:
        """将记录从 old_key 移动到 new_key（SQLite 不支持直接修改 PRIMARY KEY）"""
        record = self.get_record(old_key)
        if record is None:
            return
        self.delete_record(old_key)
        record.update(extra_fields)
        record['file_key'] = new_key
        # 布尔字段转为整数
        for col in ('non_rapid_dispatched', 'uploaded', 'processed'):
            record[col] = 1 if record.get(col) else 0
        cols = ', '.join(record.keys())
        placeholders = ', '.join(['?'] * len(record))
        with self._get_conn() as conn:
            conn.execute(
                f"INSERT OR REPLACE INTO file_records ({cols}) VALUES ({placeholders})",
                list(record.values())
            )

    def count_records(self) -> int:
        with self._get_conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM file_records").fetchone()[0]

    # ─── processed_files ────────────────────────────────────────

    def get_all_processed(self) -> Set[str]:
        with self._get_conn() as conn:
            rows = conn.execute("SELECT file_key FROM processed_files").fetchall()
            return {row[0] for row in rows}

    def mark_processed(self, file_key: str) -> None:
        with self._get_conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO processed_files (file_key, created_at) VALUES (?, ?)",
                (file_key, time.time())
            )

    def is_processed(self, file_key: str) -> bool:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM processed_files WHERE file_key = ?", (file_key,)
            ).fetchone()
            return row is not None

    # ─── migration ──────────────────────────────────────────────

    def migrate_from_json(self, recheck_file: Path, checkpoint_file: Path) -> int:
        """
        将旧 JSON 数据迁移到 SQLite（仅在数据库为空时执行，避免重复导入）。
        返回迁移的 file_records 条数。
        """
        if self.count_records() > 0:
            return 0  # 已有数据，跳过

        migrated = 0

        if recheck_file.exists():
            try:
                with open(recheck_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for file_key, record in data.items():
                    self.upsert_record(
                        file_key,
                        sha1=record.get('sha1'),
                        size=record.get('size'),
                        last_status=record.get('last_status'),
                        check_count=record.get('check_count', 0),
                        first_check_time=record.get('first_check_time'),
                        last_check_time=record.get('last_check_time'),
                        location=record.get('location', 'input'),
                        non_rapid_dispatched=1 if record.get('non_rapid_dispatched') else 0,
                        non_rapid_path=record.get('non_rapid_path'),
                        uploaded=1 if record.get('uploaded') else 0,
                        processed=1 if record.get('processed') else 0,
                        processed_time=record.get('processed_time'),
                        target_path=record.get('target_path'),
                        source_input_key=record.get('source_input_key'),
                    )
                    migrated += 1
                print(f"[DB] 已从 recheck.json 迁移 {migrated} 条记录到 SQLite")
            except Exception as e:
                print(f"[DB] 迁移 recheck.json 失败: {e}")

        if checkpoint_file.exists():
            try:
                with open(checkpoint_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for file_key in data.get('processed_files', []):
                    self.mark_processed(file_key)
            except Exception as e:
                print(f"[DB] 迁移 checkpoint.json 失败: {e}")

        return migrated
