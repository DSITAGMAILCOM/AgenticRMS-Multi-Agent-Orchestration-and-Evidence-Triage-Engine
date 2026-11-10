# core/admin_db.py
"""
Dedicated Administrator Authentication & Audit Logging Engine.
Maintains absolute data separation:
- All administrator credentials, hashed passwords, active sessions,
  and administrative audit trails are stored strictly in `admin.db`.
- Student records and ticket information remain strictly in `university.db`.
"""
import os
import sqlite3
import hashlib
import secrets
import hmac
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADMIN_DB_PATH = os.path.join(BASE_DIR, "admin.db")
PBKDF2_ROUNDS = 100_000
SESSION_EXPIRY_HOURS = 12


def get_admin_db_connection() -> sqlite3.Connection:
    """Returns a connection to the dedicated admin.db database."""
    conn = sqlite3.connect(ADMIN_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def hash_password(password: str, salt_hex: Optional[str] = None) -> tuple[str, str]:
    """
    Hashes a password using PBKDF2-HMAC-SHA256 with 100,000 iterations
    and a cryptographically secure 16-byte random salt.
    Returns: (password_hash_hex, salt_hex)
    """
    if not salt_hex:
        salt_bytes = secrets.token_bytes(16)
        salt_hex = salt_bytes.hex()
    else:
        salt_bytes = bytes.fromhex(salt_hex)

    derived = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt_bytes,
        PBKDF2_ROUNDS
    )
    return derived.hex(), salt_hex


def verify_password(plain_password: str, stored_hash_hex: str, salt_hex: str) -> bool:
    """
    Verifies a plain password against the stored PBKDF2 hash using constant-time comparison
    to defend against timing side-channel attacks.
    """
    computed_hash_hex, _ = hash_password(plain_password, salt_hex=salt_hex)
    return hmac.compare_digest(computed_hash_hex, stored_hash_hex)


def init_admin_database():
    """
    Initializes the dedicated admin database schema and seeds initial administrator accounts.
    Strictly isolated from university.db.
    """
    conn = get_admin_db_connection()
    cursor = conn.cursor()

    # 1. Administrator Accounts Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admin_users (
        admin_id TEXT PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'SupportOfficer',
        full_name TEXT NOT NULL,
        department TEXT NOT NULL DEFAULT 'Student Welfare & Helpdesk',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_login TIMESTAMP,
        is_active INTEGER DEFAULT 1
    );
    """)

    # 2. Administrator Active Sessions Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admin_sessions (
        session_token TEXT PRIMARY KEY,
        admin_id TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP NOT NULL,
        ip_address TEXT,
        user_agent TEXT,
        FOREIGN KEY (admin_id) REFERENCES admin_users (admin_id) ON DELETE CASCADE
    );
    """)

    # 3. Administrative Audit Logs Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admin_audit_logs (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_id TEXT NOT NULL,
        username TEXT NOT NULL,
        action TEXT NOT NULL,
        target_ticket_id TEXT,
        details TEXT,
        ip_address TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    conn.commit()

    # Seed Default Administrators if table is empty
    cursor.execute("SELECT COUNT(*) FROM admin_users")
    if cursor.fetchone()[0] == 0:
        seed_admins = [
            {
                "admin_id": "ADM-001",
                "username": "admin",
                "email": "admin@lpu.in",
                "password": "Admin@RMS2026!",
                "role": "SuperAdmin",
                "full_name": "Dr. Vikram Malhotra",
                "department": "Dean of Student Affairs"
            },
            {
                "admin_id": "ADM-002",
                "username": "officer_sharma",
                "email": "r.sharma@lpu.in",
                "password": "Officer@RMS2026!",
                "role": "SupportOfficer",
                "full_name": "Rajesh Sharma",
                "department": "Hostel & Central Grievance Desk"
            },
            {
                "admin_id": "ADM-003",
                "username": "exam_controller",
                "email": "coe@lpu.in",
                "password": "Exam@RMS2026!",
                "role": "ExaminationOfficer",
                "full_name": "Prof. S. K. Gupta",
                "department": "Controller of Examinations"
            }
        ]

        for adm in seed_admins:
            p_hash, salt = hash_password(adm["password"])
            cursor.execute("""
                INSERT INTO admin_users (admin_id, username, email, password_hash, salt, role, full_name, department)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                adm["admin_id"],
                adm["username"],
                adm["email"],
                p_hash,
                salt,
                adm["role"],
                adm["full_name"],
                adm["department"]
            ))

        conn.commit()

    conn.close()


def authenticate_admin(username: str, plain_password: str, ip_address: str = "127.0.0.1") -> Dict[str, Any]:
    """
    Authenticates an administrator against the isolated admin.db database.
    If valid, creates a new session token and records an audit log entry.
    """
    conn = get_admin_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT admin_id, username, email, password_hash, salt, role, full_name, department, is_active
        FROM admin_users
        WHERE LOWER(username) = LOWER(?) OR LOWER(email) = LOWER(?)
    """, (username.strip(), username.strip()))
    user = cursor.fetchone()

    if not user:
        # Check if table exists or is unseeded
        try:
            cursor.execute("SELECT COUNT(*) FROM admin_users")
            cnt = cursor.fetchone()[0]
            if cnt == 0:
                raise ValueError("Unseeded admin table")
        except Exception:
            conn.close()
            init_admin_database()
            return authenticate_admin(username, plain_password, ip_address)

        conn.close()
        return {"success": False, "error": "Invalid administrator username or credentials."}

    if not user["is_active"]:
        conn.close()
        return {"success": False, "error": "This administrator account is disabled."}

    is_valid = verify_password(plain_password, user["password_hash"], user["salt"])
    if not is_valid:
        conn.close()
        return {"success": False, "error": "Invalid administrator username or credentials."}

    # Generate cryptographically secure session token
    session_token = secrets.token_urlsafe(32)
    now = datetime.now()
    expires_at = (now + timedelta(hours=SESSION_EXPIRY_HOURS)).strftime("%Y-%m-%d %H:%M:%S")
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")

    # Store active session in admin.db
    cursor.execute("""
        INSERT INTO admin_sessions (session_token, admin_id, created_at, expires_at, ip_address)
        VALUES (?, ?, ?, ?, ?)
    """, (session_token, user["admin_id"], now_str, expires_at, ip_address))

    # Update last login timestamp
    cursor.execute("UPDATE admin_users SET last_login = ? WHERE admin_id = ?", (now_str, user["admin_id"]))

    # Write audit log to admin.db
    cursor.execute("""
        INSERT INTO admin_audit_logs (admin_id, username, action, target_ticket_id, details, ip_address)
        VALUES (?, ?, 'LOGIN', NULL, 'Successful administrator login', ?)
    """, (user["admin_id"], user["username"], ip_address))

    conn.commit()
    conn.close()

    return {
        "success": True,
        "session_token": session_token,
        "expires_at": expires_at,
        "admin": {
            "admin_id": user["admin_id"],
            "username": user["username"],
            "email": user["email"],
            "role": user["role"],
            "full_name": user["full_name"],
            "department": user["department"]
        }
    }


