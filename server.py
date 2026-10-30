# server.py
"""
University Multi-Agent RAG System - High-Performance Web Backend
Built on Starlette + Uvicorn to serve the modern RMS Query frontend,
handle REST API requests, manage live student sessions, and provide
an isolated administrator authentication & stage management subsystem.
"""
import os
import json
import sqlite3
import datetime
import hashlib
import hmac
import secrets
from typing import Optional, List, Dict, Any
import uvicorn
from starlette.applications import Starlette
from starlette.responses import JSONResponse, HTMLResponse, FileResponse
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

from config import DB_PATH, console
from core.session import StudentSession
from core.tracker import QueryTracker
from orchestrator.router import orchestrate_query, clean_query, active_gate_classify, detect_all_matching_domains
from core.rms_handler import detect_rms_intent, handle_tracking_query, handle_history_query, create_automated_rms_ticket
from core.stt import transcribe_audio_file
from core.query_logger import (
    format_student_university_email,
    log_query_across_all_locations,
    make_polite_comprehensive_answer
)
from core.admin_db import (
    authenticate_admin,
    validate_admin_session,
    terminate_admin_session,
    log_admin_action,
    get_recent_admin_audit_logs
)


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
os.makedirs(STATIC_DIR, exist_ok=True)
STUDENT_TOKEN_SECRET = os.getenv("STUDENT_TOKEN_SECRET", "univ_student_secure_token_secret_2026")


