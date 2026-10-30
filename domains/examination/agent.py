# domains/examination/agent.py
"""
Controller of Examinations (COE) Agent
Handles examination schedules, seating desk allocations, academic grade transcripts,
and provides zero-cost FAQ deflection for grading ordinances and re-evaluation policies.
"""
import json
from config import client, AGENT_MODEL, console
from core.db_engine import run_db_query
from domains.examination.rag import exam_rag
from core.session import StudentSession
from core.faq import match_faq

EXAM_FAQS = [
    {
        "patterns": [
            ("grading", "system"), ("passing", "mark"), ("passing", "marks"),
            ("pass", "mark"), ("pass", "marks"), ("grade", "scheme"),
            ("grade", "scale"), ("grading", "scale"), ("how to pass",)
        ],
        "answer": """### 📊 University Grading System & Passing Standards

Academic performance is graded on a **10-point relative scale**:

| Grade | Performance Level | Grade Point | Percentage Equivalent |
| :--- | :--- | :--- | :--- |
| **O** | Outstanding | 10.0 | 90% and above |
| **A+** | Excellent | 9.0 | 80% – 89% |
| **A** | Very Good | 8.0 | 70% – 79% |
| **B+** | Good | 7.0 | 60% – 69% |
| **B** | Above Average | 6.0 | 50% – 59% |
| **C** | Pass | 5.0 | 40% – 49% |
| **F** | Fail | 0.0 | Below 40% |

- **Passing Criterion**: Minimum **40% combined aggregate** across Continuous Assessment (CA) and End-Term Exam.
"""
    },
    {
        "patterns": [
            ("re", "eval"), ("reeval",), ("recheck",), ("re", "checking"),
            ("answer", "sheet"), ("scrutiny",), ("apply", "re eval")
        ],
        "answer": """### 📝 End-Term Answer Script Re-Evaluation & Scrutiny

If you suspect an evaluation error in your final exam results:

1. **Filing Window**: Applications open on ERP within **10 calendar days** from the official result publication date.
2. **Application Fee**: **₹500 per course** (non-refundable) paid online via ERP.
3. **Process**:
   - Stage 1 (Verification): Totaling and un-evaluated question check.
   - Stage 2 (Blind Re-marking): Complete re-evaluation by an independent external examiner.
4. **Outcome**: The revised score is final and updated on your grade transcript within 21 working days.
"""
    },
    {
        "patterns": [
            ("admit", "card"), ("hall", "ticket"), ("download", "admit"),
            ("download", "hall ticket"), ("exam", "eligibility")
        ],
        "answer": """### 🎫 Examination Admit Card & Hall Ticket Rules

- **Release Date**: Available on ERP **5 days prior** to the commencement of end-term exams.
- **Mandatory Clearances for Download**:
  1. **Attendance**: Minimum **75% attendance** in each registered course (detained students cannot download admit cards).
  2. **Accounts Clearance**: Zero pending tuition or hostel dues on your student ledger.
- **Exam Hall Requirements**: Carry your printed Admit Card along with your physical University Student RFID Card. Digital soft copies on phones are strictly prohibited in exam halls.
"""
    },
    {
        "patterns": [
            ("backlog",), ("re", "appear"), ("reappear",), ("clearing", "backlog"),
            ("compartment",), ("arrear",), ("supplementary", "exam")
        ],
        "answer": """### 🔄 Backlog Clearance & Re-Appear Examinations

- **Exam Windows**: Re-appear exams are conducted alongside regular semester examinations and during the dedicated **Summer Term**.
- **Internal Marks**: Your previously earned Continuous Assessment (CA) marks are carried forward.
- **Registration Fee**: **₹300 per theory course** / **₹500 per practical lab**.
- **Registration Process**: Select eligible courses on **ERP ➔ Examination ➔ Re-Appear Registration** during the announced enrollment window.
"""
    },
    {
        "patterns": [
            ("attendance", "exam"), ("attendance", "sit"), ("attendance", "requirement"),
            ("detention",), ("attendance", "percentage")
        ],
        "answer": """### ⏱️ Examination Attendance & Detention Regulations

- **Mandatory Minimum**: Exactly **75% aggregate attendance** is mandatory in each enrolled course to be eligible to sit for End-Term Theory & Practical Examinations.
- **Medical Relaxation**: Up to 10% concession (relaxing threshold down to 65%) with CMO-endorsed medical certificate submitted within 7 days.
- **Detention**: Attendance below 75% without authorized leave leads to Course Detention (Grade 'DE'). Detained students are debarred from the exam and must repeat the course.
"""
    }
]

