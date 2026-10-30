import argparse
import sqlite3
import datetime
import json
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from config import DB_PATH

console = Console()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def view_ticket(ticket_id: str):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT t.*, q.query_id, q.full_trajectory, q.total_hops
        FROM helpdesk_tickets t
        LEFT JOIN query_audit_logs q ON t.ticket_id = q.ticket_id
        WHERE LOWER(t.ticket_id) = LOWER(?)
    """, (ticket_id.strip(),))
    ticket = cursor.fetchone()

    if not ticket:
        console.print(f"[bold red]❌ Ticket '{ticket_id}' not found.[/bold red]")
        conn.close()
        return None

    status_style = "green" if ticket["status"] == "RESOLVED" else "bold yellow"
    overview = (
        f"[bold]Student:[/bold] {ticket['student_name']} ([cyan]{ticket['university_id']}[/cyan])\n"
        f"[bold]Email:[/bold] {ticket['university_email']} | [bold]Dept:[/bold] {ticket['department_id']}\n"
        f"[bold]Category:[/bold] {ticket['category']} | [bold]Status:[/bold] [{status_style}]{ticket['status']}[/{status_style}]\n"
        f"[bold]Created At:[/bold] {ticket['created_at']}\n"
        f"─────────────────────────────────────────────────────────────\n"
        f"[bold white]Query & Context:[/bold white]\n{ticket['query_text']}\n"
        f"─────────────────────────────────────────────────────────────\n"
        f"[bold red]Escalation Reason:[/bold red] {ticket['escalation_reason']}\n"
        f"[bold yellow]Full Trajectory:[/bold yellow] {ticket['full_trajectory'] or 'N/A'}"
    )
    console.print(Panel(overview, title=f"[bold cyan]Inspection: {ticket['ticket_id']}[/bold cyan]", border_style="cyan"))

    if ticket["query_id"]:
        cursor.execute("""
            SELECT hop_number, from_agent, to_agent, action_type, tool_name, payload_input, observation_output
            FROM query_hops
            WHERE query_id = ?
            ORDER BY hop_number ASC
        """, (ticket["query_id"],))
        hops = cursor.fetchall()

        if hops:
            table = Table(title=f"Detailed Trajectory Hops ({ticket['query_id']})", border_style="dim")
            table.add_column("Hop", style="cyan", width=5)
            table.add_column("From ➔ To", style="yellow")
            table.add_column("Action / Tool", style="magenta")
            table.add_column("Payload / Args", style="dim", max_width=40)
            table.add_column("Observation Preview", style="white", max_width=45)

            for h in hops:
                try:
                    payload = json.dumps(json.loads(h["payload_input"]))[:30] + "..."
                except Exception:
                    payload = h["payload_input"][:30]

                table.add_row(
                    str(h["hop_number"]),
                    f"{h['from_agent']} ➔ {h['to_agent']}",
                    f"{h['action_type']} ({h['tool_name']})",
                    payload,
                    (h["observation_output"] or "").replace("\n", " ")[:40] + "..."
                )
            console.print(table)

    if ticket["status"] == "RESOLVED":
        console.print(Panel(
            f"[bold green]Resolved By:[/bold green] {ticket['assigned_officer']}\n"
            f"[bold green]Resolved At:[/bold green] {ticket['resolved_at']}\n"
            f"[bold white]Resolution Notes:[/bold white] {ticket['human_resolution_notes']}",
            title="[bold green]Resolution Details[/bold green]",
            border_style="green"
        ))

    conn.close()
    return ticket

def resolve_ticket(ticket_id: str, officer_name: str, notes: str):
    conn = get_db()
    cursor = conn.cursor()
    now_ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        UPDATE helpdesk_tickets
        SET status = 'RESOLVED',
            assigned_officer = ?,
            human_resolution_notes = ?,
            resolved_at = ?
        WHERE LOWER(ticket_id) = LOWER(?)
    """, (officer_name, notes, now_ts, ticket_id.strip()))

    if cursor.rowcount > 0:
        conn.commit()
        console.print(f"[bold green]✅ Ticket {ticket_id} resolved by {officer_name}.[/bold green]")
    else:
        console.print(f"[bold red]❌ Ticket {ticket_id} not found.[/bold red]")
    conn.close()

def list_open():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT ticket_id, university_id, student_name, category, escalation_reason, created_at
        FROM helpdesk_tickets
        WHERE status = 'OPEN'
        ORDER BY created_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        console.print("[bold green]✨ No open helpdesk tickets.[/bold green]")
        return

    table = Table(title="📋 Open Helpdesk Escalations", border_style="yellow")
    table.add_column("Ticket ID", style="bold cyan")
    table.add_column("Roll No", style="dim")
    table.add_column("Student", style="white")
    table.add_column("Category", style="magenta")
    table.add_column("Reason", style="yellow")
    table.add_column("Created", style="dim")

    for r in rows:
        table.add_row(r["ticket_id"], r["university_id"], r["student_name"], r["category"], r["escalation_reason"][:35] + "...", r["created_at"])
    console.print(table)

def main():
    parser = argparse.ArgumentParser(description="University Helpdesk Admin CLI")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list")

    view_cmd = sub.add_parser("view")
    view_cmd.add_argument("ticket_id", type=str)

    res_cmd = sub.add_parser("resolve")
    res_cmd.add_argument("ticket_id", type=str)
    res_cmd.add_argument("--officer", "-o", type=str)
    res_cmd.add_argument("--notes", "-n", type=str)

    args = parser.parse_args()

    if args.command == "list":
        list_open()
    elif args.command == "view":
        ticket = view_ticket(args.ticket_id)
        if ticket and ticket["status"] == "OPEN":
            if Confirm.ask("\nResolve this ticket now?"):
                officer = Prompt.ask("Officer Name")
                notes = Prompt.ask("Resolution Notes")
                resolve_ticket(args.ticket_id, officer, notes)
    elif args.command == "resolve":
        ticket = view_ticket(args.ticket_id)
        if ticket:
            officer = args.officer or Prompt.ask("Officer Name")
            notes = args.notes or Prompt.ask("Resolution Notes")
            resolve_ticket(args.ticket_id, officer, notes)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()