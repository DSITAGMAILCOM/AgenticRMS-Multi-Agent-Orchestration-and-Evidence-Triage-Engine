# domains/administration/agent.py
"""
University Administration & Residential Services Agent
Handles student fee statements, tuition payments, hostel room records,
and fast zero-cost FAQ deflection for financial and residential policies.
"""
import json
import sqlite3
from typing import Dict, Any
from config import client, AGENT_MODEL, DB_PATH, console
from core.faq import match_faq
from core.rms_handler import detect_rms_intent, handle_tracking_query, handle_history_query

ADMIN_FAQS = [
    {
        "patterns": [
            ("pay", "fee"), ("pay", "fees"), ("pay", "tuition"), ("how to pay",),
            ("payment", "mode"), ("payment", "method"), ("online", "payment"),
            ("fee", "online"), ("fee", "challan"), ("payment", "portal")
        ],
        "answer": """### 💳 University Fee Payment Modes & Online Portal

Tuition, hostel, and term dues can be settled through the following authorized modes:

1. **Student ERP Portal (Recommended – Instant Clearance)**:
   - Navigate to: **ERP Portal ➔ Accounts & Fees ➔ Make Online Payment**.
   - Accepted: **UPI (Google Pay, PhonePe, Paytm)**, **Debit/Credit Cards**, and **Net Banking**.
   - Official digital receipts are generated immediately under your **Payment Receipts** tab.

2. **Bank Challan (Offline Cash / NEFT / RTGS)**:
   - Generate and download the official 3-part bank challan from your fee ledger.
   - Pay at any branch of **Punjab National Bank (PNB)** or **HDFC Bank** across India.

3. **Finance & Accounts Desk**:
   - In-person POS card payments available at **Block 30, Ground Floor (Finance Office)**.
   - Counter Hours: Monday – Friday, 09:00 AM – 04:30 PM.
"""
    },
    {
        "patterns": [
            ("installment",), ("late", "fee"), ("late", "fine"), ("delay", "fee"),
            ("fine", "day"), ("penalty", "fee"), ("fee", "extension")
        ],
        "answer": """### ⚠️ Tuition Fee Installment & Late Penalty Policy

- **Late Fine Structure**: A fine of **₹100 per day** is automatically levied starting the first business day following the designated due date.
- **Installment Facility**:
  - Eligible students may request a split into **2 installments** (60% initial, 40% prior to mid-terms).
  - Installment applications must be submitted via **ERP ➔ Relationship Center** at least 7 days before the standard fee deadline.
- **De-registration Warning**: Unpaid dues exceeding 30 calendar days may lead to temporary suspension of LMS and campus Wi-Fi access.
"""
    },
    {
        "patterns": [
            ("hostel", "timing"), ("gate", "pass"), ("in out timing",), ("curfew",),
            ("night", "out"), ("hostel", "entry"), ("leave", "hostel")
        ],
        "answer": """### 🏢 Residential Hostel Regulations & Gate Pass Timings

- **Curfew & Entry Timing**: All residential students must report inside their assigned hostel block by **08:30 PM**.
- **Biometric Turnstiles**: Mandatory punch-in at hostel entry turnstiles.
- **Outstation & Night Leave Pass**:
  - Submit through the **LPU Touch Mobile App / ERP ➔ Hostel Services** at least **24 hours in advance**.
  - Requires automated SMS consent verification from registered parent/guardian mobile number.
- **Warden Office Hours**: Daily 05:00 PM – 07:30 PM at the respective Hostel Block Administration Desk.
"""
    },
    {
        "patterns": [
            ("scholarship", "criteria"), ("maintain", "scholarship"),
            ("retain", "scholarship"), ("scholarship", "rules"), ("scholarship", "waiver")
        ],
        "answer": """### 🎓 Scholarship Maintenance & Continuation Guidelines

To retain merit, entrance test, or sports scholarships across academic years:

1. **Academic Performance**: Must maintain a minimum cumulative CGPA of **7.50** (or 8.0 for >50% scholarship brackets).
2. **Backlog Clearance**: Zero standing backlogs/re-appears at the conclusion of each academic year.
3. **Attendance Standard**: Mandatory minimum of **75% aggregate attendance** across all enrolled courses.
4. **Disciplinary Record**: No record of ragging, misconduct, or hostel suspension.
"""
    }
]