EXAM_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_examination_database",
            "description": (
                "Query exam timetables, seating arrangements, room/desk assignments, and grade records. "
                "Tables: "
                "1. exam_datesheets(course_code, exam_type, exam_date, session_time, venue_center) "
                "2. seating_arrangements(university_id, course_code, room_no, desk_no, invigilator_name) "
                "3. grade_records(university_id, course_code, grade, credits, semester)"
            ),
            "parameters": {
                "type": "object",
                "properties": {"sql_query": {"type": "string"}},
                "required": ["sql_query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_exam_ordinances",
            "description": "FAISS vector search over university exam ordinances: grading scales, CGPA formulas, re-eval rules, UMC bylaws.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"]
            }
        }
    }
]

TOOL_REGISTRY = {
    "query_examination_database": run_db_query,
    "search_exam_ordinances": exam_rag.search
}


class ExaminationAgent:
    """
    Examination Agent:
    1. Checks zero-cost FAQs first to bypass LLM and vector RAG operations.
    2. If personalized query, executes live database queries and FAISS ordinance retrieval.
    """
    def run(self, query: str, session: StudentSession) -> str:
        # Step 1: Zero-cost FAQ Check
        faq_match = match_faq(query, EXAM_FAQS)
        if faq_match:
            console.print("[bold green]  ⚡ [Exam Agent] FAQ Hit -> Bypassing Database & RAG (₹0 Token Cost)[/bold green]")
            return faq_match

        # Step 2: Personalized Inquiry via DB + RAG
        system_prompt = f"""You are the Controller of Examinations (COE) Agent.
Handle all exam logistics, admit cards, datesheets, seating arrangements, and grades.

STUDENT PROFILE:
- Name: {session.full_name}
- Registration ID: {session.university_id}
- Enrolled Courses: {', '.join(session.enrolled_courses)}

Instructions:
1. Always filter student-specific records using university_id = '{session.university_id}'.
2. Read the student's question carefully and provide a concise, point-to-point answer within 2 to 3 lines.
3. Do not write long paragraphs or unnecessary filler.
"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query}
        ]

        for _ in range(3):
            res = client.chat.completions.create(model=AGENT_MODEL, messages=messages, tools=EXAM_TOOLS, temperature=0.0)
            msg = res.choices[0].message
            messages.append(msg)
            if not msg.tool_calls:
                return msg.content or ""

            for call in msg.tool_calls:
                fn_name = call.function.name
                args = json.loads(call.function.arguments)
                console.print(f"[dim blue]📝 [Exam Agent Tool] `{fn_name}` -> {args}[/dim blue]")

                if fn_name == "query_examination_database":
                    output = run_db_query(args.get("sql_query", ""), authenticated_student_id=session.university_id)
                elif fn_name == "search_exam_ordinances":
                    output = exam_rag.search(args.get("query", ""))
                else:
                    output = "Tool missing."
                messages.append({"role": "tool", "tool_call_id": call.id, "content": str(output)})

        final = client.chat.completions.create(model=AGENT_MODEL, messages=messages, tools=EXAM_TOOLS, tool_choice="none")
        return final.choices[0].message.content or ""


exam_agent = ExaminationAgent()