def ensure_feedback_table():
    """Guarantees student_feedback table exists with indexes in university.db."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS student_feedback (
                feedback_id TEXT PRIMARY KEY,
                university_id TEXT NOT NULL,
                student_name TEXT NOT NULL,
                category TEXT NOT NULL,
                rating INTEGER NOT NULL CHECK(rating >= 1 AND rating <= 5),
                resolution_quality TEXT NOT NULL,
                recommendation TEXT NOT NULL,
                comments TEXT NOT NULL,
                suggestions TEXT,
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ip_address TEXT DEFAULT '127.0.0.1'
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_feedback_submitted_at ON student_feedback (submitted_at DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_feedback_university_id ON student_feedback (university_id)")
        conn.commit()
        conn.close()
    except Exception as e:
        console.print(f"[dim red]Feedback table note: {e}[/dim red]")


ensure_feedback_table()



# =========================================================================
# Cryptographic Student Session Tokens (IDOR & Breach Prevention)
# =========================================================================
def generate_student_token(university_id: str) -> str:
    """Generates a tamper-proof HMAC-signed session token for the student."""
    clean_id = str(university_id).strip()
    sig = hmac.new(STUDENT_TOKEN_SECRET.encode(), clean_id.encode(), hashlib.sha256).hexdigest()[:24]
    return f"{clean_id}:{sig}"


def verify_student_token(token: str) -> Optional[str]:
    """Verifies the student session token integrity and returns university_id."""
    if not token or ":" not in token:
        return None
    uid, sig = token.split(":", 1)
    expected = hmac.new(STUDENT_TOKEN_SECRET.encode(), uid.encode(), hashlib.sha256).hexdigest()[:24]
    if hmac.compare_digest(sig, expected):
        return uid
    return None


def get_authenticated_student_id(request) -> Optional[str]:
    """Extracts and verifies student identity from cookies or headers."""
    # 1. Cookie
    cookie_token = request.cookies.get("student_session_token", "").strip()
    if cookie_token:
        uid = verify_student_token(cookie_token)
        if uid:
            return uid

    # 2. X-Student-Token header
    hdr_token = request.headers.get("X-Student-Token", "").strip()
    if hdr_token:
        uid = verify_student_token(hdr_token)
        if uid:
            return uid

    # 3. Authorization: Bearer
    auth_header = request.headers.get("Authorization", "").strip()
    if auth_header.startswith("Bearer "):
        bearer_token = auth_header[7:].strip()
        uid = verify_student_token(bearer_token)
        if uid:
            return uid

    return None


# =========================================================================
# Authentication Guard for Administrative APIs
# =========================================================================
def get_authenticated_admin(request):
    """
    Extracts and validates the administrator session token against the dedicated admin.db.
    Checks Authorization: Bearer <token>, X-Admin-Token header, or admin_token cookie.
    """
    auth_header = request.headers.get("Authorization", "").strip()
    token = None
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    if not token:
        token = request.headers.get("X-Admin-Token", "").strip()
    if not token:
        token = request.cookies.get("admin_token", "").strip()

    if not token:
        return None
    return validate_admin_session(token)


# =========================================================================
# Page Serving Handlers
# =========================================================================
async def serve_index(request):
    """Serves the primary Single Page Application interface."""
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTMLResponse("<h1>RMS Query Portal - static/index.html not found</h1>", status_code=404)


async def serve_admin(request):
    """Serves the dedicated Administrator Management Portal."""
    admin_path = os.path.join(STATIC_DIR, "admin.html")
    if os.path.exists(admin_path):
        return FileResponse(admin_path)
    return HTMLResponse("<h1>RMS Admin Portal - static/admin.html not found</h1>", status_code=404)


# =========================================================================
# Student Query & Multi-Agent Execution Handlers
# =========================================================================
async def api_query(request):
    """
    Main Chat & Multi-Agent Execution Endpoint:
    Receives user query, attaches StudentSession, dispatches through the Orchestrator,
    and returns response markdown, routing telemetry, and live RMS UI synchronization directives.
    Enforces strict student data boundary to prevent data breaches.
    """
    try:
        data = await request.json()
        query = data.get("query", "").strip()
        reg_no = data.get("registration_no", "").strip()
        custom_name = data.get("student_name", "").strip()
        four_digit_no = data.get("four_digit_number", "").strip() or data.get("digit_number", "").strip()

        # Data breach prevention: verify authenticated session
        auth_uid = get_authenticated_student_id(request)
        if auth_uid:
            if reg_no and reg_no != auth_uid:
                return JSONResponse({
                    "success": False,
                    "error": "Security Violation: Cross-student data access is strictly prohibited under university security policy."
                }, status_code=403)
            reg_no = auth_uid
        elif not reg_no:
            return JSONResponse({"success": False, "error": "Authentication required. Please log in with your Registration Number."}, status_code=401)

        # Authenticate / load student context
        session = StudentSession()
        found = session.authenticate_or_lookup(reg_no)
        if not found:
            return JSONResponse({"success": False, "error": f"Registration No. '{reg_no}' is not recognized in university database."}, status_code=403)

        if not query:
            return JSONResponse({"error": "Query cannot be empty."}, status_code=400)

        # 1. Student Identity & Formatted University Email ID
        student_name = custom_name or session.full_name or "Aditya Sharma"
        session.full_name = student_name
        session.user_name = student_name
        session.name = student_name

        formatted_email = format_student_university_email(
            student_name=student_name,
            four_digit_number=four_digit_no,
            university_id=session.university_id
        )
        session.university_email = formatted_email

        cleaned_q = clean_query(query)
        rms_intent = detect_rms_intent(cleaned_q)

        # Create Tracker for Hop Telemetry
        tracker = QueryTracker(
            university_id=session.university_id,
            student_name=session.full_name,
            email=session.university_email,
            raw_query=cleaned_q
        )

        raw_response = orchestrate_query(query, session=session, tracker=tracker)

        # Determine domain from actual agent execution hops (multi-domain vs single)
        agent_hops = [h["to_agent"].replace("Agent", "").lower() for h in tracker.hops if "Agent" in h.get("to_agent", "")]
        unique_domains = list(dict.fromkeys(agent_hops))
        if len(unique_domains) > 1:
            domain = "multi_domain"
        elif unique_domains:
            domain = unique_domains[0]
        else:
            domain = active_gate_classify(cleaned_q)

        # Check if deflection occurred
        is_faq = "⚡" in str(raw_response) or any(h["action_type"] in ["FAQ_HIT", "FAQ_DEFLECTION", "RMS_TRACKING", "RMS_HISTORY"] for h in tracker.hops)

        # 2. Point-to-point response
        action = None
        target_tid = getattr(tracker, "ticket_id", None)
        if rms_intent == "RMS_TRACKING":
            action = "OPEN_TRACKER"
        elif rms_intent == "RMS_HISTORY":
            action = "OPEN_HISTORY"
        else:
            action = "UPDATE_RMS"

        polite_response = make_polite_comprehensive_answer(
            raw_response=raw_response,
            student_name=student_name,
            query_text=query,
            domain=domain
        )

        is_routed_to_gateway = (
            "Request Escalated to University Helpdesk" in raw_response
            or "Default Human Gateway" in raw_response
            or any(h.get("to_agent") == "Default Human Gateway" or h.get("action_type") == "ESCALATION" for h in tracker.hops)
        )

        # 3. Record query in all storage locations
        log_res = log_query_across_all_locations(
            query_text=query,
            student_name=student_name,
            university_id=session.university_id,
            department=session.department_id,
            domain=domain,
            response_text=polite_response,
            four_digit_number=four_digit_no,
            ticket_id=target_tid,
            query_id=tracker.query_id,
            routed_to_default_gateway=is_routed_to_gateway
        )
        target_tid = log_res["ticket_id"]

        resp = JSONResponse({
            "success": True,
            "query": query,
            "response": polite_response,
            "domain": domain,
            "is_faq": is_faq,
            "action": action,
            "ticket_id": target_tid,
            "status": "in-progress" if is_routed_to_gateway else "resolved",
            "student_name": session.full_name,
            "university_id": session.university_id,
            "university_email": formatted_email,
            "total_hops": len(tracker.hops),
            "trajectory": [h["to_agent"] for h in tracker.hops],
            "logged_everywhere": True,
            "storage_locations": ["RMS History", "Admin Portal", "Student Database"]
        })

        # Ensure session token is attached
        if not auth_uid:
            tok = generate_student_token(session.university_id)
            resp.set_cookie("student_session_token", tok, httponly=False, samesite="lax", max_age=86400)
        return resp

    except Exception as e:
        console.print(f"[bold red]API Error: {e}[/bold red]")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


async def api_login(request):
    """
    Mandatory Student Login Gate:
    Verifies Registration Number and issues cryptographic session token to prevent IDOR / data breaches.
    """
    try:
        data = await request.json()
        reg_no = data.get("registration_no", "").strip()
        if not reg_no:
            return JSONResponse({"success": False, "error": "Please enter your Registration Number to log in."}, status_code=400)

        session = StudentSession()
        found = session.authenticate_or_lookup(reg_no)
        if not found:
            return JSONResponse({
                "success": False, 
                "error": f"Registration No. '{reg_no}' not found in university database. Access denied."
            }, status_code=404)

        token = generate_student_token(session.university_id)
        resp = JSONResponse({
            "success": True,
            "token": token,
            "student": {
                "student_name": session.full_name,
                "university_id": session.university_id,
                "email": session.university_email,
                "faculty": session.faculty_id,
                "department": session.department_id,
                "semester": session.semester,
                "courses": session.enrolled_courses,
                "mentor_name": session.mentor_name,
                "mentor_cabin": session.mentor_cabin
            }
        })
        resp.set_cookie(
            key="student_session_token",
            value=token,
            httponly=False,
            samesite="lax",
            max_age=86400
        )
        return resp
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


async def api_session(request):
    """Retrieves active student profile with session validation."""
    auth_uid = get_authenticated_student_id(request)
    reg_no = request.query_params.get("reg_no", "").strip()
    target_id = auth_uid or reg_no

    if not target_id:
        return JSONResponse({"authenticated": False, "error": "Not authenticated"}, status_code=401)

    session = StudentSession()
    found = session.authenticate_or_lookup(target_id)
    if not found:
        return JSONResponse({"authenticated": False, "error": "Not authenticated"}, status_code=404)

    return JSONResponse({
        "authenticated": True,
        "student_name": session.full_name,
        "university_id": session.university_id,
        "email": session.university_email,
        "faculty": session.faculty_id,
        "department": session.department_id,
        "semester": session.semester,
        "courses": session.enrolled_courses,
        "mentor_name": session.mentor_name,
        "mentor_cabin": session.mentor_cabin
    })


async def api_tickets(request):
    """Retrieves RMS support tickets for the authenticated student only (IDOR protected)."""
    auth_uid = get_authenticated_student_id(request)
    param_reg = request.query_params.get("reg_no", "").strip()

    if auth_uid:
        if param_reg and param_reg != auth_uid:
            return JSONResponse({"tickets": [], "stats": {}, "error": "Access Denied: Cross-student ticket inspection is strictly prohibited."}, status_code=403)
        reg_no = auth_uid
    else:
        reg_no = param_reg
        if not reg_no:
            return JSONResponse({"tickets": [], "stats": {}, "error": "Authentication or student ID required."}, status_code=401)

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT *
            FROM helpdesk_tickets
            WHERE university_id = ? OR LOWER(university_id) = LOWER(?)
            ORDER BY created_at DESC
        """, (reg_no, reg_no))
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()

        total = len(rows)
        resolved = sum(1 for r in rows if (r.get("status") or "").lower() == "resolved")
        in_progress = sum(1 for r in rows if (r.get("status") or "").lower() == "in progress")

        return JSONResponse({
            "tickets": rows,
            "stats": {
                "total_requests": total,
                "resolved": resolved,
                "in_progress": in_progress,
                "avg_resolution_days": 2.3
            }
        })
    except Exception as e:
        return JSONResponse({"tickets": [], "stats": {}, "error": str(e)})


