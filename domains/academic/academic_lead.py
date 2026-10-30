# domains/academic/academic_lead.py
"""
Chief Academic Dean & Academic Lead Agent
Supervises academic faculties (Engineering, Finance, Pharmaceutical, Design),
coordinates curriculum advising, and deflects standard academic inquiries via FAQs.
"""
import json
from config import client, AGENT_MODEL, console
from core.session import StudentSession
from core.faq import match_faq
from domains.academic.faculties import FACULTY_AGENTS
from domains.academic.faculties.registry import FACULTY_CATALOG

ACADEMIC_FAQS = [
    {
        "patterns": [
            ("attendance", "requirement"), ("mandatory", "attendance"), ("minimum", "attendance"),
            ("attendance", "percentage"), ("medical", "leave"), ("duty", "leave"), ("75", "attendance"),
            ("attendance", "criteria"), ("how much", "attendance")
        ],
        "answer": """### ⏱️ University Attendance Regulations & Concession Rules

- **Standard Threshold**: Minimum **75% aggregate attendance** is mandatory in every course to qualify for End-Term Theory & Practical Examinations.
- **Medical Concession (Up to 10%)**:
  - Medical certificates must be endorsed by the Chief Medical Officer (CMO) at Uni-Hospital within **7 days** of returning to campus.
  - Concession relaxes the threshold down to a hard floor of **65%**.
- **Duty Leaves (OD)**: Permitted for university-sanctioned participation in hackathons, athletics, and academic symposiums.
- **Course Detention**: Students with attendance below the threshold are awarded grade **'DE' (Detained)** and must re-register for the course.
"""
    },
    {
        "patterns": [
            ("add", "drop"), ("credit", "limit"), ("drop", "course"),
            ("course", "registration"), ("minimum", "credits"), ("maximum", "credits"),
            ("change", "elective")
        ],
        "answer": """### 📚 Academic Credit System & Elective Selection

- **Semester Credit Load**:
  - Minimum allowed: **18 credits** per regular semester.
  - Standard full-time load: **22 – 24 credits**.
  - Maximum overload limit: **28 credits** (requires CGPA >= 8.50 and Dean approval).
- **Add / Drop Period**:
  - Open during the first **14 calendar days** of the semester via the Course Registration Portal.
  - Elective swaps are subject to class seat availability and zero timetable clashes.
"""
    },
    {
        "patterns": [
            ("mentor", "meeting"), ("mentor", "role"), ("faculty", "mentor"),
            ("who is", "mentor"), ("mentorship", "hours"), ("mentor", "guidance")
        ],
        "answer": """### 👨‍🏫 Faculty Mentorship System & Office Hours

- **Role of Mentor**: Every undergraduate and postgraduate student is assigned a dedicated faculty mentor to advise on academic performance, elective tracks, project approvals, and leave verification.
- **Consultation Hours**: Formal mentoring hour is held every **Wednesday between 03:00 PM – 05:00 PM**.
- **Appointments**: Check your mentor's cabin location on your Student ERP Dashboard under **Academic Profile ➔ Faculty Mentor**.
"""
    },
    {
        "patterns": [
            ("deans", "list"), ("dean", "honour"), ("honour", "roll"),
            ("distinction",), ("academic", "excellence"), ("gold", "medal")
        ],
        "answer": """### 🏆 Dean’s Honour Roll & Academic Distinctions

- **Dean's Honour Roll**: Awarded semester-wise to the top 5% of students in each department who achieve:
  - Minimum Semester GPA (SGPA) of **9.00 or above**.
  - No active backlogs or grade revisions.
  - Clean disciplinary and attendance record.
- **Degree with Honours / Distinction**: Awarded at convocation to graduates graduating with cumulative **CGPA >= 8.50** with all courses cleared in first attempt.
"""
    }
]

ACADEMIC_LEAD_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": f"consult_{fac_id}_faculty",
            "description": f"Query curriculum, courses, instructors, and lab syllabi for {meta['name']}. Departments: {', '.join(meta['departments'])}.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sub_query": {"type": "string", "description": "Academic topic or course inquiry."}
                },
                "required": ["sub_query"]
            }
        }
    }
    for fac_id, meta in FACULTY_CATALOG.items()
]


class AcademicLeadAgent:
    """
    Chief Academic Dean Agent:
    1. Checks zero-cost FAQs first to bypass faculty delegation and RAG search.
    2. If course/syllabus specific, delegates to the appropriate FacultyAgent.
    """
    def __init__(self):
        self.model = AGENT_MODEL

    def run(self, query: str, session: StudentSession) -> str:
        # Step 1: Zero-cost FAQ Check
        faq_match = match_faq(query, ACADEMIC_FAQS)
        if faq_match:
            console.print("[bold green]  ⚡ [Academic Lead] FAQ Hit -> Bypassing Faculty Sub-Agents & RAG (₹0 Token Cost)[/bold green]")
            return faq_match

        # Step 2: Faculty Delegation via LLM Tools
        lead_prompt = f"""You are the Chief Academic Dean Agent for the University.
You oversee all academic faculties (Engineering, Finance, Pharmaceutical, Design).

STUDENT PROFILE:
- Name: {session.full_name}
- Department: {session.department_id} ({session.faculty_id})
- Enrolled Courses: {', '.join(session.enrolled_courses)}

RESPONSIBILITIES:
1. Route the academic query to the appropriate faculty tool (e.g., `consult_engineering_faculty`).
2. Read the student's question carefully and provide a concise, point-to-point answer strictly within 2 to 3 lines.
3. Do not write long paragraphs or verbose explanations.
"""
        messages = [
            {"role": "system", "content": lead_prompt},
            {"role": "user", "content": query}
        ]

        for _ in range(3):
            res = client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=ACADEMIC_LEAD_TOOLS,
                tool_choice="auto",
                temperature=0.0
            )
            msg = res.choices[0].message
            messages.append(msg)

            if not msg.tool_calls:
                return msg.content or ""

            for call in msg.tool_calls:
                fac_id = call.function.name.replace("consult_", "").replace("_faculty", "")
                args = json.loads(call.function.arguments)
                sub_q = args.get("sub_query", query)

                console.print(f"[bold cyan]  🎓 [Academic Lead] Delegating to {fac_id.title()} Faculty[/bold cyan]")
                sub_agent = FACULTY_AGENTS.get(fac_id)
                output = sub_agent.run(sub_q, session=session) if sub_agent else f"Faculty {fac_id} not available."

                messages.append({"role": "tool", "tool_call_id": call.id, "content": str(output)})

        final = client.chat.completions.create(model=self.model, messages=messages, tools=ACADEMIC_LEAD_TOOLS, tool_choice="none")
        return final.choices[0].message.content or ""


academic_lead = AcademicLeadAgent()