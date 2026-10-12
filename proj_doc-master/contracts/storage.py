import json
from contextlib import contextmanager
from pathlib import Path
import sqlite3


@contextmanager
def connect(path):
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def initialize(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as db:
        db.execute('''CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_name TEXT NOT NULL,
            stored_name TEXT NOT NULL,
            number TEXT,
            date TEXT,
            customer TEXT,
            contractor TEXT,
            amount TEXT,
            raw_text TEXT NOT NULL,
            normalized_text TEXT NOT NULL,
            warnings TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )''')


def save_document(path, original_name, stored_name, result):
    with connect(path) as db:
        cursor = db.execute('''INSERT INTO documents
            (original_name, stored_name, number, date, customer, contractor, amount,
             raw_text, normalized_text, warnings, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (
                original_name, stored_name, result.fields['number'], result.fields['date'],
                result.fields['customer'], result.fields['contractor'], result.fields['amount'],
                result.raw_text, result.normalized_text,
                json.dumps(result.warnings, ensure_ascii=False), result.status,
            ))
        return cursor.lastrowid


def list_documents(path):
    with connect(path) as db:
        return db.execute('SELECT * FROM documents ORDER BY id DESC').fetchall()


def get_document(path, document_id):
    with connect(path) as db:
        return db.execute('SELECT * FROM documents WHERE id = ?', (document_id,)).fetchone()
