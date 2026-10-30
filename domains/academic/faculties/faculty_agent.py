import json
from config import client, AGENT_MODEL, console
from core.base_rag import DepartmentVectorStore
from core.db_engine import run_db_query

class FacultyAgent:
    def __init__(self, faculty_id: str, faculty_name: str, departments: list[str], faculty_folder: str):
        self.faculty_id = faculty_id
        self.faculty_name = faculty_name
        self.departments = departments
        self.stores = {
            dept: DepartmentVectorStore(faculty_id, dept, faculty_folder)
            for dept in departments
        }

    def run(self, query: str, session=None) -> str:
        dept_options = ", ".join(self.departments)
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "search_department_syllabus",
                    "description": f"Search syllabus, practical labs, and course topics in {self.faculty_name}: [{dept_options}].",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "department": {"type": "string", "enum": self.departments},
                            "search_terms": {"type": "string"}
                        },
                        "required": ["department", "search_terms"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "query_course_database",
                    "description": "Query live SQL tables: courses (course_code, course_name, credits, department_id, instructor_name, schedule, room_number).",
                    "parameters": {
                        "type": "object",
                        "properties": {"sql_query": {"type": "string"}},
                        "required": ["sql_query"]
                    }
                }
            }
        ]

        messages = [
            {
                "role": "system",
                "content": f"You are the Dean/Lead Agent for {self.faculty_name}. "
                           f"Manage inquiries across departments: {dept_options}. "
                           f"Use `search_department_syllabus` for course outlines and `query_course_database` for class schedules. "
                           f"Read the student's question carefully and provide a concise, point-to-point answer within 2 to 3 lines. "
                           f"Do not write long paragraphs."
            },
            {"role": "user", "content": query}
        ]

        for _ in range(3):
            res = client.chat.completions.create(model=AGENT_MODEL, messages=messages, tools=tools, temperature=0.0)
            msg = res.choices[0].message
            messages.append(msg)
            if not msg.tool_calls:
                return msg.content or ""

            for call in msg.tool_calls:
                fn_name = call.function.name
                args = json.loads(call.function.arguments)
                console.print(f"[dim]    [{self.faculty_id}] Tool `{fn_name}` -> {args}[/dim]")

                if fn_name == "search_department_syllabus":
                    target_dept = args.get("department")
                    search_txt = args.get("search_terms")
                    output = self.stores[target_dept].search(search_txt) if target_dept in self.stores else "Invalid department."
                elif fn_name == "query_course_database":
                    output = run_db_query(args.get("sql_query", ""), session=session)
                else:
                    output = "Tool not found."

                messages.append({"role": "tool", "tool_call_id": call.id, "content": str(output)})

        final = client.chat.completions.create(model=AGENT_MODEL, messages=messages, tools=tools, tool_choice="none")
        return final.choices[0].message.content or ""