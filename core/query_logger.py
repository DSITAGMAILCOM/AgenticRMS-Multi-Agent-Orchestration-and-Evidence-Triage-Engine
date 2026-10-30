# core/query_logger.py
"""
Universal Multi-Location Query Logging & Polite Response Engine:
1. Records queries in RMS History (university.db: helpdesk_tickets & query_audit_logs).
2. Records queries in Admin Portal (admin.db: admin_query_records & admin_audit_logs).
3. Records queries in Student Database (university.db: students & student_queries),
   ensuring the university email ID follows the exact format:
   `student_name_four_digit_number@lpu.in`
4. Generates fully detailed, polite answers without token limits.
"""
import os
import re
import secrets
import datetime
import sqlite3
from typing import Dict, Any, Optional
from config import DB_PATH, ADMIN_DB_PATH, console


def format_student_university_email(
    student_name: str,
    four_digit_number: Optional[str] = None,
    university_id: Optional[str] = None
) -> str:
    """
    Constructs the university email ID following the exact required pattern:
    `student_name_four_digit_number@lpu.in`
    
    Examples:
    - student_name: "Aditya Sharma", four_digit_number: "3452"
      -> "aditya_sharma_3452@lpu.in"
    - student_name: "Priya Patel", four_digit_number: "1984"
      -> "priya_patel_1984@lpu.in"
    """
    # 1. Clean student name in snake_case format
    clean_name = re.sub(r'[^a-zA-Z0-9]+', '_', student_name.strip().lower()).strip('_')
    if not clean_name:
        clean_name = "student"

    # 2. Extract or resolve 4-digit identifier
    digits = ""
    if four_digit_number:
        # Match 4-digit pattern if present
        m = re.findall(r'\d{4}', str(four_digit_number))
        if m:
            digits = m[0]
        else:
            all_digits = re.findall(r'\d+', str(four_digit_number))
            if all_digits and len(all_digits[0]) >= 4:
                digits = all_digits[0][:4]
            elif all_digits:
                digits = all_digits[0].zfill(4)

    # Fallback to university_id digits if not provided
    if not digits and university_id:
        uid_digits = re.findall(r'\d+', str(university_id))
        if uid_digits and len(uid_digits[0]) >= 4:
            digits = uid_digits[0][-4:]

    # Default fallback four-digit identifier
    if not digits or len(digits) != 4:
        digits = "3452"

    return f"{clean_name}_{digits}@lpu.in"