def validate_admin_session(session_token: str) -> Optional[Dict[str, Any]]:
    """
    Validates a session token against admin.db. Returns administrator details if active.
    """
    if not session_token:
        return None

    conn = get_admin_db_connection()
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        SELECT s.session_token, s.admin_id, s.expires_at,
               u.username, u.email, u.role, u.full_name, u.department, u.is_active
        FROM admin_sessions s
        JOIN admin_users u ON s.admin_id = u.admin_id
        WHERE s.session_token = ? AND s.expires_at > ? AND u.is_active = 1
    """, (session_token, now_str))
    row = cursor.fetchone()
    conn.close()

    if row:
        return dict(row)
    return None


def terminate_admin_session(session_token: str) -> bool:
    """Invalidates an active admin session and logs the logout event in admin.db."""
    conn = get_admin_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT admin_id FROM admin_sessions WHERE session_token = ?", (session_token,))
    row = cursor.fetchone()

    if row:
        admin_id = row["admin_id"]
        cursor.execute("DELETE FROM admin_sessions WHERE session_token = ?", (session_token,))
        cursor.execute("""
            INSERT INTO admin_audit_logs (admin_id, username, action, details)
            VALUES (?, 'admin', 'LOGOUT', 'Admin session terminated')
        """, (admin_id,))
        conn.commit()
        conn.close()
        return True

    conn.close()
    return False


def log_admin_action(admin_id: str, username: str, action: str, target_ticket_id: Optional[str] = None, details: str = "", ip_address: str = "127.0.0.1"):
    """Records an administrative action into admin_audit_logs in admin.db."""
    conn = get_admin_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO admin_audit_logs (admin_id, username, action, target_ticket_id, details, ip_address)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (admin_id, username, action, target_ticket_id, details, ip_address))
    conn.commit()
    conn.close()


def get_recent_admin_audit_logs(limit: int = 50) -> List[Dict[str, Any]]:
    """Retrieves the recent administrative audit entries from admin.db."""
    conn = get_admin_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT log_id, admin_id, username, action, target_ticket_id, details, ip_address, timestamp
        FROM admin_audit_logs
        ORDER BY timestamp DESC
        LIMIT ?
    """, (limit,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def create_portal_credentials(
    portal_type: str = "academic",
    full_name: Optional[str] = None,
    department: Optional[str] = None,
    assigned_ticket_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Provisions dedicated access credentials in admin.db for either:
    1. Academic Portal: Academic Teacher / Academic Course Evaluator
    2. Administrative Portal: Support Officer / Exam Controller Administrator
    """
    conn = get_admin_db_connection()
    cursor = conn.cursor()

    suffix = secrets.token_hex(2)
    is_academic = portal_type.lower() in ["academic", "teacher", "evaluator", "curriculum"]

    if is_academic:
        admin_id = f"ACAD-{secrets.token_hex(3).upper()}"
        username = f"acad_teacher_{suffix}"
        email = f"teacher_{suffix}@faculty.lpu.in"
        role = "AcademicTeacher"
        name = full_name or "Academic Evaluation Officer"
        dept = department or "Academic Affairs & Timetable Coordination"
        target_portal = "Academic Portal (/portal/academic)"
        portal_key = "ACADEMIC_PORTAL"
    else:
        admin_id = f"ADM-{secrets.token_hex(3).upper()}"
        username = f"admin_officer_{suffix}"
        email = f"officer_{suffix}@admin.lpu.in"
        role = "Administrator"
        name = full_name or "Administrative Service Officer"
        dept = department or "Central Administration & Helpdesk"
        target_portal = "Administrator Portal (/portal/admin)"
        portal_key = "ADMINISTRATIVE_PORTAL"

    raw_password = f"{'Acad' if is_academic else 'Admin'}@RMS2026_{suffix}!"
    p_hash, salt = hash_password(raw_password)

    cursor.execute("""
        INSERT INTO admin_users (admin_id, username, email, password_hash, salt, role, full_name, department, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
    """, (admin_id, username, email, p_hash, salt, role, name, dept))

    log_details = f"Provisioned credentials for {target_portal} to handle ticket {assigned_ticket_id or 'GENERAL'}"
    cursor.execute("""
        INSERT INTO admin_audit_logs (admin_id, username, action, target_ticket_id, details)
        VALUES (?, ?, 'CREDENTIAL_PROVISIONING', ?, ?)
    """, (admin_id, username, assigned_ticket_id, log_details))

    conn.commit()
    conn.close()

    return {
        "admin_id": admin_id,
        "username": username,
        "email": email,
        "temporary_password": raw_password,
        "role": role,
        "full_name": name,
        "department": dept,
        "target_portal": target_portal,
        "portal_key": portal_key
    }


def record_central_test_log(
    query_id: str,
    student_id: str,
    student_query: str,
    response_text: str,
    routing_path: str,
    decision_rationale: str,
    processing_time_seconds: float,
    escalation_status: str = "RESOLVED",
    assigned_portal: Optional[str] = None,
    created_credentials: Optional[Dict[str, Any]] = None,
    bottleneck_analysis: Optional[str] = None
) -> Dict[str, Any]:
    """
    Maintains a central test log in admin.db detailing end-to-end query handling,
    routing trajectory, decision criteria, and latency diagnostics.
    """
    import json
    conn = get_admin_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS central_test_logs (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        query_id TEXT UNIQUE,
        student_id TEXT,
        student_query TEXT NOT NULL,
        response_text TEXT NOT NULL,
        routing_path TEXT NOT NULL,
        decision_rationale TEXT NOT NULL,
        processing_time_seconds REAL NOT NULL,
        escalation_status TEXT,
        assigned_portal TEXT,
        created_credentials TEXT,
        bottleneck_analysis TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cred_json = json.dumps(created_credentials) if created_credentials else None

    cursor.execute("""
        INSERT OR REPLACE INTO central_test_logs (
            query_id, student_id, student_query, response_text,
            routing_path, decision_rationale, processing_time_seconds,
            escalation_status, assigned_portal, created_credentials, bottleneck_analysis
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        query_id, student_id, student_query, response_text,
        routing_path, decision_rationale, round(processing_time_seconds, 4),
        escalation_status, assigned_portal, cred_json, bottleneck_analysis
    ))

    conn.commit()
    conn.close()
    return {"status": "SUCCESS", "query_id": query_id}


# Initialize database automatically upon module import
init_admin_database()