ADMIN_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "lookup_student_fee",
            "description": "Fetch live tuition, scholarship waiver, paid amount, pending dues, and hostel details for a student.",
            "parameters": {
                "type": "object",
                "properties": {
                    "registration_number": {"type": "string", "description": "Student unique registration number."}
                },
                "required": ["registration_number"]
            }
        }
    }
]


def fetch_fee_data(reg_no: str) -> Dict[str, Any]:
    """
    Direct SQL extraction: queries student_fees and hostel_allocations for the authenticated student.
    Ensures accurate numbers without LLM hallucination.
    """
    clean_reg = str(reg_no).strip()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT f.university_id, f.total_term_fee, f.paid_amount, f.pending_dues, 
               f.due_date, f.payment_status, f.scholarship_name, f.scholarship_waiver,
               h.hostel_block, h.room_number, h.room_type, h.warden_name
        FROM student_fees f
        LEFT JOIN hostel_allocations h ON f.university_id = h.university_id
        WHERE f.university_id = ?
    """, (clean_reg,))
    row = cursor.fetchone()
    cols = [d[0] for d in cursor.description] if cursor.description else []
    conn.close()

    if row:
        return {"success": True, "record": dict(zip(cols, row))}
    return {"success": False, "error": f"No fee record on file for {clean_reg}"}


class AdminAgent:
    """
    Administration Domain Agent:
    1. Evaluates zero-cost FAQs first to bypass LLM and database queries.
    2. If personalized query, executes read-only SQL lookup and synthesizes answer.
    """
    def run(self, user_query: str, session=None) -> str:
        reg_no = getattr(session, "university_id", "") or getattr(session, "registration_no", "12204521")
        name = getattr(session, "full_name", "Student")

        # Step 1: RMS History and Tracking Direct Query Handler
        rms_intent = detect_rms_intent(user_query)
        if rms_intent == "RMS_TRACKING":
            console.print("[bold spring_green3]  ⚡ [Admin Agent] Live RMS Tracking Query -> Updating Inquiry Records in DB[/bold spring_green3]")
            res = handle_tracking_query(user_query, reg_no, name)
            return res["markdown"]
        elif rms_intent == "RMS_HISTORY":
            console.print("[bold spring_green3]  ⚡ [Admin Agent] RMS History Query -> Fetching & Updating Records in DB[/bold spring_green3]")
            res = handle_history_query(reg_no, name)
            return res["markdown"]

        # Step 2: Zero-cost FAQ Check
        faq_match = match_faq(user_query, ADMIN_FAQS)
        if faq_match:
            console.print("[bold green]  ⚡ [Admin Agent] FAQ Hit -> Bypassing Database & RAG (₹0 Token Cost)[/bold green]")
            return faq_match

        # Step 3: Personalized Fee/Hostel Inquiry via DB + LLM

        system_prompt = (
            f"You are the University Administration Agent.\n"
            f"Student: {name} (Registration No: {reg_no}).\n"
            f"Instructions:\n"
            f"1. Invoke 'lookup_student_fee' with registration_number='{reg_no}'.\n"
            f"2. Read the student's question carefully and provide a direct, point-to-point answer within 2 to 3 lines. Do not write long paragraphs.\n"
            f"3. Never ask for credentials or registration number."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query}
        ]

        res = client.chat.completions.create(
            model=AGENT_MODEL,
            messages=messages,
            tools=ADMIN_TOOLS,
            tool_choice="auto",
            temperature=0.0
        )
        msg = res.choices[0].message

        if msg.tool_calls:
            messages.append(msg)
            for call in msg.tool_calls:
                fn_result = fetch_fee_data(reg_no)
                messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "name": call.function.name,
                    "content": json.dumps(fn_result)
                })

            final = client.chat.completions.create(
                model=AGENT_MODEL,
                messages=messages,
                temperature=0.0
            )
            return final.choices[0].message.content or ""

        return msg.content or ""


admin_agent = AdminAgent()