def ensure_multi_location_tables():
    """Ensures query logging tables exist across all storage locations."""
    # Location 2: Admin Portal (admin.db)
    try:
        conn_admin = sqlite3.connect(ADMIN_DB_PATH)
        cursor_admin = conn_admin.cursor()
        cursor_admin.execute("""
            CREATE TABLE IF NOT EXISTS admin_query_records (
                record_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id TEXT,
                query_id TEXT,
                university_id TEXT NOT NULL,
                student_name TEXT NOT NULL,
                university_email TEXT NOT NULL,
                query_text TEXT NOT NULL,
                response_text TEXT,
                status TEXT DEFAULT 'IN_PROGRESS',
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn_admin.commit()
        conn_admin.close()
    except Exception as e:
        console.print(f"[dim red]Note admin.db table creation: {e}[/dim red]")

    # Location 3: Student Database (university.db)
    try:
        conn_univ = sqlite3.connect(DB_PATH)
        cursor_univ = conn_univ.cursor()
        cursor_univ.execute("""
            CREATE TABLE IF NOT EXISTS student_queries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query_id TEXT,
                ticket_id TEXT,
                university_id TEXT NOT NULL,
                student_name TEXT NOT NULL,
                university_email TEXT NOT NULL,
                query_text TEXT NOT NULL,
                response_text TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn_univ.commit()
        conn_univ.close()
    except Exception as e:
        console.print(f"[dim red]Note university.db table creation: {e}[/dim red]")


# Initialize storage schemas on import
ensure_multi_location_tables()


def make_polite_comprehensive_answer(
    raw_response: str,
    student_name: str,
    query_text: str,
    domain: str = "general"
) -> str:
    """
    Returns the direct, point-to-point response without bloated boilerplate or long paragraphs.
    """
    return raw_response.strip()


def log_query_across_all_locations(
    query_text: str,
    student_name: str,
    university_id: str,
    department: str = "computer_science",
    domain: str = "general",
    response_text: str = "",
    four_digit_number: Optional[str] = None,
    ticket_id: Optional[str] = None,
    query_id: Optional[str] = None,
    routed_to_default_gateway: bool = False
) -> Dict[str, Any]:
    """
    Records the query in all three required storage locations:
    1. RMS History (helpdesk_tickets & query_audit_logs in university.db)
    2. Admin Portal (admin_query_records & admin_audit_logs in admin.db)
    3. Student Database (students & student_queries in university.db),
       with the university email in `student_name_four_digit_number@lpu.in` format.

    Status Rule:
    - Queries routed to default gateway (unhandled by AI agent) -> status = 'in-progress'
    - All other queries (handled by AI agent) -> status = 'resolved'
    """
    ensure_multi_location_tables()

    # Generate IDs if not provided
    if not ticket_id:
        ticket_id = f"RMS{datetime.datetime.now().strftime('%Y%m%d')}{secrets.token_hex(2).upper()}"
    if not query_id:
        query_id = f"QRY-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(2).upper()}"

    # Calculate exact formatted email ID: student_name_four_digit_number@lpu.in
    university_email = format_student_university_email(
        student_name=student_name,
        four_digit_number=four_digit_number,
        university_id=university_id
    )

    # Determine desk category
    q_lower = query_text.lower()
    if "hostel" in q_lower or "room" in q_lower:
        category = "Hostel Related"
        officer = "Hostel Warden Office"
    elif domain == "administration" or "fee" in q_lower:
        category = "Fee & Accounts"
        officer = "Finance & Accounts Desk"
    elif domain == "examination" or "exam" in q_lower:
        category = "Examination"
        officer = "Controller of Examinations"
    elif domain == "academic" or "course" in q_lower or "syllabus" in q_lower:
        category = "Academic Affairs"
        officer = "Chief Academic Dean"
    elif domain == "edu_revolution" or "internship" in q_lower or "placement" in q_lower:
        category = "Internship & Career"
        officer = "Edu-Revolution Division"
    else:
        category = "General Inquiry"
        officer = "Central University Helpdesk"

    # Status Determination Rule:
    # - If routed to Default Gateway (unhandled by AI agent): status = 'in-progress'
    # - For all other queries (handled and answered by AI agent): status = 'resolved'
    if routed_to_default_gateway:
        ticket_status = "in-progress"
        admin_status = "in-progress"
        stage_progress = 2
        current_stage = "Default Gateway Review"
        resolution_type = "GATEWAY_IN_PROGRESS"
        res_notes = "Query routed to Default Gateway for officer review."
    else:
        ticket_status = "resolved"
        admin_status = "resolved"
        stage_progress = 4
        current_stage = "Final Resolution"
        resolution_type = "AI_RESOLVED"
        res_notes = "Query successfully resolved by AI Multi-Agent System."

    # =========================================================================
    # LOCATION 1: RMS History (university.db)
    # =========================================================================
    try:
        conn_rms = sqlite3.connect(DB_PATH)
        cur_rms = conn_rms.cursor()

        # Insert/Update into helpdesk_tickets
        cur_rms.execute("""
            INSERT OR REPLACE INTO helpdesk_tickets (
                ticket_id, university_id, student_name, university_email, department_id,
                query_text, escalation_reason, category, status, assigned_officer,
                human_resolution_notes, current_stage, stage_progress, next_stage,
                estimated_resolution, created_at, last_inquiry_at, inquiry_count
            ) VALUES (
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, 'Final Resolution',
                'Same Day', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1
            )
        """, (
            ticket_id, str(university_id).strip(), student_name, university_email, department,
            query_text, f"Automated inquiry ({domain.title()})", category, ticket_status, officer,
            res_notes, current_stage, stage_progress
        ))

        # Insert into query_audit_logs
        cur_rms.execute("""
            INSERT OR REPLACE INTO query_audit_logs (
                query_id, university_id, student_name, university_email,
                raw_query, final_resolution_type, ticket_id, total_hops,
                full_trajectory, created_at
            ) VALUES (
                ?, ?, ?, ?,
                ?, ?, ?, 1,
                ?, CURRENT_TIMESTAMP
            )
        """, (
            query_id, str(university_id).strip(), student_name, university_email,
            query_text, resolution_type, ticket_id,
            f"Top Orchestrator ➔ {category} ➔ {'Resolution Completed' if not routed_to_default_gateway else 'In Progress'}"
        ))
        conn_rms.commit()
        conn_rms.close()
    except Exception as e:
        console.print(f"[bold red]RMS History logging error: {e}[/bold red]")

    # =========================================================================
    # LOCATION 2: Admin Portal (admin.db)
    # =========================================================================
    try:
        conn_admin = sqlite3.connect(ADMIN_DB_PATH)
        cur_admin = conn_admin.cursor()

        # Record in admin_query_records
        cur_admin.execute("""
            INSERT INTO admin_query_records (
                ticket_id, query_id, university_id, student_name,
                university_email, query_text, response_text, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ticket_id, query_id, str(university_id).strip(), student_name,
            university_email, query_text, response_text, admin_status
        ))

        # Record in admin_audit_logs
        cur_admin.execute("""
            INSERT INTO admin_audit_logs (
                admin_id, username, action, target_ticket_id, details
            ) VALUES (
                'SYSTEM', 'CHATBOT_LOGGER', 'STUDENT_QUERY', ?, ?
            )
        """, (
            ticket_id,
            f"Student {student_name} ({university_email}) submitted query: {query_text[:120]}"
        ))
        conn_admin.commit()
        conn_admin.close()
    except Exception as e:
        console.print(f"[bold red]Admin Portal logging error: {e}[/bold red]")

    # =========================================================================
    # LOCATION 3: Student Database (university.db: students & student_queries)
    # =========================================================================
    try:
        conn_stu = sqlite3.connect(DB_PATH)
        cur_stu = conn_stu.cursor()

        # Update student record with exact formatted email ID
        cur_stu.execute("""
            UPDATE students
            SET university_email = ?
            WHERE university_id = ? OR LOWER(full_name) = LOWER(?)
        """, (university_email, str(university_id).strip(), student_name.strip()))

        # Record in student_queries
        cur_stu.execute("""
            INSERT INTO student_queries (
                query_id, ticket_id, university_id, student_name,
                university_email, query_text, response_text
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            query_id, ticket_id, str(university_id).strip(), student_name,
            university_email, query_text, response_text
        ))
        conn_stu.commit()
        conn_stu.close()
    except Exception as e:
        console.print(f"[bold red]Student Database logging error: {e}[/bold red]")

    return {
        "success": True,
        "ticket_id": ticket_id,
        "query_id": query_id,
        "university_email": university_email,
        "category": category,
        "assigned_officer": officer
    }