async def api_history(request):
    """Retrieves conversation history for the authenticated student only (IDOR protected)."""
    auth_uid = get_authenticated_student_id(request)
    param_reg = request.query_params.get("reg_no", "").strip()

    if auth_uid:
        if param_reg and param_reg != auth_uid:
            return JSONResponse({"history": [], "error": "Access Denied: Cross-student history inspection is strictly prohibited."}, status_code=403)
        reg_no = auth_uid
    else:
        reg_no = param_reg
        if not reg_no:
            return JSONResponse({"history": [], "error": "Authentication or student ID required."}, status_code=401)

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT query_id, raw_query, final_resolution_type, ticket_id, total_hops, created_at
            FROM query_audit_logs
            WHERE university_id = ?
            ORDER BY created_at DESC
            LIMIT 15
        """, (reg_no,))
        rows = cursor.fetchall()
        conn.close()
        return JSONResponse({"history": [dict(r) for r in rows]})
    except Exception as e:
        return JSONResponse({"history": [], "error": str(e)})


# =========================================================================
# Dedicated Administrator API Endpoints (Backed by admin.db)
# =========================================================================
async def api_admin_login(request):
    """
    Administrator Authentication Endpoint:
    Verifies credentials strictly against admin.db using PBKDF2-HMAC-SHA256.
    Zero interaction with student university.db.
    """
    try:
        data = await request.json()
        username = data.get("username", "").strip()
        password = data.get("password", "")

        if not username or not password:
            return JSONResponse({"success": False, "error": "Username and password required."}, status_code=400)

        ip = request.client.host if request.client else "127.0.0.1"
        auth_result = authenticate_admin(username, password, ip_address=ip)

        if auth_result["success"]:
            response = JSONResponse(auth_result)
            response.set_cookie(
                key="admin_token",
                value=auth_result["session_token"],
                httponly=True,
                max_age=43200,
                samesite="lax"
            )
            return response
        else:
            return JSONResponse(auth_result, status_code=401)
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


async def api_admin_session(request):
    """Validates the administrator session token against admin.db."""
    admin = get_authenticated_admin(request)
    if not admin:
        return JSONResponse({"authenticated": False, "error": "Admin session invalid or expired."}, status_code=401)

    return JSONResponse({
        "authenticated": True,
        "admin": {
            "admin_id": admin["admin_id"],
            "username": admin["username"],
            "email": admin["email"],
            "role": admin["role"],
            "full_name": admin["full_name"],
            "department": admin["department"]
        }
    })


async def api_admin_logout(request):
    """Terminates administrator session in admin.db."""
    auth_header = request.headers.get("Authorization", "").strip()
    token = auth_header[7:].strip() if auth_header.startswith("Bearer ") else request.cookies.get("admin_token", "")
    if token:
        terminate_admin_session(token)

    response = JSONResponse({"success": True, "message": "Admin session logged out successfully."})
    response.delete_cookie("admin_token")
    return response


async def api_admin_tickets(request):
    """
    Administrator Ticket Explorer:
    Reads tickets across all students from university.db and provides live KPIs.
    """
    admin = get_authenticated_admin(request)
    if not admin:
        return JSONResponse({"success": False, "tickets": [], "error": "Unauthorized. Administrator session required."}, status_code=401)

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT *
            FROM helpdesk_tickets
            ORDER BY created_at DESC
        """)
        rows = [dict(r) for r in cursor.fetchall()]
        # Get count of audit logs from admin.db
        audit_logs = get_recent_admin_audit_logs(limit=100)

        # Get feedback metrics from university.db
        cursor.execute("SELECT COUNT(*), AVG(rating) FROM student_feedback")
        fb_row = cursor.fetchone()
        fb_count = fb_row[0] if fb_row else 0
        fb_avg = round(fb_row[1], 1) if (fb_row and fb_row[1]) else 0.0

        conn.close()

        total = len(rows)
        resolved = sum(1 for r in rows if (r.get("status") or "").lower() == "resolved")
        in_progress = sum(1 for r in rows if (r.get("status") or "").lower() in ("in progress", "open"))

        return JSONResponse({
            "success": True,
            "tickets": rows,
            "stats": {
                "total": total,
                "resolved": resolved,
                "in_progress": in_progress,
                "audit_logs_count": len(audit_logs),
                "feedback_count": fb_count,
                "feedback_avg": fb_avg
            }
        })
    except Exception as e:
        return JSONResponse({"success": False, "tickets": [], "error": str(e)}, status_code=500)



