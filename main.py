# main.py
import sys
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.table import Table
from rich.prompt import Prompt
from rich.theme import Theme

from core.session import StudentSession, UserSession
from orchestrator.router import orchestrate_query
from config import console


def render_welcome_header():
    console.print()
    banner = (
        "[bold deep_sky_blue1]🎓 UNIVERSITY INTELLIGENT MULTI-AGENT PORTAL[/bold deep_sky_blue1]\n"
        "[dim]Enterprise Student & Campus Operations Assistance[/dim]"
    )
    console.print(Panel(banner, border_style="dodger_blue1", expand=False, padding=(1, 4)))
    console.print()


def render_session_card(session: StudentSession):
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_row("[bold cyan]Student Name:[/bold cyan]", f"[bold white]{session.full_name}[/bold white]")
    table.add_row("[bold cyan]University ID:[/bold cyan]", f"[bold yellow]{session.university_id}[/bold yellow]")
    table.add_row("[bold cyan]Department:[/bold cyan]", f"[green]{session.department_id.replace('_', ' ').title()} ({session.faculty_id.title()})[/green]")
    table.add_row("[bold cyan]Semester:[/bold cyan]", f"Semester {session.semester}")
    table.add_row("[bold cyan]Faculty Mentor:[/bold cyan]", f"{session.mentor_name} ({session.mentor_cabin})")
    table.add_row("[bold cyan]Courses:[/bold cyan]", f"[dim]{', '.join(session.enrolled_courses) if session.enrolled_courses else 'None'}[/dim]")
    table.add_row("[bold cyan]Access Level:[/bold cyan]", "[green]Verified Student (Read-Only)[/green]")

    console.print(Panel(table, title="[bold white]Active Student Session[/bold white]", border_style="cyan", padding=(0, 1)))
    console.print("[dim]Ask about fees, courses, professors, exams, seating, or internships. Type [bold red]'exit'[/bold red] to quit.[/dim]\n")


def main():
    render_welcome_header()

    # 1. Single Login Prompt
    reg_input = Prompt.ask("[bold cyan]👤 Enter University Email or Roll No[/bold cyan]", default="12204521").strip()
    if not reg_input:
        console.print("[red]Registration number is required to login.[/red]")
        sys.exit(1)

    with console.status("[bold green]Verifying credentials against database...", spinner="dots"):
        session = StudentSession(registration_no=reg_input)

    console.clear()
    render_welcome_header()
    render_session_card(session)

    # 2. Interactive Loop
    while True:
        try:
            user_input = Prompt.ask(f"[bold spring_green3]💬 {session.full_name}[/bold spring_green3]").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit", "q", "logout"]:
                console.print("\n[dim]Session closed. Have a great day![/dim]\n")
                break

            with console.status("[bold dodger_blue1]Consulting Multi-Agent System...", spinner="arc"):
                response = orchestrate_query(user_input, session=session)

            console.print()
            console.print(
                Panel(
                    Markdown(response),
                    title="[bold dodger_blue1]University Portal Assistant[/bold dodger_blue1]",
                    border_style="dodger_blue1",
                    padding=(1, 2)
                )
            )
            console.print()

        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Session closed. Goodbye![/dim]\n")
            break


if __name__ == "__main__":
    main()