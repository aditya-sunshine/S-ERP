#!/usr/bin/env python3
"""
School ERP — Demo Data Seeder
Creates a realistic single-school demo ready for customer presentation.
Uses only synthetic / fictional data.
"""

import os
import sqlite3
import hashlib
import secrets
import hmac
import random
from datetime import date, datetime, timedelta
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
DB_PATH = os.environ.get("SCHOOL_ERP_DB", str(APP_DIR / "school_erp.db"))

def pw_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260000).hex()
    return f"{salt}${digest}"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
 id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
 role TEXT NOT NULL DEFAULT 'admin', display_name TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS students (
 id INTEGER PRIMARY KEY AUTOINCREMENT, admission_no TEXT UNIQUE NOT NULL, first_name TEXT NOT NULL,
 last_name TEXT DEFAULT '', class_name TEXT NOT NULL, section TEXT DEFAULT '', dob TEXT DEFAULT '',
 gender TEXT DEFAULT '', parent_name TEXT DEFAULT '', parent_phone TEXT DEFAULT '', parent_email TEXT DEFAULT '',
 address TEXT DEFAULT '', admission_date TEXT DEFAULT '', status TEXT DEFAULT 'Active', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS teachers (
 id INTEGER PRIMARY KEY AUTOINCREMENT, employee_no TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
 phone TEXT DEFAULT '', email TEXT DEFAULT '', subject TEXT DEFAULT '', joining_date TEXT DEFAULT '',
 salary REAL DEFAULT 0, status TEXT DEFAULT 'Active', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS attendance (
 id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER NOT NULL REFERENCES students(id),
 attend_date TEXT NOT NULL, status TEXT NOT NULL, note TEXT DEFAULT '', marked_by INTEGER,
 UNIQUE(student_id, attend_date)
);
CREATE TABLE IF NOT EXISTS teacher_attendance (
 id INTEGER PRIMARY KEY AUTOINCREMENT, teacher_id INTEGER NOT NULL REFERENCES teachers(id),
 attend_date TEXT NOT NULL, status TEXT NOT NULL, note TEXT DEFAULT '',
 UNIQUE(teacher_id, attend_date)
);
CREATE TABLE IF NOT EXISTS fee_payments (
 id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER NOT NULL REFERENCES students(id),
 paid_date TEXT NOT NULL, amount REAL NOT NULL CHECK(amount >= 0), fee_type TEXT NOT NULL,
 payment_mode TEXT DEFAULT 'Cash', receipt_no TEXT UNIQUE NOT NULL, note TEXT DEFAULT '', created_by INTEGER
);
CREATE TABLE IF NOT EXISTS expenses (
 id INTEGER PRIMARY KEY AUTOINCREMENT, expense_date TEXT NOT NULL, category TEXT NOT NULL,
 description TEXT NOT NULL, amount REAL NOT NULL CHECK(amount >= 0), payment_mode TEXT DEFAULT 'Cash',
 voucher_no TEXT UNIQUE NOT NULL, created_by INTEGER
);
CREATE TABLE IF NOT EXISTS exams (
 id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, class_name TEXT NOT NULL,
 exam_date TEXT NOT NULL, max_marks REAL NOT NULL DEFAULT 100, academic_year TEXT DEFAULT '', notes TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS results (
 id INTEGER PRIMARY KEY AUTOINCREMENT, exam_id INTEGER NOT NULL REFERENCES exams(id),
 student_id INTEGER NOT NULL REFERENCES students(id), subject TEXT NOT NULL, marks REAL NOT NULL,
 max_marks REAL NOT NULL DEFAULT 100, remarks TEXT DEFAULT '',
 UNIQUE(exam_id, student_id, subject)
);
CREATE TABLE IF NOT EXISTS audit_log (
 id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, username TEXT, action TEXT NOT NULL,
 entity TEXT NOT NULL, entity_id TEXT DEFAULT '', details TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""

def main(force_reset=False):
    """Populate the database with demo data.
    force_reset=True deletes the existing DB first (CLI use).
    When imported by the app, force_reset stays False.
    """
    global DB_PATH
    DB_PATH = os.environ.get("SCHOOL_ERP_DB", str(APP_DIR / "school_erp.db"))

    if force_reset and os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Removed old database: {DB_PATH}")

    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    db.execute("PRAGMA foreign_keys=ON")

    # If students already exist, do not re-seed
    if db.execute("SELECT COUNT(*) FROM students").fetchone()[0] > 0:
        db.close()
        print("Demo data already present — skipping seed.")
        return

    # --- Settings ---
    db.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('school_name', ?)", ("Green Valley Public School",))
    db.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('academic_year', ?)", ("2026-27",))
    db.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('subscription_mode', ?)", ("demo",))
    db.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('school_address', ?)", ("12, Sector 18, Noida, Uttar Pradesh 201301",))
    db.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('school_phone', ?)", ("+91-120-4567890",))

    # --- Users ---
    users = [
        ("admin", "ChangeMe123!", "admin", "Rajesh Sharma (Principal)"),
        ("accountant", "Accountant@1", "accountant", "Priya Mehta (Accountant)"),
        ("teacher1", "Teacher@123", "teacher", "Anita Desai (Class Teacher)"),
        ("teacher2", "Teacher@123", "teacher", "Vikram Singh (Maths)"),
    ]
    for u, p, r, d in users:
        db.execute(
            "INSERT OR IGNORE INTO users(username, password_hash, role, display_name) VALUES(?,?,?,?)",
            (u, pw_hash(p), r, d)
        )

    now = datetime.now().isoformat(timespec="seconds")
    today = date.today()

    # --- Teachers ---
    teachers = [
        ("EMP-001", "Anita Desai", "9876500001", "anita.desai@gvps.edu.in", "English", "2018-06-15", 42000),
        ("EMP-002", "Vikram Singh", "9876500002", "vikram.singh@gvps.edu.in", "Mathematics", "2016-04-01", 48000),
        ("EMP-003", "Sunita Rao", "9876500003", "sunita.rao@gvps.edu.in", "Science", "2019-07-10", 40000),
        ("EMP-004", "Rahul Kapoor", "9876500004", "rahul.kapoor@gvps.edu.in", "Social Studies", "2020-01-20", 38000),
        ("EMP-005", "Meera Iyer", "9876500005", "meera.iyer@gvps.edu.in", "Hindi", "2017-08-05", 41000),
        ("EMP-006", "Arjun Patel", "9876500006", "arjun.patel@gvps.edu.in", "Computer Science", "2021-03-12", 45000),
        ("EMP-007", "Kavita Nair", "9876500007", "kavita.nair@gvps.edu.in", "Physical Education", "2015-11-01", 36000),
        ("EMP-008", "Sanjay Gupta", "9876500008", "sanjay.gupta@gvps.edu.in", "Art & Craft", "2022-06-01", 32000),
    ]
    for emp, name, phone, email, subj, join, sal in teachers:
        db.execute(
            """INSERT INTO teachers(employee_no,name,phone,email,subject,joining_date,salary,status,created_at)
               VALUES(?,?,?,?,?,?,?,?,?)""",
            (emp, name, phone, email, subj, join, sal, "Active", now)
        )

    # --- Students (realistic Indian names, classes 1-10, two sections) ---
    student_data = [
        # Class 1-A
        ("ADM-2026-001", "Aarav", "Sharma", "1", "A", "2019-05-12", "Male", "Rakesh Sharma", "9810001001", "rakesh.sharma@email.com", "Flat 12, Palm Residency, Noida", "2026-04-01"),
        ("ADM-2026-002", "Ananya", "Verma", "1", "A", "2019-08-22", "Female", "Sunita Verma", "9810001002", "sunita.verma@email.com", "Sector 62, Noida", "2026-04-01"),
        ("ADM-2026-003", "Vivaan", "Patel", "1", "A", "2019-03-15", "Male", "Amit Patel", "9810001003", "amit.patel@email.com", "Indirapuram, Ghaziabad", "2026-04-02"),
        ("ADM-2026-004", "Diya", "Singh", "1", "A", "2019-11-05", "Female", "Neha Singh", "9810001004", "neha.singh@email.com", "Sector 137, Noida", "2026-04-02"),
        # Class 1-B
        ("ADM-2026-005", "Kabir", "Mehta", "1", "B", "2019-07-18", "Male", "Rajesh Mehta", "9810001005", "rajesh.mehta@email.com", "Greater Noida West", "2026-04-03"),
        ("ADM-2026-006", "Ishita", "Joshi", "1", "B", "2019-09-30", "Female", "Pooja Joshi", "9810001006", "pooja.joshi@email.com", "Sector 50, Noida", "2026-04-03"),
        # Class 2-A
        ("ADM-2025-011", "Reyansh", "Gupta", "2", "A", "2018-04-10", "Male", "Vikram Gupta", "9810001011", "vikram.gupta@email.com", "Sector 76, Noida", "2025-04-01"),
        ("ADM-2025-012", "Myra", "Kapoor", "2", "A", "2018-06-25", "Female", "Anjali Kapoor", "9810001012", "anjali.kapoor@email.com", "Vasundhara, Ghaziabad", "2025-04-01"),
        ("ADM-2025-013", "Arjun", "Reddy", "2", "A", "2018-01-14", "Male", "Suresh Reddy", "9810001013", "suresh.reddy@email.com", "Sector 120, Noida", "2025-04-02"),
        # Class 3-A
        ("ADM-2024-021", "Saanvi", "Iyer", "3", "A", "2017-05-08", "Female", "Lakshmi Iyer", "9810001021", "lakshmi.iyer@email.com", "Sector 15, Noida", "2024-04-01"),
        ("ADM-2024-022", "Advait", "Nair", "3", "A", "2017-09-19", "Male", "Krishnan Nair", "9810001022", "krishnan.nair@email.com", "Mayur Vihar, Delhi", "2024-04-01"),
        ("ADM-2024-023", "Pari", "Malhotra", "3", "A", "2017-12-03", "Female", "Rohit Malhotra", "9810001023", "rohit.malhotra@email.com", "Sector 93, Noida", "2024-04-02"),
        # Class 4-A
        ("ADM-2023-031", "Vihaan", "Choudhary", "4", "A", "2016-02-28", "Male", "Manoj Choudhary", "9810001031", "manoj.choudhary@email.com", "Sector 62, Noida", "2023-04-01"),
        ("ADM-2023-032", "Aanya", "Bansal", "4", "A", "2016-07-11", "Female", "Deepa Bansal", "9810001032", "deepa.bansal@email.com", "Indirapuram", "2023-04-01"),
        # Class 5-A
        ("ADM-2022-041", "Atharv", "Saxena", "5", "A", "2015-03-22", "Male", "Alok Saxena", "9810001041", "alok.saxena@email.com", "Sector 18, Noida", "2022-04-01"),
        ("ADM-2022-042", "Kiara", "Agarwal", "5", "A", "2015-10-07", "Female", "Shweta Agarwal", "9810001042", "shweta.agarwal@email.com", "Greater Noida", "2022-04-01"),
        ("ADM-2022-043", "Dhruv", "Tiwari", "5", "A", "2015-06-14", "Male", "Pradeep Tiwari", "9810001043", "pradeep.tiwari@email.com", "Sector 137, Noida", "2022-04-02"),
        # Class 6-A
        ("ADM-2021-051", "Anika", "Mishra", "6", "A", "2014-04-18", "Female", "Sanjay Mishra", "9810001051", "sanjay.mishra@email.com", "Sector 50, Noida", "2021-04-01"),
        ("ADM-2021-052", "Shaurya", "Yadav", "6", "A", "2014-08-29", "Male", "Ramesh Yadav", "9810001052", "ramesh.yadav@email.com", "Sector 76, Noida", "2021-04-01"),
        # Class 7-A
        ("ADM-2020-061", "Navya", "Khanna", "7", "A", "2013-01-25", "Female", "Amit Khanna", "9810001061", "amit.khanna@email.com", "Vasundhara", "2020-04-01"),
        ("ADM-2020-062", "Yash", "Bhatt", "7", "A", "2013-11-12", "Male", "Nitin Bhatt", "9810001062", "nitin.bhatt@email.com", "Sector 120, Noida", "2020-04-01"),
        ("ADM-2020-063", "Riya", "Sethi", "7", "A", "2013-05-30", "Female", "Kavita Sethi", "9810001063", "kavita.sethi@email.com", "Sector 15, Noida", "2020-04-02"),
        # Class 8-A
        ("ADM-2019-071", "Krish", "Gill", "8", "A", "2012-09-04", "Male", "Harpreet Gill", "9810001071", "harpreet.gill@email.com", "Sector 62, Noida", "2019-04-01"),
        ("ADM-2019-072", "Sia", "Chopra", "8", "A", "2012-12-16", "Female", "Ritu Chopra", "9810001072", "ritu.chopra@email.com", "Mayur Vihar", "2019-04-01"),
        # Class 9-A
        ("ADM-2018-081", "Aryan", "Thakur", "9", "A", "2011-07-21", "Male", "Vijay Thakur", "9810001081", "vijay.thakur@email.com", "Sector 93, Noida", "2018-04-01"),
        ("ADM-2018-082", "Anvi", "Kulkarni", "9", "A", "2011-03-09", "Female", "Smita Kulkarni", "9810001082", "smita.kulkarni@email.com", "Sector 18, Noida", "2018-04-01"),
        ("ADM-2018-083", "Rohan", "Das", "9", "A", "2011-10-28", "Male", "Bikash Das", "9810001083", "bikash.das@email.com", "Greater Noida", "2018-04-02"),
        # Class 10-A
        ("ADM-2017-091", "Ishaan", "Banerjee", "10", "A", "2010-02-14", "Male", "Subrata Banerjee", "9810001091", "subrata.banerjee@email.com", "Sector 50, Noida", "2017-04-01"),
        ("ADM-2017-092", "Aadhya", "Rao", "10", "A", "2010-06-07", "Female", "Srinivas Rao", "9810001092", "srinivas.rao@email.com", "Sector 76, Noida", "2017-04-01"),
        ("ADM-2017-093", "Veer", "Malik", "10", "A", "2010-09-19", "Male", "Imran Malik", "9810001093", "imran.malik@email.com", "Sector 137, Noida", "2017-04-02"),
        ("ADM-2017-094", "Zara", "Khan", "10", "A", "2010-11-25", "Female", "Farhan Khan", "9810001094", "farhan.khan@email.com", "Indirapuram", "2017-04-02"),
    ]

    for adm, fn, ln, cls, sec, dob, gen, pname, pphone, pemail, addr, adate in student_data:
        db.execute(
            """INSERT INTO students(admission_no,first_name,last_name,class_name,section,dob,gender,
               parent_name,parent_phone,parent_email,address,admission_date,status,created_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (adm, fn, ln, cls, sec, dob, gen, pname, pphone, pemail, addr, adate, "Active", now)
        )

    # --- Student Attendance (last 7 working days) ---
    students = db.execute("SELECT id FROM students WHERE status='Active'").fetchall()
    statuses = ["Present", "Present", "Present", "Present", "Present", "Late", "Absent", "Leave"]
    for day_offset in range(1, 8):
        d = (today - timedelta(days=day_offset)).isoformat()
        for s in students:
            st = random.choice(statuses)
            db.execute(
                "INSERT OR IGNORE INTO attendance(student_id,attend_date,status,note,marked_by) VALUES(?,?,?,?,?)",
                (s["id"], d, st, "", 1)
            )

    # Today's attendance (mostly present)
    for s in students:
        st = random.choice(["Present", "Present", "Present", "Present", "Late", "Absent"])
        db.execute(
            "INSERT OR IGNORE INTO attendance(student_id,attend_date,status,note,marked_by) VALUES(?,?,?,?,?)",
            (s["id"], today.isoformat(), st, "", 1)
        )

    # --- Teacher Attendance ---
    teachers_db = db.execute("SELECT id FROM teachers WHERE status='Active'").fetchall()
    for day_offset in range(0, 6):
        d = (today - timedelta(days=day_offset)).isoformat()
        for t in teachers_db:
            st = random.choice(["Present", "Present", "Present", "Present", "Late", "Leave"])
            db.execute(
                "INSERT OR IGNORE INTO teacher_attendance(teacher_id,attend_date,status,note) VALUES(?,?,?,?)",
                (t["id"], d, st, "")
            )

    # --- Fee Payments (current + previous month) ---
    fee_types = ["Tuition Fee", "Transport Fee", "Annual Charges", "Computer Lab", "Library Fee", "Exam Fee"]
    modes = ["Cash", "UPI", "Bank Transfer", "Cheque"]
    receipt_counter = 1001

    # Current month payments
    for s in students[:22]:  # most students have paid something
        amount = random.choice([2500, 3000, 3500, 4000, 4500, 5000, 5500])
        ftype = random.choice(fee_types)
        mode = random.choice(modes)
        day = random.randint(1, min(today.day, 12))
        paid = today.replace(day=day).isoformat()
        receipt = f"RCT-2026-{receipt_counter:04d}"
        receipt_counter += 1
        db.execute(
            """INSERT INTO fee_payments(student_id,paid_date,amount,fee_type,payment_mode,receipt_no,note,created_by)
               VALUES(?,?,?,?,?,?,?,?)""",
            (s["id"], paid, amount, ftype, mode, receipt, "Demo payment", 1)
        )

    # Previous month payments
    prev_month = (today.replace(day=1) - timedelta(days=1))
    for s in students[5:25]:
        amount = random.choice([2500, 3000, 3500, 4000, 5000])
        ftype = random.choice(fee_types)
        mode = random.choice(modes)
        day = random.randint(1, 28)
        paid = prev_month.replace(day=day).isoformat()
        receipt = f"RCT-2026-{receipt_counter:04d}"
        receipt_counter += 1
        db.execute(
            """INSERT INTO fee_payments(student_id,paid_date,amount,fee_type,payment_mode,receipt_no,note,created_by)
               VALUES(?,?,?,?,?,?,?,?)""",
            (s["id"], paid, amount, ftype, mode, receipt, "Previous month", 1)
        )

    # --- Expenses ---
    expenses = [
        (today.isoformat(), "Salaries", "Teaching staff salary - October advance", 185000, "Bank Transfer", "VCH-2026-001"),
        ((today - timedelta(days=2)).isoformat(), "Utilities", "Electricity bill - September", 28500, "UPI", "VCH-2026-002"),
        ((today - timedelta(days=3)).isoformat(), "Maintenance", "Classroom furniture repair", 12500, "Cash", "VCH-2026-003"),
        ((today - timedelta(days=5)).isoformat(), "Stationery", "Notebooks and exam answer sheets", 18700, "Bank Transfer", "VCH-2026-004"),
        ((today - timedelta(days=7)).isoformat(), "Transport", "School bus diesel & maintenance", 42000, "Bank Transfer", "VCH-2026-005"),
        ((today - timedelta(days=10)).isoformat(), "Lab Equipment", "Science lab chemicals & glassware", 15600, "UPI", "VCH-2026-006"),
        ((today - timedelta(days=12)).isoformat(), "Events", "Independence Day celebration expenses", 8900, "Cash", "VCH-2026-007"),
        ((today - timedelta(days=15)).isoformat(), "IT", "Internet & software subscription", 9500, "UPI", "VCH-2026-008"),
        ((prev_month.replace(day=20)).isoformat(), "Salaries", "Teaching staff salary - September", 182000, "Bank Transfer", "VCH-2026-009"),
        ((prev_month.replace(day=15)).isoformat(), "Utilities", "Water & electricity - August", 31200, "Bank Transfer", "VCH-2026-010"),
    ]
    for edate, cat, desc, amt, mode, vno in expenses:
        db.execute(
            """INSERT INTO expenses(expense_date,category,description,amount,payment_mode,voucher_no,created_by)
               VALUES(?,?,?,?,?,?,?)""",
            (edate, cat, desc, amt, mode, vno, 1)
        )

    # --- Exams ---
    exams = [
        ("Half Yearly Examination", "10", (today - timedelta(days=20)).isoformat(), 100, "2026-27", "Mid-term for Class 10"),
        ("Half Yearly Examination", "9", (today - timedelta(days=21)).isoformat(), 100, "2026-27", "Mid-term for Class 9"),
        ("Half Yearly Examination", "8", (today - timedelta(days=22)).isoformat(), 100, "2026-27", "Mid-term for Class 8"),
        ("Unit Test 2", "7", (today - timedelta(days=8)).isoformat(), 40, "2026-27", "Science & Maths unit test"),
        ("Unit Test 2", "6", (today - timedelta(days=9)).isoformat(), 40, "2026-27", "English & Hindi unit test"),
        ("First Term Assessment", "5", (today - timedelta(days=15)).isoformat(), 50, "2026-27", "Class 5 term assessment"),
        ("Monthly Test", "4", (today - timedelta(days=5)).isoformat(), 25, "2026-27", "Class 4 monthly test"),
        ("Monthly Test", "3", (today - timedelta(days=6)).isoformat(), 25, "2026-27", "Class 3 monthly test"),
    ]
    exam_ids = []
    for name, cls, edate, mx, year, notes in exams:
        cur = db.execute(
            "INSERT INTO exams(name,class_name,exam_date,max_marks,academic_year,notes) VALUES(?,?,?,?,?,?)",
            (name, cls, edate, mx, year, notes)
        )
        exam_ids.append(cur.lastrowid)

    # --- Results (for a few exams) ---
    subjects_by_class = {
        "10": ["English", "Mathematics", "Science", "Social Studies", "Hindi"],
        "9": ["English", "Mathematics", "Science", "Social Studies", "Hindi"],
        "8": ["English", "Mathematics", "Science", "Social Studies", "Hindi"],
        "7": ["Science", "Mathematics"],
        "6": ["English", "Hindi"],
        "5": ["English", "Mathematics", "EVS"],
        "4": ["English", "Mathematics"],
        "3": ["English", "Mathematics"],
    }

    for exam_id in exam_ids:
        exam = db.execute("SELECT * FROM exams WHERE id=?", (exam_id,)).fetchone()
        cls = exam["class_name"]
        max_m = exam["max_marks"]
        subjects = subjects_by_class.get(cls, ["English", "Mathematics"])
        class_students = db.execute(
            "SELECT id FROM students WHERE class_name=? AND status='Active'", (cls,)
        ).fetchall()
        for s in class_students:
            for subj in subjects:
                # Realistic mark distribution
                base = max_m * 0.55
                marks = round(base + random.randrange(0, max(1, int(max_m * 0.4))), 1)
                marks = min(marks, max_m)
                remarks = ""
                if marks >= max_m * 0.9:
                    remarks = "Excellent"
                elif marks >= max_m * 0.75:
                    remarks = "Very Good"
                elif marks < max_m * 0.4:
                    remarks = "Needs Improvement"
                db.execute(
                    """INSERT OR IGNORE INTO results(exam_id,student_id,subject,marks,max_marks,remarks)
                       VALUES(?,?,?,?,?,?)""",
                    (exam_id, s["id"], subj, marks, max_m, remarks)
                )

    # --- Audit log samples ---
    audit_entries = [
        (now, "admin", "LOGIN", "user", "1", "Successful login"),
        (now, "admin", "CREATE", "student", "1", "ADM-2026-001"),
        (now, "admin", "CREATE", "teacher", "1", "EMP-001"),
        (now, "accountant", "CREATE", "fee_payment", "1", "RCT-2026-1001"),
        (now, "admin", "UPSERT", "attendance", today.isoformat(), "Bulk attendance saved"),
        (now, "teacher1", "UPSERT", "result", "1:1", "English"),
    ]
    for at, user, action, entity, eid, details in audit_entries:
        db.execute(
            "INSERT INTO audit_log(at,username,action,entity,entity_id,details) VALUES(?,?,?,?,?,?)",
            (at, user, action, entity, eid, details)
        )

    db.commit()
    db.close()

    print("=" * 60)
    print("DEMO DATABASE READY")
    print("=" * 60)
    print(f"Database : {DB_PATH}")
    print()
    print("Login credentials (for customer demo):")
    print("  Principal / Admin :  admin       /  ChangeMe123!")
    print("  Accountant        :  accountant  /  Accountant@1")
    print("  Teacher           :  teacher1    /  Teacher@123")
    print("  Teacher (Maths)   :  teacher2    /  Teacher@123")
    print()
    print("School   : Green Valley Public School")
    print("Year     : 2026-27")
    print("Students : 32  |  Teachers : 8")
    print("Fees, expenses, attendance, exams & results are pre-loaded.")
    print("=" * 60)

if __name__ == "__main__":
    main(force_reset=True)
