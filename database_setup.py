import sqlite3
import os
from config import DB_PATH, console

def init_db(force_recreate: bool = False):
    if force_recreate and os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.executescript("""
    -- 1. Student Identity & Profiles
    CREATE TABLE IF NOT EXISTS students (
        student_id TEXT PRIMARY KEY,
        university_id TEXT UNIQUE NOT NULL,
        university_email TEXT UNIQUE NOT NULL,
        full_name TEXT NOT NULL,
        faculty_id TEXT NOT NULL,
        department_id TEXT NOT NULL,
        current_semester INTEGER NOT NULL,
        enrolled_courses TEXT,
        mentor_name TEXT NOT NULL,
        mentor_cabin TEXT NOT NULL
    );

    -- 2. Academic Courses & Schedule
    CREATE TABLE IF NOT EXISTS courses (
        course_code TEXT PRIMARY KEY,
        course_name TEXT NOT NULL,
        credits INTEGER NOT NULL,
        department_id TEXT NOT NULL,
        instructor_name TEXT NOT NULL,
        schedule TEXT NOT NULL,
        room_number TEXT NOT NULL
    );

    -- 3. Administration: Fees & Dues
    CREATE TABLE IF NOT EXISTS student_fees (
        university_id TEXT PRIMARY KEY,
        total_term_fee REAL NOT NULL,
        paid_amount REAL NOT NULL,
        pending_dues REAL NOT NULL,
        due_date TEXT NOT NULL,
        payment_status TEXT NOT NULL,
        scholarship_name TEXT DEFAULT 'None',
        scholarship_waiver REAL DEFAULT 0.0
    );

    -- 4. Administration: Hostel Allotment
    CREATE TABLE IF NOT EXISTS hostel_allocations (
        university_id TEXT PRIMARY KEY,
        hostel_block TEXT NOT NULL,
        room_number TEXT NOT NULL,
        room_type TEXT NOT NULL,
        warden_name TEXT NOT NULL,
        warden_cabin TEXT NOT NULL,
        warden_contact TEXT NOT NULL
    );

    -- 5. Administration: Transport
    CREATE TABLE IF NOT EXISTS transport_routes (
        route_id TEXT PRIMARY KEY,
        route_name TEXT NOT NULL,
        pickup_point TEXT NOT NULL,
        morning_pickup_time TEXT NOT NULL,
        evening_drop_time TEXT NOT NULL,
        bus_number TEXT NOT NULL
    );

    -- 6. Examination: Datesheets & Seating
    CREATE TABLE IF NOT EXISTS exam_datesheets (
        course_code TEXT NOT NULL,
        exam_type TEXT NOT NULL,
        exam_date TEXT NOT NULL,
        session_time TEXT NOT NULL,
        venue_center TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS seating_arrangements (
        university_id TEXT NOT NULL,
        course_code TEXT NOT NULL,
        room_no TEXT NOT NULL,
        desk_no TEXT NOT NULL,
        invigilator_name TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS grade_records (
        university_id TEXT NOT NULL,
        course_code TEXT NOT NULL,
        grade TEXT NOT NULL,
        credits INTEGER NOT NULL,
        semester INTEGER NOT NULL
    );

    -- 7. Edu-Revolution: Internship Files
    CREATE TABLE IF NOT EXISTS internship_files (
        file_id TEXT PRIMARY KEY,
        university_id TEXT NOT NULL,
        company_name TEXT NOT NULL,
        role_title TEXT NOT NULL,
        internship_type TEXT NOT NULL,
        stipend_monthly REAL,
        file_status TEXT NOT NULL,
        current_desk TEXT NOT NULL,
        hod_approval TEXT NOT NULL,
        dean_approval TEXT NOT NULL,
        noc_issued INTEGER NOT NULL DEFAULT 0,
        coordinator_name TEXT NOT NULL,
        coordinator_cabin TEXT NOT NULL,
        remarks TEXT
    );

    -- 8. Helpdesk Escalation & Audit Trail
    CREATE TABLE IF NOT EXISTS helpdesk_tickets (
        ticket_id TEXT PRIMARY KEY,
        university_id TEXT NOT NULL,
        student_name TEXT NOT NULL,
        university_email TEXT NOT NULL,
        department_id TEXT NOT NULL,
        query_text TEXT NOT NULL,
        escalation_reason TEXT NOT NULL,
        category TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'OPEN',
        assigned_officer TEXT DEFAULT 'Unassigned',
        human_resolution_notes TEXT DEFAULT '',
        current_stage TEXT DEFAULT 'Hostel Office',
        next_stage TEXT DEFAULT 'Dean (Hostel Affairs)',
        estimated_resolution TEXT DEFAULT 'In 2-3 Working Days',
        handler_email TEXT DEFAULT 'support@lpu.in',
        stage_progress INTEGER DEFAULT 2,
        last_inquiry_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        inquiry_count INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        resolved_at TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS query_audit_logs (
        query_id TEXT PRIMARY KEY,
        university_id TEXT NOT NULL,
        student_name TEXT NOT NULL,
        university_email TEXT NOT NULL,
        raw_query TEXT NOT NULL,
        final_resolution_type TEXT NOT NULL,
        ticket_id TEXT,
        total_hops INTEGER DEFAULT 0,
        full_trajectory TEXT NOT NULL,
        prompt_tokens INTEGER DEFAULT 0,
        completion_tokens INTEGER DEFAULT 0,
        total_tokens INTEGER DEFAULT 0,
        latency_ms REAL DEFAULT 0.0,
        arize_trace_id TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS query_hops (
        hop_id INTEGER PRIMARY KEY AUTOINCREMENT,
        query_id TEXT NOT NULL,
        hop_number INTEGER NOT NULL,
        from_agent TEXT NOT NULL,
        to_agent TEXT NOT NULL,
        action_type TEXT NOT NULL,
        tool_name TEXT,
        payload_input TEXT,
        observation_output TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- 9. Student Feedback
    CREATE TABLE IF NOT EXISTS student_feedback (
        feedback_id TEXT PRIMARY KEY,
        university_id TEXT NOT NULL,
        student_name TEXT NOT NULL,
        category TEXT NOT NULL,
        rating INTEGER NOT NULL CHECK(rating >= 1 AND rating <= 5),
        resolution_quality TEXT NOT NULL,
        recommendation TEXT NOT NULL,
        comments TEXT NOT NULL,
        suggestions TEXT,
        submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        ip_address TEXT DEFAULT '127.0.0.1'
    );
    """)

    # Ensure all migration columns exist on existing database
    for col, ctype in [
        ("current_stage", "TEXT DEFAULT 'Hostel Office'"),
        ("next_stage", "TEXT DEFAULT 'Dean (Hostel Affairs)'"),
        ("estimated_resolution", "TEXT DEFAULT 'In 2-3 Working Days'"),
        ("handler_email", "TEXT DEFAULT 'support@lpu.in'"),
        ("stage_progress", "INTEGER DEFAULT 2"),
        ("last_inquiry_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
        ("inquiry_count", "INTEGER DEFAULT 1")
    ]:
        try:
            cursor.execute(f"ALTER TABLE helpdesk_tickets ADD COLUMN {col} {ctype}")
        except Exception:
            pass

    for col, ctype in [
        ("prompt_tokens", "INTEGER DEFAULT 0"),
        ("completion_tokens", "INTEGER DEFAULT 0"),
        ("total_tokens", "INTEGER DEFAULT 0"),
        ("latency_ms", "REAL DEFAULT 0.0"),
        ("arize_trace_id", "TEXT DEFAULT ''")
    ]:
        try:
            cursor.execute(f"ALTER TABLE query_audit_logs ADD COLUMN {col} {ctype}")
        except Exception:
            pass

    cursor.execute("SELECT COUNT(*) FROM students")
    has_students = cursor.fetchone()[0] > 0

    if not has_students:
        cursor.executemany("""
            INSERT INTO students VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            ("STU101", "12204521", "aditya_sharma_3452@lpu.in", "Aditya Sharma", "engineering", "computer_science", 6, "CSE423, CSE312, MATH204", "Dr. Rajesh Sharma", "Block 34, Cabin 304 (3rd Floor)"),
            ("STU102", "12208934", "priya_patel_1984@lpu.in", "Priya Patel", "engineering", "mechanical", 4, "ME201, ME204, MATH204", "Prof. Vikram Seth", "Block 36, Room 102"),
            ("STU103", "12301142", "rahul_mehta_7712@lpu.in", "Rahul Mehta", "finance", "accounting", 2, "ACC101, FIN102", "Dr. Sneha Nair", "Block 14, Cabin 412")
        ])

        cursor.executemany("""
            INSERT INTO courses VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [
            ("CSE423", "Cloud Computing & DevOps", 4, "computer_science", "Dr. A. Verma", "Mon/Wed 09:00 - 11:00 AM", "Room 34-401"),
            ("CSE312", "Distributed Systems", 4, "computer_science", "Dr. P. Kaur", "Tue/Thu 11:00 AM - 01:00 PM", "Lab 34-202"),
            ("ME201", "Applied Thermodynamics", 3, "mechanical", "Prof. Vikram Seth", "Mon/Wed 02:00 - 04:00 PM", "Workshop Hall 2"),
            ("ACC101", "Principles of Accounting", 4, "accounting", "Dr. Sneha Nair", "Tue/Fri 10:00 AM - 12:00 PM", "Block 14-105")
        ])

        cursor.executemany("""
            INSERT INTO student_fees VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            ("12204521", 120000.0, 120000.0, 0.0, "2026-08-15", "Clear", "Merit Scholarship Top 5%", 30000.0),
            ("12208934", 115000.0, 80000.0, 35000.0, "2026-11-10", "Pending", "None", 0.0),
            ("12301142", 95000.0, 95000.0, 0.0, "2026-08-15", "Clear", "None", 0.0)
        ])

        cursor.executemany("""
            INSERT INTO hostel_allocations VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [
            ("12204521", "Hostel Block 4 (Boys)", "Room 412", "2-Seater AC", "Mr. Sukhwinder Singh", "Block 4 Ground Floor", "+91-9876543210"),
            ("12208934", "Hostel Block 7 (Girls)", "Room 205", "3-Seater AC", "Dr. Geeta Sharma", "Block 7 Lobby", "+91-9876543211")
        ])

        cursor.executemany("""
            INSERT INTO transport_routes VALUES (?, ?, ?, ?, ?, ?)
        """, [
            ("R-01", "Model Town Route", "City Center Fountain", "07:30 AM", "05:30 PM", "PB-08-AB-1022"),
            ("R-02", "Jalandhar Cantt Express", "Cantt Station Gate 2", "07:15 AM", "05:45 PM", "PB-08-AB-4055")
        ])

        cursor.executemany("""
            INSERT INTO exam_datesheets VALUES (?, ?, ?, ?, ?)
        """, [
            ("CSE423", "End-Term Practical", "2026-11-20", "09:30 AM - 12:30 PM", "Central Computing Complex Lab 3"),
            ("CSE312", "End-Term Theory", "2026-11-24", "01:30 PM - 04:30 PM", "Block 38 Examination Hall B"),
            ("ME201", "End-Term Theory", "2026-11-22", "09:30 AM - 12:30 PM", "Block 36 Hall A")
        ])

        cursor.executemany("""
            INSERT INTO seating_arrangements VALUES (?, ?, ?, ?, ?)
        """, [
            ("12204521", "CSE423", "Room 34-401", "Desk CS-14", "Prof. R. Khanna"),
            ("12204521", "CSE312", "Hall B-2", "Desk CS-88", "Dr. T. Chawla"),
            ("12208934", "ME201", "Hall A-1", "Desk ME-04", "Prof. K. Das")
        ])

        cursor.executemany("""
            INSERT INTO grade_records VALUES (?, ?, ?, ?, ?)
        """, [
            ("12204521", "MATH204", "A+", 4, 4),
            ("12204521", "CSE202", "O", 4, 4),
            ("12204521", "CSE310", "A", 3, 5)
        ])

        cursor.executemany("""
            INSERT INTO internship_files VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            ("FILE-INT-2026-9042", "12204521", "Google Cloud India", "Cloud Engineering Intern", "6-Month Industrial", 60000.0, "Under Review with Dean", "Dean of Academics Office", "Approved", "Pending", 0, "Dr. Gagandeep Sethi", "Block 34, Cabin 201 (2nd Floor)", "HOD approval verified. Final Dean clearance pending."),
            ("FILE-INT-2026-8812", "12208934", "Tata Motors", "R&D Mechanical Intern", "Summer Internship", 25000.0, "Approved", "NOC Generation Cell", "Approved", "Approved", 1, "Prof. Vikram Seth", "Block 36, Room 102", "Official NOC generated and dispatched.")
        ])

    cursor.execute("SELECT COUNT(*) FROM helpdesk_tickets")
    has_tickets = cursor.fetchone()[0] > 0

    if not has_tickets:
        initial_tickets = [
            (
                "RMS20261110A5A7", "12204521", "Aditya Sharma", "aditya_sharma_4521@lpu.in", "computer_science",
                "My exams are clashing on the same date. Can you just resolve that thing?",
                "Automated inquiry (Examination)", "Examination", "In Progress", "Controller of Examinations",
                "[Official Human Resolution — Controller of Examinations]\n\nDear student, we have identified the scheduling overlap and alerted the timetable committee to review alternate reserve slots.",
                "Timetable Committee Review", "Controller of Examinations", "In 2-3 Working Days", "coe@lpu.in",
                2, "2026-11-10 12:05:35", "2026-11-10 12:39:30", 2, None
            ),
            (
                "RMS20261027A277", "12204521", "Aditya Sharma", "aditya_sharma_4521@lpu.in", "computer_science",
                "What is my university ID and registration profile?",
                "Automated inquiry (General)", "General Inquiry", "Resolved", "Central University Helpdesk",
                "[Official Human Resolution — Central University Helpdesk]\n\nDear student, your academic profile is verified and active with 6th semester standing in Computer Science Engineering.",
                "Final Resolution", "Completed", "Same Day", "helpdesk@lpu.in",
                4, "2026-10-27 10:15:00", "2026-10-27 10:15:00", 1, "2026-10-27 10:15:05"
            ),
            (
                "RMS20261027474A", "12204521", "Aditya Sharma", "aditya_sharma_4521@lpu.in", "computer_science",
                "Hostel Room 412 AC maintenance and filter service request",
                "Automated inquiry (Hostel Related)", "Hostel Related", "Resolved", "Hostel Warden Office",
                "[Official Human Resolution — Hostel Warden Office]\n\nDear student, the maintenance team has serviced the air conditioning unit and replaced the filter in Room 412.",
                "Final Resolution", "Completed", "Same Day", "warden.bh4@lpu.in",
                4, "2026-10-25 14:20:00", "2026-10-25 14:20:00", 1, "2026-10-26 11:00:00"
            ),
            (
                "RMS2026102715D2", "12204521", "Aditya Sharma", "aditya_sharma_4521@lpu.in", "computer_science",
                "Fee payment receipt generation for term 6",
                "Automated inquiry (Administration)", "Fee Payment", "Resolved", "Finance & Accounts Desk",
                "[Official Human Resolution — Finance & Accounts Desk]\n\nDear student, your payment has been credited and the term clearance receipt is available.",
                "Final Resolution", "Completed", "Same Day", "accounts@lpu.in",
                4, "2026-10-20 09:30:00", "2026-10-20 09:30:00", 1, "2026-10-20 09:30:04"
            )
        ]
        cursor.executemany("""
            INSERT INTO helpdesk_tickets (
                ticket_id, university_id, student_name, university_email, department_id,
                query_text, escalation_reason, category, status, assigned_officer,
                human_resolution_notes, current_stage, next_stage, estimated_resolution,
                handler_email, stage_progress, created_at, last_inquiry_at, inquiry_count, resolved_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, initial_tickets)

        initial_audits = [
            (
                "QRY-20261110-01", "12204521", "Aditya Sharma", "aditya_sharma_4521@lpu.in",
                "My exams are clashing on the same date. Can you just resolve that thing?",
                "GATEWAY_IN_PROGRESS", "RMS20261110A5A7", 2, "Top Orchestrator ➔ Examination ➔ In Progress",
                1200, 150, 1350, 1250.0, "2026-11-10 12:05:35"
            ),
            (
                "QRY-20261027-01", "12204521", "Aditya Sharma", "aditya_sharma_4521@lpu.in",
                "What is my university ID and registration profile?",
                "AI_RESOLVED", "RMS20261027A277", 1, "Top Orchestrator ➔ General ➔ AI_RESOLVED",
                850, 95, 945, 820.0, "2026-10-27 10:15:00"
            ),
            (
                "QRY-20261025-01", "12204521", "Aditya Sharma", "aditya_sharma_4521@lpu.in",
                "What is my current fee balance and hostel room?",
                "AI_RESOLVED", "RMS20261027474A", 1, "Top Orchestrator ➔ Administration ➔ AI_RESOLVED",
                920, 110, 1030, 910.0, "2026-10-25 14:20:00"
            ),
            (
                "QRY-20261020-01", "12204521", "Aditya Sharma", "aditya_sharma_4521@lpu.in",
                "Show my exam datesheets and seating desk arrangement",
                "AI_RESOLVED", "RMS2026102715D2", 1, "Top Orchestrator ➔ Examination ➔ AI_RESOLVED",
                980, 130, 1110, 890.0, "2026-10-20 09:30:00"
            )
        ]
        cursor.executemany("""
            INSERT INTO query_audit_logs (
                query_id, university_id, student_name, university_email,
                raw_query, final_resolution_type, ticket_id, total_hops,
                full_trajectory, prompt_tokens, completion_tokens,
                total_tokens, latency_ms, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, initial_audits)

    conn.commit()
    conn.close()
    console.print(f"[bold green]✅ Database initialized and seeded at: {DB_PATH}[/bold green]")

if __name__ == "__main__":
    init_db()
