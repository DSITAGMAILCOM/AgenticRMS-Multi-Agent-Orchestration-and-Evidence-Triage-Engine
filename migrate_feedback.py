# migrate_feedback.py
"""
Database Migration Script: Creates student_feedback table in university.db
and seeds initial verified feedback records.
"""
import sqlite3
import os
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "university.db")

def run_migration():
    print(f"📦 Connecting to database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Create student_feedback table
    cursor.execute("""
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

    # 2. Create index for fast sorting by submission date
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_feedback_submitted_at ON student_feedback (submitted_at DESC);
    """)
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_feedback_university_id ON student_feedback (university_id);
    """)

    conn.commit()

    # 3. Check if table is empty; if so, seed sample feedback
    cursor.execute("SELECT COUNT(*) FROM student_feedback")
    count = cursor.fetchone()[0]

    if count == 0:
        print("🌱 Seeding realistic initial feedback records...")
        now = datetime.now()
        sample_feedback = [
            (
                "FB-2026-001",
                "12204521",
                "Aditya Sharma",
                "Hostel & Living Facilities",
                5,
                "Exceptional / Immediate",
                "Very Likely",
                "The hostel room allotment inquiry was answered instantly with exact warden details and cabin location. Extremely helpful!",
                "Could we also get a push notification when gate pass is approved?",
                (now - timedelta(days=2, hours=3)).strftime("%Y-%m-%d %H:%M:%S"),
                "127.0.0.1"
            ),
            (
                "FB-2026-002",
                "12204521",
                "Aditya Sharma",
                "Fee & Administration",
                4,
                "Satisfactory / Clear",
                "Likely",
                "Point-to-point breakdown of tuition fee ledger and scholarship waiver was accurate and concise.",
                "Add direct payment link integration if possible.",
                (now - timedelta(days=1, hours=5)).strftime("%Y-%m-%d %H:%M:%S"),
                "127.0.0.1"
            ),
            (
                "FB-2026-003",
                "12204522",
                "Priya Patel",
                "Academic Curriculum & Classes",
                5,
                "Exceptional / Immediate",
                "Very Likely",
                "Engineering Dean agent provided the exact CSE423 syllabus units and instructor consultation hours within seconds.",
                "Please add previous year question paper download links.",
                (now - timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S"),
                "127.0.0.1"
            ),
            (
                "FB-2026-004",
                "ANON-8821",
                "Anonymous Student",
                "Campus IT & Wi-Fi",
                4,
                "Satisfactory / Clear",
                "Likely",
                "Wi-Fi MAC registration guide solved my connection issues in Block 34 without needing to visit the IT desk.",
                "Expand Wi-Fi coverage near the open amphitheatre.",
                (now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S"),
                "127.0.0.1"
            )
        ]

        cursor.executemany("""
            INSERT INTO student_feedback (
                feedback_id, university_id, student_name, category, rating,
                resolution_quality, recommendation, comments, suggestions,
                submitted_at, ip_address
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, sample_feedback)
        conn.commit()
        print(f"✅ Seeded {len(sample_feedback)} feedback entries successfully.")
    else:
        print(f"ℹ️ Table student_feedback already has {count} entries.")

    conn.close()
    print("🎉 Database migration completed successfully.")

if __name__ == "__main__":
    run_migration()