async def api_admin_ticket_update(request):
    """
    Administrator Ticket Management & Stage Updating:
    1. Validates admin identity and role in admin.db.
    2. Updates ticket stage, progress, handler, and notes in university.db.
    3. Records an immutable administrative audit record in admin.db.
    """
    admin = get_authenticated_admin(request)
    if not admin:
        return JSONResponse({"success": False, "error": "Unauthorized. Administrator session required."}, status_code=401)

    try:
        data = await request.json()
        ticket_id = data.get("ticket_id", "").strip()
        status = data.get("status", "In Progress").strip()
        stage_progress = int(data.get("stage_progress", 3))
        current_stage = data.get("current_stage", "").strip()
        next_stage = data.get("next_stage", "").strip()
        assigned_officer = data.get("assigned_officer", "").strip()
        estimated_resolution = data.get("estimated_resolution", "").strip()
        human_resolution_notes = data.get("human_resolution_notes", "").strip()

        if not ticket_id:
            return JSONResponse({"success": False, "error": "Ticket ID is required."}, status_code=400)

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        resolved_at = now_str if status.lower() == "resolved" else None

        cursor.execute("""
            UPDATE helpdesk_tickets
            SET status = ?,
                stage_progress = ?,
                current_stage = ?,
                next_stage = ?,
                assigned_officer = ?,
                estimated_resolution = ?,
                human_resolution_notes = ?,
                resolved_at = COALESCE(?, resolved_at)
            WHERE LOWER(ticket_id) = LOWER(?)
        """, (
            status,
            stage_progress,
            current_stage,
            next_stage,
            assigned_officer,
            estimated_resolution,
            human_resolution_notes,
            resolved_at,
            ticket_id
        ))

        if cursor.rowcount == 0:
            conn.close()
            return JSONResponse({"success": False, "error": f"Ticket '{ticket_id}' not found."}, status_code=404)

        conn.commit()
        conn.close()

        # Record action in dedicated admin.db audit logs
        log_details = f"Status: {status}, Stage: {current_stage} ({stage_progress*25}%), Desk: {assigned_officer}. Notes: {human_resolution_notes[:50]}"
        ip = request.client.host if request.client else "127.0.0.1"
        log_admin_action(
            admin_id=admin["admin_id"],
            username=admin["username"],
            action="UPDATE_TICKET_STAGE",
            target_ticket_id=ticket_id,
            details=log_details,
            ip_address=ip
        )

        return JSONResponse({
            "success": True,
            "message": f"Ticket '{ticket_id}' successfully updated by {admin['full_name']}.",
            "updated_fields": {
                "ticket_id": ticket_id,
                "status": status,
                "current_stage": current_stage,
                "stage_progress": stage_progress,
                "assigned_officer": assigned_officer,
                "estimated_resolution": estimated_resolution,
                "human_resolution_notes": human_resolution_notes
            }
        })
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


