import sqlite3
import uuid
import json
from config import DB_PATH, console

class QueryTracker:
    def __init__(self, university_id: str, student_name: str, email: str, raw_query: str):
        self.query_id = f"QRY-{uuid.uuid4().hex[:8].upper()}"
        self.university_id = university_id
        self.student_name = student_name
        self.email = email
        self.raw_query = raw_query
        self.hops = []
        self.current_agent = "Top Orchestrator"

    def log_hop(self, from_agent: str, to_agent: str, action_type: str, tool_name: str = None, payload: dict = None, output: str = None):
        hop_record = {
            "hop_number": len(self.hops) + 1,
            "from_agent": from_agent,
            "to_agent": to_agent,
            "action_type": action_type,
            "tool_name": tool_name or "N/A",
            "payload_input": json.dumps(payload or {}),
            "observation_output": str(output or "")[:500]
        }
        self.hops.append(hop_record)
        self.current_agent = to_agent
        console.print(f"[dim grey]📍 [Audit Hop #{hop_record['hop_number']}] {from_agent} ➔ {to_agent} ({action_type})[/dim grey]")

    def finalize(self, resolution_type: str, ticket_id: str = None):
        trajectory_str = " ➔ ".join([h["from_agent"] for h in self.hops] + [self.current_agent])
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO query_audit_logs (
                    query_id, university_id, student_name, university_email,
                    raw_query, final_resolution_type, ticket_id, total_hops, full_trajectory
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                self.query_id, self.university_id, self.student_name, self.email,
                self.raw_query, resolution_type, ticket_id, len(self.hops), trajectory_str
            ))

            for h in self.hops:
                cursor.execute("""
                    INSERT INTO query_hops (
                        query_id, hop_number, from_agent, to_agent,
                        action_type, tool_name, payload_input, observation_output
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    self.query_id, h["hop_number"], h["from_agent"], h["to_agent"],
                    h["action_type"], h["tool_name"], h["payload_input"], h["observation_output"]
                ))

            conn.commit()
            conn.close()
        except Exception as e:
            console.print(f"[red]Audit log persistence warning: {e}[/red]")