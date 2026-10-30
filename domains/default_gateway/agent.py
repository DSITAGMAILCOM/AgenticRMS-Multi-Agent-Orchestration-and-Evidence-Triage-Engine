# domains/default_gateway/agent.py
"""
Default Human Gateway & Campus General Support Agent
Handles campus-wide services FAQs (Library, Health Center, Wi-Fi),
and manages human helpdesk ticket creation when automated resolution is unviable.
"""
import sqlite3
import random
import datetime
from typing import Optional
from config import DB_PATH, console
from core.session import StudentSession
from core.tracker import QueryTracker
from core.faq import match_faq

GATEWAY_FAQS = [
    {
        "patterns": ["library timing", "library hours", "central library", "borrow book", "library book", "issue book"],
        "answer": """### 📖 Central Library Timings & Borrowing Policy

- **Operating Hours**:
  - Regular Working Days: **08:00 AM – 11:00 PM**.
  - During Mid-Term & End-Term Examination Weeks: **Open 24/7**.
- **Borrowing Limit**: Undergraduates may borrow up to **4 books for 14 calendar days** (renewable twice online via Web-OPAC).
- **Digital Library**: Remote access to IEEE Xplore, Springer, and ScienceDirect available through the university campus network.
"""
    },
    {
        "patterns": ["hospital", "health center", "medical emergency", "doctor timing", "ambulance", "pharmacy on campus", "clinic"],
        "answer": """### 🏥 University Health Clinic & Emergency Support

- **Location**: **Uni-Hospital, Block 29 (Central Campus)**.
- **Timings**: **Open 24 Hours / 7 Days a week** with resident medical officers and emergency trauma care.
- **Services**: Free OPD consultations, routine diagnostic lab, and in-house pharmacy.
- **24/7 Ambulance Emergency Helpline**: **+91-98765-00108** (Internal Ext: 108).
"""
    },
    {
        "patterns": ["wifi", "wi fi", "internet access", "reset password", "erp login issue", "it helpdesk"],
        "answer": """### 📶 Campus Wi-Fi & Technical Support Desk

- **Network SSID**: Connect to **`Campus-Secure`** using your University Email ID and ERP password.
- **Device Limit**: Up to 3 personal devices per registered student.
- **IT Helpdesk Office**: **Block 30, Room 104** (Monday – Friday, 09:00 AM – 05:00 PM).
- **Password Reset**: Use the self-service *"Forgot Password"* link on the ERP portal login page.
"""
    }
]


class DefaultGatewayAgent:
    """
    Default Gateway Agent:
    1. Checks general campus FAQs (Library, Health Center, IT/Wi-Fi) to avoid unnecessary ticketing.
    2. If an issue requires manual officer intervention, logs ticket to helpdesk_tickets and produces diagnostic trace.
    """
    def check_faq(self, query: str) -> Optional[str]:
        """Exposes FAQ check directly to the orchestrator for fast-path general resolution."""
        return match_faq(query, GATEWAY_FAQS)

    def run(self, query: str, session: StudentSession, tracker: QueryTracker, reason: str = "Manual verification required") -> str:
        # Step 1: Check general FAQs
        faq_ans = self.check_faq(query)
        if faq_ans:
            console.print("[bold green]  ⚡ [Default Gateway] FAQ Hit -> Immediate Response (₹0 Token Cost)[/bold green]")
            return faq_ans

        # Step 2: Human Ticket Escalation
        ticket_id = f"TKT-{datetime.datetime.now().year}-{random.randint(1000, 9999)}"

        tracker.log_hop(
            from_agent=tracker.current_agent,
            to_agent="Default Human Gateway",
            action_type="ESCALATION",
            payload={"reason": reason},
            output=f"Created support ticket {ticket_id}."
        )

        trajectory_str = " ➔ ".join([h["from_agent"] for h in tracker.hops] + ["Default Human Gateway"])

        q_lower = query.lower()
        if any(w in q_lower for w in ["fee", "dues", "hostel", "bus"]):
            category = "Fee/Admin"
        elif any(w in q_lower for w in ["exam", "marks", "grade", "datesheet"]):
            category = "Exam"
        elif any(w in q_lower for w in ["internship", "noc", "file"]):
            category = "Internship"
        elif any(w in q_lower for w in ["syllabus", "course", "lab"]):
            category = "Academic"
        else:
            category = "General"

        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO helpdesk_tickets (
                    ticket_id, university_id, student_name, university_email,
                    department_id, query_text, escalation_reason, category, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'OPEN')
            """, (
                ticket_id, session.university_id, session.full_name, session.university_email,
                session.department_id, f"{query}\n\n[AI DIAGNOSTIC TRAJECTORY]:\n{trajectory_str}",
                f"{reason} (Linked Audit ID: {tracker.query_id})", category
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            console.print(f"[red]Helpdesk ticket insertion error: {e}[/red]")

        tracker.finalize(resolution_type="ESCALATED_TO_HUMAN", ticket_id=ticket_id)

        return f"""### 👨‍💼 Request Escalated to University Helpdesk

I could not find an authoritative automated answer for your query in our records. To ensure accuracy, this request has been logged for a university officer.

| Reference | Detail |
| :--- | :--- |
| **Ticket Reference ID** | `{ticket_id}` |
| **Audit Session Trace** | `{tracker.query_id}` |
| **Student** | {session.full_name} ({session.university_id}) |
| **Category** | {category} Support Desk |
| **Ticket Status** | **OPEN (Pending Officer Review)** |

> **Diagnostic Trace:**  
> `{trajectory_str}`  
>
> An officer will review your full routing trail and reply to **`{session.university_email}`**.
"""


default_gateway_agent = DefaultGatewayAgent()