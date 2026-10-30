# domains/edu_revolution/agent.py
"""
Edu-Revolution & Career Services Agent
Manages industrial internships, corporate training approvals, NOC workflows,
and deflects general corporate internship policy questions via zero-cost FAQs.
"""
import json
from config import client, AGENT_MODEL, console
from core.db_engine import run_db_query
from domains.edu_revolution.rag import edurev_rag
from core.session import StudentSession
from core.faq import match_faq

EDUREV_FAQS = [
    {
        "patterns": [
            ("noc",), ("how to get", "noc"), ("steps", "noc"),
            ("apply", "noc"), ("internship", "noc"), ("get", "noc")
        ],
        "answer": """### 📜 Internship NOC (No Objection Certificate) Application Workflow

To obtain an official university NOC for industrial training or off-campus internship:

1. **Step 1 – Upload Offer Letter**: Submit the formal company offer letter (with stipend, duration, and job description) on **ERP ➔ Edu-Revolution ➔ Internship Portal**.
2. **Step 2 – Departmental Verification**: Department Internship Coordinator & HOD review and approve within **48 hours**.
3. **Step 3 – Dean Clearance**: Office of the Dean of Academics verifies credit eligibility.
4. **Step 4 – Digital NOC Dispatch**: A digitally signed, QR-coded NOC is generated and emailed to your employer and student inbox.
"""
    },
    {
        "patterns": [
            ("minimum", "stipend"), ("stipend", "policy"), ("stipend", "criteria"),
            ("stipend", "requirement"), ("lowest", "stipend")
        ],
        "answer": """### 💵 University Minimum Stipend Policy

- **6-Month Full-Time Industrial Internships (Final Year)**:
  - Minimum mandatory stipend: **₹15,000 per month** for engineering/technology roles.
  - Unpaid internships are only permitted for research institutions (e.g. IITs, IISc, CSIR, DRDO) with Dean pre-authorization.
- **Summer Internships (2 Months)**: Stipend is recommended but optional for non-credit summer industrial training.
"""
    },
    {
        "patterns": [
            ("internship", "diary"), ("weekly", "report"), ("internship", "credits"),
            ("internship", "evaluation"), ("internship", "presentation"), ("diary", "submission")
        ],
        "answer": """### 📓 Internship Diary Submission & Evaluation Metrics

- **Bi-Weekly Log**: Submit bi-weekly work summary reports on the portal signed/verified by your external company mentor.
- **Evaluation Breakdown (Total 100 Marks / 10 Credits)**:
  - **40%**: Continuous assessment based on bi-weekly diary logs and company supervisor appraisal.
  - **30%**: Comprehensive technical project report submission.
  - **30%**: Final viva-voce examination and demonstration before university faculty panel.
"""
    },
    {
        "patterns": [
            ("placement", "eligibility"), ("campus", "drive"), ("placement", "criteria"),
            ("pep", "classes"), ("placement", "rules"), ("sit for", "placement")
        ],
        "answer": """### 💼 Campus Placement Drive Eligibility Rules

To register for tier-1 and dream campus recruitment drives:

1. **CGPA Requirement**: Minimum **6.50 CGPA** (Tier-1 Dream companies typically require 7.50+).
2. **Backlogs**: Maximum 1 active backlog permitted at the time of drive registration; must be cleared prior to joining.
3. **PEP Attendance**: Minimum **75% attendance** in Professional Enhancement Programme (PEP) aptitude & soft skills classes.
"""
    }
]

EDUREV_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_internship_files",
            "description": (
                "Query internship file approvals and NOC progress. "
                "Table: internship_files(file_id, university_id, company_name, role_title, internship_type, "
                "stipend_monthly, file_status, current_desk, hod_approval, dean_approval, noc_issued, coordinator_name, coordinator_cabin, remarks)"
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
            "name": "search_internship_guidelines",
            "description": "FAISS search over university guidelines for NOC generation, minimum stipend, weekly report diary, and credits.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"]
            }
        }
    }
]

TOOL_REGISTRY = {
    "query_internship_files": run_db_query,
    "search_internship_guidelines": edurev_rag.search
}


class EduRevolutionAgent:
    """
    Edu-Revolution Agent:
    1. Checks zero-cost FAQs first to bypass database queries and vector RAG operations.
    2. If personalized query, executes live internship_files SQL lookup and guidelines search.
    """
    def run(self, query: str, session: StudentSession) -> str:
        # Step 1: Zero-cost FAQ Check
        faq_match = match_faq(query, EDUREV_FAQS)
        if faq_match:
            console.print("[bold green]  ⚡ [Edu-Rev Agent] FAQ Hit -> Bypassing Database & RAG (₹0 Token Cost)[/bold green]")
            return faq_match

        # Step 2: Personalized Inquiry via DB + RAG
        system_prompt = f"""You are the Edu-Revolution & Career Services Agent for the University.
Track industrial internship files, NOC status, HOD/Dean sign-offs, and coordinator office locations.

STUDENT PROFILE:
- Name: {session.full_name}
- Registration ID: {session.university_id}

Instructions:
1. Always filter internship records using university_id = '{session.university_id}'.
2. Read the student's question carefully and provide a concise, point-to-point answer within 2 to 3 lines.
3. Do not write long paragraphs. Present status or answers directly and concisely.
"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query}
        ]

        for _ in range(3):
            res = client.chat.completions.create(model=AGENT_MODEL, messages=messages, tools=EDUREV_TOOLS, temperature=0.0)
            msg = res.choices[0].message
            messages.append(msg)
            if not msg.tool_calls:
                return msg.content or ""

            for call in msg.tool_calls:
                fn_name = call.function.name
                args = json.loads(call.function.arguments)
                console.print(f"[dim yellow]💼 [Edu-Rev Tool] `{fn_name}` -> {args}[/dim yellow]")

                if fn_name == "query_internship_files":
                    output = run_db_query(args.get("sql_query", ""), authenticated_student_id=session.university_id)
                elif fn_name == "search_internship_guidelines":
                    output = edurev_rag.search(args.get("query", ""))
                else:
                    output = "Tool missing."
                messages.append({"role": "tool", "tool_call_id": call.id, "content": str(output)})

        final = client.chat.completions.create(model=AGENT_MODEL, messages=messages, tools=EDUREV_TOOLS, tool_choice="none")
        return final.choices[0].message.content or ""


edurev_agent = EduRevolutionAgent()