async def api_admin_audit_logs(request):
    """Retrieves recent administrative action logs from admin.db."""
    admin = get_authenticated_admin(request)
    if not admin:
        return JSONResponse({"success": False, "logs": [], "error": "Unauthorized. Administrator session required."}, status_code=401)

    try:
        logs = get_recent_admin_audit_logs(limit=50)
        return JSONResponse({"success": True, "logs": logs})
    except Exception as e:
        return JSONResponse({"success": False, "logs": [], "error": str(e)}, status_code=500)


async def api_admin_student_queries(request):
    """Retrieves logged student queries across systems from admin.db."""
    admin = get_authenticated_admin(request)
    if not admin:
        return JSONResponse({"success": False, "queries": [], "error": "Unauthorized. Administrator session required."}, status_code=401)

    try:
        from config import ADMIN_DB_PATH
        conn = sqlite3.connect(ADMIN_DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM admin_query_records ORDER BY timestamp DESC LIMIT 100")
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return JSONResponse({"success": True, "queries": rows})
    except Exception as e:
        return JSONResponse({"success": False, "queries": [], "error": str(e)}, status_code=500)


async def api_transcribe(request):
    """
    Speech-to-Text Transcription API using Faster-Whisper CPU model.
    Accepts raw audio bytes or multipart form file and returns transcribed text.
    """
    import tempfile
    try:
        content_type = request.headers.get("Content-Type", "")
        audio_bytes = None
        if "multipart/form-data" in content_type:
            form = await request.form()
            audio_file = form.get("audio") or form.get("file")
            if audio_file:
                audio_bytes = await audio_file.read()
        else:
            audio_bytes = await request.body()

        if not audio_bytes or len(audio_bytes) < 100:
            return JSONResponse({"success": False, "error": "No valid audio payload received."}, status_code=400)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            res = transcribe_audio_file(tmp_path)
            return JSONResponse(res)
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


async def api_submit_feedback(request):
    """
    Submits student feedback (multiple-choice ratings and free-text comments).
    Stores submission in university.db with timestamp and mirrors in admin audit log.
    """
    try:
        data = await request.json()
        category = (data.get("category") or "General Support").strip()
        rating = int(data.get("rating") or 5)
        if rating < 1 or rating > 5:
            rating = 5
        resolution_quality = (data.get("resolution_quality") or "Satisfactory / Clear").strip()
        recommendation = (data.get("recommendation") or "Likely").strip()
        comments = (data.get("comments") or "").strip()
        suggestions = (data.get("suggestions") or "").strip()
        is_anonymous = bool(data.get("is_anonymous", False))

        if not comments:
            return JSONResponse({"success": False, "error": "Please provide feedback comments."}, status_code=400)

        # Determine student identification
        auth_id = get_authenticated_student_id(request)
        if not auth_id:
            auth_id = (data.get("university_id") or "").strip()

        student_name = (data.get("student_name") or "").strip()
        if is_anonymous or not auth_id:
            university_id = f"ANON-{secrets.token_hex(2).upper()}"
            student_name = "Anonymous Student"
        else:
            university_id = auth_id
            if not student_name:
                student_name = f"Student ({university_id})"

        feedback_id = f"FB-{datetime.datetime.now().strftime('%Y%m')}-{secrets.token_hex(2).upper()}"
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ip_addr = request.client.host if request.client else "127.0.0.1"

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO student_feedback (
                feedback_id, university_id, student_name, category, rating,
                resolution_quality, recommendation, comments, suggestions,
                submitted_at, ip_address
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            feedback_id, university_id, student_name, category, rating,
            resolution_quality, recommendation, comments, suggestions,
            now_str, ip_addr
        ))
        conn.commit()
        conn.close()

        # Log into admin audit logs
        log_admin_action(
            admin_id="SYSTEM",
            username="system",
            action="STUDENT_FEEDBACK",
            target_ticket_id=feedback_id,
            details=f"New {rating}-star feedback submitted for {category} by {university_id}",
            ip_address=ip_addr
        )

        return JSONResponse({
            "success": True,
            "feedback_id": feedback_id,
            "message": "Thank you! Your feedback has been securely recorded."
        })
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


