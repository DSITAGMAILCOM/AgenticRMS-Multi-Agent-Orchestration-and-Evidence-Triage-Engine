# streamlit_app.py
"""
University Multi-Agent RAG System - Complete Streamlit Application
Hosts both the Student Query Portal (with Multi-Agent Orchestration & RAG)
and the Administrator Workspace (with Live Ticket Triage & Audit Telemetry).
Compatible with local execution and 1-Click Streamlit Community Cloud Deployment.
"""

import os
import sys
import json
import sqlite3
import datetime
import secrets
import streamlit as st

# Ensure base directory is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config import DB_PATH, ADMIN_DB_PATH, console
from core.session import StudentSession
from core.tracker import QueryTracker
from orchestrator.router import orchestrate_query, clean_query, active_gate_classify
from core.rms_handler import detect_rms_intent
from core.query_logger import (
    format_student_university_email,
    log_query_across_all_locations,
    make_polite_comprehensive_answer
)
from core.admin_db import (
    init_admin_database,
    authenticate_admin,
    log_admin_action,
    get_recent_admin_audit_logs
)


# =========================================================================
# 1. Automatic Database Bootstrapping (Essential for Streamlit Cloud)
# =========================================================================
def bootstrap_databases():
    """Initializes university.db, admin.db, and feedback tables if missing."""
    if not os.path.exists(DB_PATH):
        try:
            from database_setup import init_db
            init_db()
        except Exception as e:
            st.error(f"Error seeding student database: {e}")

    try:
        init_admin_database()
    except Exception as e:
        pass

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
        conn.commit()
        conn.close()
    except Exception:
        pass


bootstrap_databases()


