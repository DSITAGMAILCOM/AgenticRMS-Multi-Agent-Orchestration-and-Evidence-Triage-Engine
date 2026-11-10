import sqlite3
import uuid
import json
import time
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
        self.start_time = time.perf_counter()
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0
        self.latency_ms = 0.0
        self.arize_trace_id = ""

    def add_tokens(self, prompt_tokens: int = 0, completion_tokens: int = 0, total_tokens: int = 0):
        self.prompt_tokens += int(prompt_tokens or 0)
        self.completion_tokens += int(completion_tokens or 0)
        self.total_tokens += int(total_tokens or (prompt_tokens + completion_tokens))

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
        if self.latency_ms <= 0.0:
            self.latency_ms = round((time.perf_counter() - self.start_time) * 1000, 2)

        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()

            # Ensure columns exist in case of legacy schema
            for col_def in [
                ("prompt_tokens", "INTEGER DEFAULT 0"),
                ("completion_tokens", "INTEGER DEFAULT 0"),
                ("total_tokens", "INTEGER DEFAULT 0"),
                ("latency_ms", "REAL DEFAULT 0.0"),
                ("arize_trace_id", "TEXT DEFAULT ''")
            ]:
                try:
                    cursor.execute(f"ALTER TABLE query_audit_logs ADD COLUMN {col_def[0]} {col_def[1]}")
                except Exception:
                    pass

            cursor.execute("""
                INSERT OR REPLACE INTO query_audit_logs (
                    query_id, university_id, student_name, university_email,
                    raw_query, final_resolution_type, ticket_id, total_hops,
                    full_trajectory, prompt_tokens, completion_tokens, total_tokens,
                    latency_ms, arize_trace_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                self.query_id, self.university_id, self.student_name, self.email,
                self.raw_query, resolution_type, ticket_id, len(self.hops),
                trajectory_str, self.prompt_tokens, self.completion_tokens,
                self.total_tokens, self.latency_ms, self.arize_trace_id
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

            console.print(
                f"[bold cyan]📊 [Query Telemetry] {self.query_id} | "
                f"⚡ Tokens: {self.total_tokens} (p:{self.prompt_tokens}, c:{self.completion_tokens}) | "
                f"⏱️ Time: {self.latency_ms}ms | Hops: {len(self.hops)}[/bold cyan]"
            )
        except Exception as e:
            console.print(f"[red]Audit log persistence warning: {e}[/red]")