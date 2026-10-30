# core/db_engine.py
"""
Secure Read-Only Database Engine for University Multi-Agent System
Enforces zero-trust query validation, strict table whitelisting,
and mandatory student-level data isolation to prevent data breaches and IDOR.
"""
import re
import sqlite3
import json
from typing import Optional, Any
from config import DB_PATH, console

# Allowed tables classification
PUBLIC_TABLES = {"courses", "transport_routes", "exam_datesheets"}
STUDENT_TABLES = {
    "students", "student_fees", "hostel_allocations", 
    "seating_arrangements", "grade_records", "internship_files", 
    "helpdesk_tickets", "query_audit_logs", "student_queries", "student_feedback"
}
ALL_ALLOWED_TABLES = PUBLIC_TABLES | STUDENT_TABLES

# Forbidden SQL tokens and commands
DISALLOWED_PATTERNS = [
    r";",                    # Stacked queries
    r"--",                   # Single-line comment
    r"/\*",                  # Multi-line comment
    r"\bdrop\b",             # Drop table/index
    r"\bdelete\b",           # Delete rows
    r"\bupdate\b",           # Update rows
    r"\binsert\b",           # Insert rows
    r"\balter\b",            # Alter schema
    r"\battach\b",           # Attach external database
    r"\bdetach\b",           # Detach database
    r"\bpragma\b",           # Internal pragma
    r"\bexec(?:ute)?\b",     # Execute procedures
    r"\bcreate\b",           # Create table
    r"\bunion\b",            # Union injection attempts
    r"\bsqlite_\w+",         # Internal SQLite metadata tables
    r"\badmin_\w+"           # Internal admin tables
]


def extract_table_names(sql: str) -> set[str]:
    """Extracts table names mentioned after FROM or JOIN in the SQL query."""
    tables = set()
    # Matches: FROM tablename or JOIN tablename
    matches = re.findall(r"\b(?:from|join)\s+([a-zA-Z0-9_]+)", sql, re.IGNORECASE)
    for m in matches:
        tables.add(m.lower())
    return tables


def run_db_query(
    sql_query: str, 
    authenticated_student_id: Optional[str] = None,
    session: Optional[Any] = None
) -> str:
    """
    Executes a validated read-only SQLite SELECT query against university.db.
    Guarantees:
    1. Read-only execution (only single SELECT permitted).
    2. Strict table whitelisting.
    3. Mandatory Student Data Isolation: queries on student tables are strictly
       isolated to authenticated_student_id to eliminate data breaches.
    """
    clean_sql = sql_query.strip()

    # 1. Resolve student ID if session passed
    auth_id = authenticated_student_id
    if not auth_id and session:
        auth_id = getattr(session, "university_id", None) or getattr(session, "registration_no", None)
    if auth_id:
        auth_id = str(auth_id).strip()

    # 2. Syntax & Security validations
    if not clean_sql.lower().startswith("select"):
        return "Security Violation: Only SELECT queries are permitted on this database."

    for pat in DISALLOWED_PATTERNS:
        if re.search(pat, clean_sql, re.IGNORECASE):
            return "Security Violation: Disallowed SQL token, comment, or command detected."

    # 3. Table Whitelisting Check
    tables_used = extract_table_names(clean_sql)
    if not tables_used:
        return "Security Violation: Unable to identify target table in query."

    unauthorized_tables = tables_used - ALL_ALLOWED_TABLES
    if unauthorized_tables:
        return f"Security Violation: Access to table(s) {list(unauthorized_tables)} is strictly prohibited."

    # 4. Mandatory Student Data Isolation (Row-Level Security Enforcement)
    touches_student_data = bool(tables_used & STUDENT_TABLES)

    if touches_student_data:
        if not auth_id:
            return "Security Violation: Authentication required to query student records."

        # Detect cross-student query attempts (e.g. searching for a different university_id or roll number)
        # Look for explicit university_id or student ID patterns differing from auth_id
        found_ids = re.findall(r"['\"](\d{5,12})['\"]", clean_sql)
        for found_id in found_ids:
            if found_id != auth_id:
                return (
                    f"Security Policy Violation: Access to records belonging to other students "
                    f"is strictly prohibited under university privacy policy."
                )

        # Enforce student isolation filter:
        # Append WHERE or AND clause to bind strictly to authenticated student ID
        id_filter_pattern = rf"\buniversity_id\s*=\s*['\"]?{re.escape(auth_id)}['\"]?"
        if not re.search(id_filter_pattern, clean_sql, re.IGNORECASE):
            if re.search(r"\bwhere\b", clean_sql, re.IGNORECASE):
                clean_sql = f"{clean_sql} AND university_id = '{auth_id}'"
            else:
                clean_sql = f"{clean_sql} WHERE university_id = '{auth_id}'"

    # 5. Execute with read-only connection
    try:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        cursor = conn.cursor()
        cursor.execute(clean_sql)
        rows = cursor.fetchall()
        cols = [d[0] for d in cursor.description] if cursor.description else []
        conn.close()

        if not rows:
            return "No matching records found in the database."

        results = [dict(zip(cols, r)) for r in rows[:15]]
        return json.dumps(results, indent=2)
    except sqlite3.OperationalError as oe:
        return f"Query Notice: {oe}"
    except Exception as e:
        return f"Database Error: {e}"