# =========================================================================
# 2. Streamlit Page Configuration & Modern Glassmorphic CSS Styling
# =========================================================================
st.set_page_config(
    page_title="RMS Query — University Multi-Agent RAG System",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

CUSTOM_CSS = """
<style>
/* Root Glassmorphism & Color Variables */
:root {
  --terracotta: #c2410c;
  --terracotta-light: #ea580c;
  --glass-card: rgba(255, 255, 255, 0.72);
  --glass-border: rgba(255, 255, 255, 0.85);
  --text-dark: #0f172a;
  --text-muted: #334155;
}

/* App Background & Typography */
.stApp {
  background: linear-gradient(135deg, #1e1b18 0%, #2d2420 50%, #1a1614 100%);
  color: #f8fafc;
  font-family: 'Plus Jakarta Sans', -apple-system, sans-serif;
}

/* Frosted Glass Cards */
.glass-panel {
  background: rgba(255, 255, 255, 0.08);
  backdrop-filter: blur(24px) saturate(160%);
  -webkit-backdrop-filter: blur(24px);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 16px;
  padding: 20px 24px;
  margin-bottom: 20px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.25);
}

.suggestion-box {
  background: rgba(255, 255, 255, 0.12);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.22);
  border-radius: 14px;
  padding: 16px 18px;
  transition: all 0.2s ease;
  min-height: 120px;
}
.suggestion-box:hover {
  background: rgba(255, 255, 255, 0.2);
  border-color: rgba(255, 255, 255, 0.4);
  transform: translateY(-2px);
}

/* Status Badges */
.badge-resolved {
  background: rgba(16, 185, 129, 0.2);
  color: #34d399;
  border: 1px solid rgba(16, 185, 129, 0.4);
  padding: 3px 10px;
  border-radius: 9999px;
  font-size: 0.8rem;
  font-weight: 600;
}
.badge-progress {
  background: rgba(245, 158, 11, 0.2);
  color: #fbbf24;
  border: 1px solid rgba(245, 158, 11, 0.4);
  padding: 3px 10px;
  border-radius: 9999px;
  font-size: 0.8rem;
  font-weight: 600;
}
.badge-agent {
  background: rgba(194, 65, 12, 0.22);
  color: #fdba74;
  border: 1px solid rgba(194, 65, 12, 0.5);
  padding: 3px 10px;
  border-radius: 9999px;
  font-size: 0.78rem;
  font-weight: 600;
  margin-right: 6px;
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# =========================================================================
# 3. Session State Initialization
# =========================================================================
if "student_reg" not in st.session_state:
    st.session_state["student_reg"] = "12204521"
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []
if "admin_user" not in st.session_state:
    st.session_state["admin_user"] = None
if "active_view" not in st.session_state:
    st.session_state["active_view"] = "student"
if "prefilled_prompt" not in st.session_state:
    st.session_state["prefilled_prompt"] = ""


# =========================================================================
# 4. Sidebar: Navigation & Identity Context
# =========================================================================
with st.sidebar:
    st.markdown("### 🎓 **RMS Query System**")
    st.caption("Autonomous University Multi-Agent RAG & Evidence Triage Engine")
    st.markdown("---")

    view_choice = st.radio(
        "**Navigation Mode**",
        ["🎓 Student Query Portal", "🛡️ Administrator Workspace"],
        index=0 if st.session_state["active_view"] == "student" else 1
    )
    st.session_state["active_view"] = "student" if "Student" in view_choice else "admin"

    st.markdown("---")

    if st.session_state["active_view"] == "student":
        st.markdown("#### 👤 Student Identity")
        student_options = {
            "12204521": "Aditya Sharma (B.Tech CSE)",
            "12204522": "Priya Patel (Pharm.D)",
            "12204523": "Rahul Verma (B.Des UI/UX)"
        }
        selected_reg = st.selectbox(
            "Select Student Profile",
            options=list(student_options.keys()),
            format_func=lambda x: f"{x} - {student_options[x]}"
        )
        st.session_state["student_reg"] = selected_reg

        # Load Student Profile Details
        curr_session = StudentSession(selected_reg)
        st.markdown(f"""
        <div style="font-size: 0.85rem; background: rgba(255,255,255,0.06); padding: 12px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.1);">
          <strong>Name:</strong> {curr_session.full_name}<br>
          <strong>Reg No:</strong> <code>{curr_session.university_id}</code><br>
          <strong>Email:</strong> {curr_session.university_email}<br>
          <strong>Dept:</strong> {curr_session.department_id}<br>
          <strong>Mentor:</strong> {curr_session.mentor_name} ({curr_session.mentor_cabin})
        </div>
        """, unsafe_allow_html=True)

        if st.button("Clear Chat History", use_container_width=True):
            st.session_state["chat_history"] = []
            st.rerun()

    else:
        st.markdown("#### 🛡️ Administrator Session")
        if st.session_state["admin_user"]:
            u = st.session_state["admin_user"]
            st.success(f"Signed in as **{u['full_name']}**")
            st.caption(f"Role: `{u['role']}` | Dept: {u['department']}")
            if st.button("Sign Out", use_container_width=True):
                st.session_state["admin_user"] = None
                st.rerun()
        else:
            st.info("Please sign in to the administrator portal.")

    st.markdown("---")
    st.caption("Active Model: `openai/gpt-oss-20b` via Groq Cloud")
    st.caption("Orchestrator: Multi-Agent Graph Router with Evidence Verification")


# =========================================================================
# 5. VIEW 1: STUDENT PORTAL
# =========================================================================
if st.session_state["active_view"] == "student":
    student_session = StudentSession(st.session_state["student_reg"])

    st.markdown(f"## Welcome back, {student_session.full_name} 👋")
    st.markdown("Ask anything regarding your term fees, examination marks, NOC credits, hostel rooms, or raise an RMS ticket.")

    # --- 3 Suggestion Cards (Matching Exact Frosted Glass Design) ---
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("""
        <div class="suggestion-box">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
            <span style="font-size:1.3rem;">💡</span>
            <span style="color:rgba(255,255,255,0.6);">↗</span>
          </div>
          <div style="font-weight:700; font-size:1.05rem; margin-bottom:4px;">Ask your Query</div>
          <div style="font-size:0.83rem; color:rgba(255,255,255,0.75);">What is my current fee balance and hostel room allotment?</div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Ask Query Example", key="btn_q1", use_container_width=True):
            st.session_state["prefilled_prompt"] = "What is my current fee balance and hostel room allotment?"
            st.rerun()

    with col2:
        st.markdown("""
        <div class="suggestion-box">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
            <span style="font-size:1.3rem;">⭐</span>
            <span style="color:rgba(255,255,255,0.6);">↗</span>
          </div>
          <div style="font-weight:700; font-size:1.05rem; margin-bottom:4px;">Give Feedback</div>
          <div style="font-size:0.83rem; color:rgba(255,255,255,0.75);">Rate your experience and share suggestions to improve campus services.</div>
        </div>
        """, unsafe_allow_html=True)
        open_fb_expander = st.button("Open Feedback Form", key="btn_q2", use_container_width=True)

    with col3:
        st.markdown("""
        <div class="suggestion-box">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
            <span style="font-size:1.3rem;">🕒</span>
            <span style="color:rgba(255,255,255,0.6);">↗</span>
          </div>
          <div style="font-weight:700; font-size:1.05rem; margin-bottom:4px;">Track RMS Status</div>
          <div style="font-size:0.83rem; color:rgba(255,255,255,0.75);">Monitor live resolution progress and assigned officer stages.</div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Check Active Tickets", key="btn_q3", use_container_width=True):
            st.session_state["prefilled_prompt"] = "What is the status of my active RMS tickets and grievances?"
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # --- Student Feedback Form Expander ---
    with st.expander("⭐ Submit Student Feedback & Service Rating", expanded=open_fb_expander):
        with st.form("student_feedback_form"):
            fb_col1, fb_col2 = st.columns(2)
            with fb_col1:
                fb_category = st.selectbox("Feedback Category", [
                    "General Campus Support",
                    "Examination & Grades",
                    "Fees & Scholarships",
                    "Hostel & Dining",
                    "Curriculum & Faculty"
                ])
                fb_rating = st.slider("Overall Experience Rating (1-5 Stars)", min_value=1, max_value=5, value=5)
            with fb_col2:
                fb_quality = st.selectbox("Resolution Quality", [
                    "Exceptional / Instant",
                    "Satisfactory / Clear",
                    "Needs Faster Follow-up",
                    "Unresolved / Escalated"
                ])
                fb_recommend = st.selectbox("Would you recommend RMS Query to peers?", [
                    "Definitely",
                    "Likely",
                    "Neutral",
                    "Unlikely"
                ])

            fb_comments = st.text_area("Your Feedback & Comments *", placeholder="Describe your experience with the assistant...")
            fb_suggestions = st.text_input("Suggestions for Campus Administration (Optional)")
            fb_anon = st.checkbox("Submit feedback anonymously")

            submitted_fb = st.form_submit_button("Submit Secure Feedback", use_container_width=True)
            if submitted_fb:
                if not fb_comments.strip():
                    st.error("Please provide comments before submitting.")
                else:
                    fb_id = f"FB-{datetime.datetime.now().strftime('%Y%m')}-{secrets.token_hex(2).upper()}"
                    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    sub_uid = f"ANON-{secrets.token_hex(2).upper()}" if fb_anon else student_session.university_id
                    sub_name = "Anonymous Student" if fb_anon else student_session.full_name

                    try:
                        conn = sqlite3.connect(DB_PATH)
                        cur = conn.cursor()
                        cur.execute("""
                            INSERT INTO student_feedback (
                                feedback_id, university_id, student_name, category, rating,
                                resolution_quality, recommendation, comments, suggestions,
                                submitted_at, ip_address
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            fb_id, sub_uid, sub_name, fb_category, fb_rating,
                            fb_quality, fb_recommend, fb_comments, fb_suggestions,
                            now_str, "127.0.0.1"
                        ))
                        conn.commit()
                        conn.close()

                        log_admin_action(
                            admin_id="SYSTEM",
                            username="system",
                            action="STUDENT_FEEDBACK",
                            target_ticket_id=fb_id,
                            details=f"New {fb_rating}-star feedback submitted for {fb_category} by {sub_uid}",
                            ip_address="127.0.0.1"
                        )
                        st.success(f"✅ Thank you! Your feedback has been recorded (ID: `{fb_id}`).")
                    except Exception as e:
                        st.error(f"Failed to record feedback: {e}")

    # --- Render Chat Stream ---
    for msg in st.session_state["chat_history"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("hops"):
                with st.expander("🔍 Multi-Agent Reasoning Telemetry & Execution Trajectory"):
                    st.caption("Agent Execution Hops:")
                    for idx, hop in enumerate(msg["hops"], 1):
                        st.markdown(f"**Step {idx}:** `{hop.get('from_agent', 'Orchestrator')}` ➔ `{hop.get('to_agent', 'Agent')}` (`{hop.get('action_type', 'ROUTE')}`)")
                    if msg.get("domains"):
                        st.markdown(f"**Detected Domains:** {', '.join([f'`{d}`' for d in msg['domains']])}")
                    if msg.get("ticket"):
                        st.info(f"🎫 **RMS Ticket Automatically Generated:** `{msg['ticket']}`")

    # --- Chat Input Box ---
    default_text = st.session_state["prefilled_prompt"]
    user_query = st.chat_input("Ask a question, request hostel status, or report an issue...", key="main_chat_input")

    # Handle button-clicked prefilled prompt
    if not user_query and default_text:
        user_query = default_text
        st.session_state["prefilled_prompt"] = ""

    if user_query:
        # Append User Message
        st.session_state["chat_history"].append({"role": "user", "content": user_query})
        with st.chat_message("user"):
            st.markdown(user_query)

        # Multi-Agent Orchestration Execution
        with st.chat_message("assistant"):
            with st.spinner("🤖 Routing across university domain agents & querying knowledge graphs..."):
                cleaned_q = clean_query(user_query)
                tracker = QueryTracker(
                    university_id=student_session.university_id,
                    student_name=student_session.full_name,
                    email=student_session.university_email,
                    raw_query=cleaned_q
                )

                raw_response = orchestrate_query(user_query, session=student_session, tracker=tracker)

                # Determine domain from actual agent hops
                agent_hops = [h["to_agent"].replace("Agent", "").lower() for h in tracker.hops if "Agent" in h.get("to_agent", "")]
                unique_domains = list(dict.fromkeys(agent_hops))
                if len(unique_domains) > 1:
                    domain = "multi_domain"
                elif unique_domains:
                    domain = unique_domains[0]
                else:
                    domain = active_gate_classify(cleaned_q)

                polite_response = make_polite_comprehensive_answer(
                    raw_response=raw_response,
                    student_name=student_session.full_name,
                    query_text=user_query,
                    domain=domain
                )

                target_tid = getattr(tracker, "ticket_id", None)
                if not target_tid and "RMS" in polite_response:
                    import re
                    m = re.findall(r'RMS\d{8}[0-9A-Fa-f]+', polite_response)
                    if m:
                        target_tid = m[0]

                # Log query across all storage tiers
                log_query_across_all_locations(
                    query_text=user_query,
                    student_name=student_session.full_name,
                    university_id=student_session.university_id,
                    department=student_session.department_id,
                    domain=domain,
                    response_text=polite_response,
                    ticket_id=target_tid,
                    tracker=tracker
                )

                st.markdown(polite_response)

                st.session_state["chat_history"].append({
                    "role": "assistant",
                    "content": polite_response,
                    "hops": tracker.hops,
                    "domains": unique_domains or [domain],
                    "ticket": target_tid
                })

                if tracker.hops:
                    with st.expander("🔍 Multi-Agent Reasoning Telemetry & Execution Trajectory"):
                        for idx, hop in enumerate(tracker.hops, 1):
                            st.markdown(f"**Step {idx}:** `{hop.get('from_agent', 'Orchestrator')}` ➔ `{hop.get('to_agent', 'Agent')}` (`{hop.get('action_type', 'ROUTE')}`)")

    # --- Live Active RMS Tickets View for Student ---
    st.markdown("---")
    st.markdown("### 📋 Your Active RMS Helpdesk Tickets")
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("""
            SELECT ticket_id, category, status, current_stage, next_stage,
                   stage_progress, assigned_officer, estimated_resolution, created_at
            FROM helpdesk_tickets
            WHERE university_id = ?
            ORDER BY created_at DESC
        """, (student_session.university_id,))
        my_tickets = [dict(r) for r in cur.fetchall()]
        conn.close()

        if my_tickets:
            for t in my_tickets:
                prog = int(t.get("stage_progress") or 1) * 25
                status_color = "badge-resolved" if (t.get("status") or "").lower() == "resolved" else "badge-progress"
                st.markdown(f"""
                <div style="background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.12); padding: 14px 18px; border-radius: 12px; margin-bottom: 12px;">
                  <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                    <div>
                      <strong style="color: #60a5fa; font-size: 1.05rem;">{t['ticket_id']}</strong> — {t['category']}
                    </div>
                    <span class="{status_color}">{t['status']}</span>
                  </div>
                  <div style="font-size:0.85rem; color:rgba(255,255,255,0.8); margin-bottom:8px;">
                    <strong>Stage:</strong> {t.get('current_stage') or 'Initial Triage'} ➔ <strong>Next:</strong> {t.get('next_stage') or 'Final Resolution'} | 
                    <strong>Desk:</strong> {t.get('assigned_officer') or 'University Helpdesk'}
                  </div>
                </div>
                """, unsafe_allow_html=True)
                st.progress(prog / 100.0, text=f"Stage Progress: {prog}% Complete")
        else:
            st.info("No open grievances or support tickets found for your account.")
    except Exception as e:
        st.caption(f"Note loading tickets: {e}")


# =========================================================================
# 6. VIEW 2: ADMINISTRATOR WORKSPACE
# =========================================================================
else:
    st.markdown("## 🛡️ University Administrator Workspace")
    st.caption("Live Ticket Triage, SLA Stage Management & Multi-Location Audit Logs")

    # Admin Login Form if not authenticated
    if not st.session_state["admin_user"]:
        col_l, col_r = st.columns([1, 1])
        with col_l:
            st.markdown("""
            <div class="glass-panel">
              <h4>🔐 Administrator Authentication</h4>
              <p style="font-size: 0.85rem; color: rgba(255,255,255,0.7);">
                Access is restricted to authorized university administrative officers. Credentials are authenticated via PBKDF2 with 100,000 hash iterations.
              </p>
            </div>
            """, unsafe_allow_html=True)

            with st.form("admin_login_form"):
                admin_username = st.text_input("Administrator Username", value="admin")
                admin_password = st.text_input("Password", type="password", value="Admin@RMS2026!")
                login_btn = st.form_submit_button("Sign In to Portal", use_container_width=True)

                if login_btn:
                    auth_res = authenticate_admin(admin_username.strip(), admin_password.strip(), ip_address="127.0.0.1")
                    if auth_res.get("success"):
                        st.session_state["admin_user"] = auth_res["user"]
                        st.success(f"Welcome, {auth_res['user']['full_name']}!")
                        st.rerun()
                    else:
                        st.error(auth_res.get("error", "Invalid credentials."))

        with col_r:
            st.markdown("""
            <div class="glass-panel">
              <h4>Default Test Credentials</h4>
              <table style="width:100%; font-size:0.85rem; color:#f8fafc;">
                <tr><td style="padding:6px;"><strong>Username</strong></td><td style="padding:6px;"><code>admin</code></td></tr>
                <tr><td style="padding:6px;"><strong>Password</strong></td><td style="padding:6px;"><code>Admin@RMS2026!</code></td></tr>
                <tr><td style="padding:6px;"><strong>Role</strong></td><td style="padding:6px;">SuperAdmin</td></tr>
              </table>
              <hr style="border-color: rgba(255,255,255,0.1);">
              <table style="width:100%; font-size:0.85rem; color:#f8fafc;">
                <tr><td style="padding:6px;"><strong>Username</strong></td><td style="padding:6px;"><code>officer</code></td></tr>
                <tr><td style="padding:6px;"><strong>Password</strong></td><td style="padding:6px;"><code>Officer@RMS2026!</code></td></tr>
                <tr><td style="padding:6px;"><strong>Role</strong></td><td style="padding:6px;">SupportOfficer</td></tr>
              </table>
            </div>
            """, unsafe_allow_html=True)

    else:
        admin = st.session_state["admin_user"]

        # --- Admin KPI Metric Row ---
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM helpdesk_tickets ORDER BY created_at DESC")
        all_tickets = [dict(r) for r in cur.fetchall()]

        cur.execute("SELECT COUNT(*), AVG(rating) FROM student_feedback")
        fb_stats = cur.fetchone()
        fb_count = fb_stats[0] if fb_stats else 0
        fb_avg = round(fb_stats[1], 1) if (fb_stats and fb_stats[1]) else 0.0

        total_t = len(all_tickets)
        resolved_t = sum(1 for r in all_tickets if (r.get("status") or "").lower() == "resolved")
        in_prog_t = sum(1 for r in all_tickets if (r.get("status") or "").lower() in ("in progress", "open"))
        conn.close()

        kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
        kpi1.metric("Total Tickets", total_t)
        kpi2.metric("In Progress", in_prog_t)
        kpi3.metric("Resolved", resolved_t)
        kpi4.metric("Student CSAT", f"⭐ {fb_avg} / 5.0", f"{fb_count} reviews")
        kpi5.metric("Admin Desk", admin["role"])

        st.markdown("<br>", unsafe_allow_html=True)

        admin_tab1, admin_tab2, admin_tab3, admin_tab4 = st.tabs([
            "🎫 Ticket Stage Manager",
            "🔍 Student Query Records",
            "⭐ Feedback & Ratings",
            "📋 Audit Trail"
        ])

        # --- TAB 1: TICKET STAGE MANAGER ---
        with admin_tab1:
            st.markdown("#### Live Helpdesk Tickets & Stage Management")
            if all_tickets:
                ticket_ids = [t["ticket_id"] for t in all_tickets]
                selected_t_id = st.selectbox("Select Ticket to Inspect & Update", ticket_ids)
                ticket_data = next((t for t in all_tickets if t["ticket_id"] == selected_t_id), None)

                if ticket_data:
                    t_col1, t_col2 = st.columns([1, 1])

                    with t_col1:
                        st.markdown(f"""
                        <div style="background:rgba(255,255,255,0.06); padding:16px; border-radius:12px; border:1px solid rgba(255,255,255,0.12);">
                          <strong style="font-size:1.1rem; color:#60a5fa;">{ticket_data['ticket_id']}</strong> ({ticket_data['category']})<br>
                          <strong>Student:</strong> {ticket_data['student_name']} (<code>{ticket_data['university_id']}</code>)<br>
                          <strong>Email:</strong> {ticket_data['university_email']} | <strong>Dept:</strong> {ticket_data.get('department_id', 'N/A')}<br>
                          <strong>Created:</strong> {ticket_data['created_at']}<br>
                          <hr style="border-color: rgba(255,255,255,0.1);">
                          <strong>Grievance Text:</strong><br>
                          <div style="color:rgba(255,255,255,0.85); font-style:italic;">"{ticket_data['query_text']}"</div>
                        </div>
                        """, unsafe_allow_html=True)

                    with t_col2:
                        with st.form("update_ticket_form"):
                            new_status = st.selectbox("Ticket Status", ["Open", "In Progress", "Resolved", "Escalated"], index=["open", "in progress", "resolved", "escalated"].index((ticket_data.get("status") or "in progress").lower()) if (ticket_data.get("status") or "").lower() in ["open", "in progress", "resolved", "escalated"] else 1)
                            new_progress = st.slider("Stage Progress (%)", min_value=1, max_value=4, value=int(ticket_data.get("stage_progress") or 2), format="%d")
                            new_stage = st.text_input("Current Stage", value=ticket_data.get("current_stage") or "Assigned to Support Officer")
                            new_next_stage = st.text_input("Next Stage", value=ticket_data.get("next_stage") or "Dean Clearance & Signoff")
                            new_officer = st.text_input("Assigned Officer / Desk", value=ticket_data.get("assigned_officer") or admin["full_name"])
                            new_notes = st.text_area("Administrative Resolution Notes", value=ticket_data.get("human_resolution_notes") or "")

                            update_btn = st.form_submit_button("Save & Update Stage Progress", use_container_width=True)

                            if update_btn:
                                now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                resolved_str = now_str if new_status.lower() == "resolved" else None

                                conn = sqlite3.connect(DB_PATH)
                                cur = conn.cursor()
                                cur.execute("""
                                    UPDATE helpdesk_tickets
                                    SET status = ?,
                                        stage_progress = ?,
                                        current_stage = ?,
                                        next_stage = ?,
                                        assigned_officer = ?,
                                        human_resolution_notes = ?,
                                        resolved_at = COALESCE(?, resolved_at)
                                    WHERE ticket_id = ?
                                """, (
                                    new_status, new_progress, new_stage, new_next_stage,
                                    new_officer, new_notes, resolved_str, selected_t_id
                                ))
                                conn.commit()
                                conn.close()

                                # Record in admin.db audit logs
                                log_admin_action(
                                    admin_id=admin["admin_id"],
                                    username=admin["username"],
                                    action="UPDATE_TICKET_STAGE",
                                    target_ticket_id=selected_t_id,
                                    details=f"Status: {new_status}, Stage: {new_stage} ({new_progress*25}%), Desk: {new_officer}.",
                                    ip_address="127.0.0.1"
                                )

                                st.success(f"✅ Ticket '{selected_t_id}' successfully updated!")
                                st.rerun()

            else:
                st.info("No tickets currently logged in university.db.")

        # --- TAB 2: STUDENT QUERY RECORDS ---
        with admin_tab2:
            st.markdown("#### Real-time Student Query Inspection & Agent Telemetry")
            try:
                conn_a = sqlite3.connect(ADMIN_DB_PATH)
                conn_a.row_factory = sqlite3.Row
                cur_a = conn_a.cursor()
                cur_a.execute("SELECT * FROM admin_query_records ORDER BY timestamp DESC LIMIT 50")
                query_records = [dict(r) for r in cur_a.fetchall()]
                conn_a.close()

                if query_records:
                    st.dataframe(
                        query_records,
                        column_config={
                            "ticket_id": "Ticket ID",
                            "student_name": "Student",
                            "university_id": "Reg No",
                            "domain": "Domain",
                            "query_text": "Student Query",
                            "response_text": "Agent Answer",
                            "timestamp": "Time"
                        },
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.info("No cross-system student query logs recorded yet.")
            except Exception as e:
                st.caption(f"Note: {e}")

        # --- TAB 3: FEEDBACK & RATINGS ---
        with admin_tab3:
            st.markdown("#### Student Sentiment & Service Feedback Analysis")
            try:
                conn = sqlite3.connect(DB_PATH)
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute("SELECT * FROM student_feedback ORDER BY submitted_at DESC")
                all_fb = [dict(r) for r in cur.fetchall()]
                conn.close()

                if all_fb:
                    st.dataframe(
                        all_fb,
                        column_config={
                            "feedback_id": "ID",
                            "university_id": "Reg No",
                            "student_name": "Student",
                            "category": "Category",
                            "rating": "Stars",
                            "resolution_quality": "Quality",
                            "recommendation": "Recommend",
                            "comments": "Comments",
                            "submitted_at": "Timestamp"
                        },
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.info("No student feedback records logged yet.")
            except Exception as e:
                st.caption(f"Note: {e}")

        # --- TAB 4: AUDIT TRAIL ---
        with admin_tab4:
            st.markdown("#### Immutable Administrative Action Audit Trail (admin.db)")
            audit_logs = get_recent_admin_audit_logs(limit=50)
            if audit_logs:
                st.dataframe(
                    audit_logs,
                    column_config={
                        "log_id": "#",
                        "username": "Admin",
                        "action": "Action",
                        "target_ticket_id": "Target ID",
                        "details": "Details",
                        "timestamp": "Timestamp"
                    },
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("No administrative actions recorded in audit logs yet.")
