import re
import sqlite3
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "contracts.db"

SORT_COLUMNS = {
    "created_at": "created_at",
    "date": "contract_date_iso",
    "amount": "amount_value",
    "number": "number",
    "customer": "customer",
    "contractor": "contractor",
    "filename": "filename",
}


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _normalize_date(value):
    if not value:
        return None

    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def _normalize_amount(value):
    if value is None:
        return None

    text = str(value).strip().replace("\xa0", " ")
    if not text:
        return None

    cleaned = re.sub(r"[^0-9,.-]", "", text.replace(" ", ""))
    if not cleaned:
        return None

    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        parts = cleaned.split(",")
        if len(parts) == 2 and len(parts[1]) <= 2:
            cleaned = cleaned.replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif cleaned.count(".") > 1:
        cleaned = cleaned.replace(".", "")

    try:
        return float(cleaned)
    except ValueError:
        return None


def init_db():
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS contracts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                stored_name TEXT NOT NULL UNIQUE,
                number TEXT,
                contract_date TEXT,
                contract_date_iso TEXT,
                customer TEXT,
                contractor TEXT,
                amount TEXT,
                amount_value REAL,
                raw_text TEXT,
                status TEXT NOT NULL DEFAULT 'Ожидает обработки',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(contracts)").fetchall()
        }
        if "contract_date_iso" not in columns:
            conn.execute("ALTER TABLE contracts ADD COLUMN contract_date_iso TEXT")
        if "amount_value" not in columns:
            conn.execute("ALTER TABLE contracts ADD COLUMN amount_value REAL")

        # Мягкая миграция старых записей, если база уже существовала.
        rows = conn.execute(
            "SELECT id, contract_date, amount FROM contracts"
        ).fetchall()
        for row in rows:
            conn.execute(
                """
                UPDATE contracts
                SET contract_date_iso = ?, amount_value = ?
                WHERE id = ?
                """,
                (
                    _normalize_date(row["contract_date"]),
                    _normalize_amount(row["amount"]),
                    row["id"],
                ),
            )

        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_contract_date ON contracts(contract_date_iso)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_amount_value ON contracts(amount_value)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_customer ON contracts(customer)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_contractor ON contracts(contractor)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_created_at ON contracts(created_at)"
        )
        conn.commit()


def add_contract(
    filename,
    stored_name,
    number=None,
    contract_date=None,
    customer=None,
    contractor=None,
    amount=None,
    raw_text=None,
    status="Ожидает обработки",
):
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO contracts (
                filename, stored_name, number, contract_date, contract_date_iso,
                customer, contractor, amount, amount_value, raw_text, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                filename,
                stored_name,
                number,
                contract_date,
                _normalize_date(contract_date),
                customer,
                contractor,
                amount,
                _normalize_amount(amount),
                raw_text,
                status,
            ),
        )
        conn.commit()
        return cursor.lastrowid


def _build_filters(
    search=None,
    date_from=None,
    date_to=None,
    customer=None,
    contractor=None,
    amount_min=None,
    amount_max=None,
    status=None,
):
    clauses = []
    params = []

    if search:
        like = f"%{search}%"
        clauses.append(
            """
            (
                filename LIKE ?
                OR COALESCE(number, '') LIKE ?
                OR COALESCE(customer, '') LIKE ?
                OR COALESCE(contractor, '') LIKE ?
                OR COALESCE(amount, '') LIKE ?
            )
            """
        )
        params.extend([like, like, like, like, like])

    if date_from:
        clauses.append("contract_date_iso >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("contract_date_iso <= ?")
        params.append(date_to)
    if customer:
        clauses.append("customer = ?")
        params.append(customer)
    if contractor:
        clauses.append("contractor = ?")
        params.append(contractor)
    if amount_min is not None:
        clauses.append("amount_value >= ?")
        params.append(amount_min)
    if amount_max is not None:
        clauses.append("amount_value <= ?")
        params.append(amount_max)
    if status:
        clauses.append("status = ?")
        params.append(status)

    where = ""
    if clauses:
        where = " WHERE " + " AND ".join(clauses)
    return where, params


def search_contracts(
    *,
    search=None,
    date_from=None,
    date_to=None,
    customer=None,
    contractor=None,
    amount_min=None,
    amount_max=None,
    status=None,
    sort="created_at",
    order="desc",
    limit=25,
    offset=0,
):
    where, params = _build_filters(
        search=search,
        date_from=date_from,
        date_to=date_to,
        customer=customer,
        contractor=contractor,
        amount_min=amount_min,
        amount_max=amount_max,
        status=status,
    )

    sort_column = SORT_COLUMNS.get(sort, SORT_COLUMNS["created_at"])
    direction = "ASC" if order.lower() == "asc" else "DESC"

    # NULL-значения всегда отправляем вниз таблицы.
    nullable_sort = sort_column in {
        "contract_date_iso",
        "amount_value",
        "number",
        "customer",
        "contractor",
    }
    if nullable_sort:
        order_sql = f" ORDER BY ({sort_column} IS NULL) ASC, {sort_column} {direction}, id DESC"
    else:
        order_sql = f" ORDER BY {sort_column} {direction}, id DESC"

    with _connect() as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM contracts" + where,
            params,
        ).fetchone()[0]

        rows = conn.execute(
            "SELECT * FROM contracts" + where + order_sql + " LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()

    return [dict(row) for row in rows], total


def get_all_contracts(limit=None, search=None):
    actual_limit = limit if limit is not None else 1000000
    rows, _ = search_contracts(search=search, limit=actual_limit, offset=0)
    return rows


def get_filter_options():
    # Заказчик и исполнитель намеренно не превращаются в выпадающие списки:
    # их может быть очень много, поэтому поиск по ним выполняется общей строкой.
    with _connect() as conn:
        statuses = [
            row[0]
            for row in conn.execute(
                """
                SELECT DISTINCT status FROM contracts
                WHERE status IS NOT NULL AND TRIM(status) != ''
                ORDER BY status COLLATE NOCASE
                """
            ).fetchall()
        ]
    return {"statuses": statuses}


def get_contract(contract_id):
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM contracts WHERE id = ?", (contract_id,)
        ).fetchone()
        return dict(row) if row else None


def update_contract_fields(
    contract_id,
    number=None,
    contract_date=None,
    customer=None,
    contractor=None,
    amount=None,
):
    with _connect() as conn:
        conn.execute(
            """
            UPDATE contracts
            SET number = ?, contract_date = ?, contract_date_iso = ?,
                customer = ?, contractor = ?, amount = ?, amount_value = ?,
                status = 'Проверено вручную'
            WHERE id = ?
            """,
            (
                number,
                contract_date,
                _normalize_date(contract_date),
                customer,
                contractor,
                amount,
                _normalize_amount(amount),
                contract_id,
            ),
        )
        conn.commit()


def delete_contract(contract_id):
    with _connect() as conn:
        conn.execute("DELETE FROM contracts WHERE id = ?", (contract_id,))
        conn.commit()


def get_stats():
    with _connect() as conn:
        total = conn.execute("SELECT COUNT(*) FROM contracts").fetchone()[0]
        processed = conn.execute(
            """
            SELECT COUNT(*) FROM contracts
            WHERE number IS NOT NULL
               OR contract_date IS NOT NULL
               OR customer IS NOT NULL
               OR contractor IS NOT NULL
               OR amount IS NOT NULL
            """
        ).fetchone()[0]
        checked = conn.execute(
            "SELECT COUNT(*) FROM contracts WHERE status = 'Проверено вручную'"
        ).fetchone()[0]

    return {"total": total, "processed": processed, "checked": checked}