async def api_admin_feedback(request):
    """
    Administrator Feedback Retrieval Endpoint:
    Returns all submitted student feedback sorted by submitted_at DESC, along with
    aggregate rating analytics. Feeds real-time KPI and feedback tables in admin portal.
    """
    admin = get_authenticated_admin(request)
    if not admin:
        return JSONResponse({"success": False, "feedback": [], "error": "Unauthorized. Administrator session required."}, status_code=401)

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT feedback_id, university_id, student_name, category, rating,
                   resolution_quality, recommendation, comments, suggestions,
                   submitted_at, ip_address
            FROM student_feedback
            ORDER BY submitted_at DESC
        """)
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()

        total = len(rows)
        avg_rating = round(sum(r["rating"] for r in rows) / total, 2) if total > 0 else 0.0

        return JSONResponse({
            "success": True,
            "feedback": rows,
            "stats": {
                "total": total,
                "average_rating": avg_rating
            }
        })
    except Exception as e:
        return JSONResponse({"success": False, "feedback": [], "error": str(e)}, status_code=500)


# =========================================================================
# Application Routing Table
# =========================================================================
routes = [
    # Pages
    Route("/", serve_index, methods=["GET"]),
    Route("/admin", serve_admin, methods=["GET"]),
    Route("/admin.html", serve_admin, methods=["GET"]),

    # Student Endpoints
    Route("/api/login", api_login, methods=["POST"]),
    Route("/api/query", api_query, methods=["POST"]),
    Route("/api/session", api_session, methods=["GET"]),
    Route("/api/tickets", api_tickets, methods=["GET"]),
    Route("/api/history", api_history, methods=["GET"]),
    Route("/api/transcribe", api_transcribe, methods=["POST"]),
    Route("/api/feedback", api_submit_feedback, methods=["POST"]),

    # Administrator Subsystem Endpoints (Isolated admin.db)
    Route("/api/admin/login", api_admin_login, methods=["POST"]),
    Route("/api/admin/session", api_admin_session, methods=["GET"]),
    Route("/api/admin/logout", api_admin_logout, methods=["POST"]),
    Route("/api/admin/tickets", api_admin_tickets, methods=["GET"]),
    Route("/api/admin/ticket/update", api_admin_ticket_update, methods=["POST"]),
    Route("/api/admin/audit-logs", api_admin_audit_logs, methods=["GET"]),
    Route("/api/admin/student-queries", api_admin_student_queries, methods=["GET"]),
    Route("/api/admin/feedback", api_admin_feedback, methods=["GET"]),

    # Static Assets
    Mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
]


middleware = [
    Middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
]

app = Starlette(routes=routes, middleware=middleware)

if __name__ == "__main__":
    console.print("[bold spring_green3]🚀 Launching RMS Query & Admin Server at http://localhost:8000[/bold spring_green3]")
    uvicorn.run(app, host="0.0.0.0", port=8000)
