import os, sqlite3, hashlib, secrets, hmac
from datetime import date, datetime
from functools import wraps
from flask import Flask, g, request, redirect, url_for, render_template, session, flash, abort

APP_DIR = os.path.dirname(os.path.abspath(__file__))
# On Vercel the filesystem is read-only except /tmp (ephemeral).
# Locally we keep the DB next to the app.
if os.environ.get("VERCEL"):
    DB_PATH = os.environ.get("SCHOOL_ERP_DB", "/tmp/school_erp.db")
else:
    DB_PATH = os.environ.get("SCHOOL_ERP_DB", os.path.join(APP_DIR, "school_erp.db"))

# Use a fixed secret in production so sessions survive cold starts.
# Set SCHOOL_ERP_SECRET in Vercel project settings for a real secret.
SECRET_KEY = os.environ.get(
    "SCHOOL_ERP_SECRET",
    "demo-secret-change-me-in-vercel-dashboard-green-valley-2026"
)
app = Flask(
    __name__,
    template_folder=os.path.join(APP_DIR, "templates"),
    static_folder=os.path.join(APP_DIR, "static"),
)
app.secret_key = SECRET_KEY
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=bool(os.environ.get("VERCEL")),
)

ROLES = {
    "admin": {"dashboard","students","parents","teachers","attendance","teacher_attendance","fees","expenses","exams","results","reports","audit"},
    "accountant": {"dashboard","students","parents","fees","expenses","reports"},
    "teacher": {"dashboard","students","attendance","teacher_attendance","exams","results"},
    "parent": {"dashboard","parent_portal"}
}

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

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db

@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def pw_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260000).hex()
    return f"{salt}${digest}"

def verify_pw(password, stored):
    try:
        salt, expected = stored.split("$", 1)
        return hmac.compare_digest(pw_hash(password, salt).split("$",1)[1], expected)
    except Exception:
        return False

def audit(action, entity, entity_id="", details=""):
    user = session.get("username", "system")
    get_db().execute("INSERT INTO audit_log(at,username,action,entity,entity_id,details) VALUES(?,?,?,?,?,?)",
                     (datetime.now().isoformat(timespec="seconds"), user, action, entity, str(entity_id), str(details)[:500]))
    get_db().commit()

def init_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    db.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('school_name','Green Valley Public School')")
    db.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('academic_year','2026-27')")
    db.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('subscription_mode','demo')")
    if not db.execute("SELECT id FROM users LIMIT 1").fetchone():
        db.execute("INSERT INTO users(username,password_hash,role,display_name) VALUES(?,?,?,?)",
                   ("admin", pw_hash("ChangeMe123!"), "admin", "Rajesh Sharma (Principal)"))
        db.execute("INSERT INTO users(username,password_hash,role,display_name) VALUES(?,?,?,?)",
                   ("accountant", pw_hash("Accountant@1"), "accountant", "Priya Mehta (Accountant)"))
        db.execute("INSERT INTO users(username,password_hash,role,display_name) VALUES(?,?,?,?)",
                   ("teacher1", pw_hash("Teacher@123"), "teacher", "Anita Desai (Class Teacher)"))
    db.commit()
    db.close()

def _maybe_seed_demo():
    """Load demo dataset once when the DB has no students."""
    marker = "/tmp/school_erp_seeded.flag" if os.environ.get("VERCEL") else None
    try:
        if marker and os.path.exists(marker):
            return
        db = sqlite3.connect(DB_PATH)
        count = db.execute("SELECT COUNT(*) FROM students").fetchone()[0]
        db.close()
        if count > 0:
            if marker:
                open(marker, "w").close()
            return
        os.environ["SCHOOL_ERP_DB"] = DB_PATH
        from seed_demo import main as seed_main
        seed_main()
        if marker:
            open(marker, "w").close()
    except Exception as e:
        print("Demo seed skipped:", repr(e))

@app.before_request
def ensure_db():
    try:
        init_db()
        _maybe_seed_demo()
    except Exception as e:
        # Never block the whole request on DB init failure
        print("ensure_db error:", repr(e))

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login", next=request.path))
        return fn(*args, **kwargs)
    return wrapper

def require(*permissions):
    def decorator(fn):
        @wraps(fn)
        @login_required
        def wrapper(*args, **kwargs):
            if session.get("role") not in ROLES or not set(permissions).issubset(ROLES[session["role"]]):
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator

@app.context_processor
def inject_globals():
    db = get_db()
    settings = {r["key"]: r["value"] for r in db.execute("SELECT key,value FROM settings")}
    return {"current_user": session.get("display_name"), "current_role": session.get("role"),
            "school_name": settings.get("school_name", "School ERP"), "today": date.today().isoformat()}

@app.route("/")
def index():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username","").strip()
        password = request.form.get("password","")
        row = get_db().execute("SELECT * FROM users WHERE username=? AND active=1", (username,)).fetchone()
        if row and verify_pw(password, row["password_hash"]):
            session.clear()
            session.update(user_id=row["id"], username=row["username"], role=row["role"], display_name=row["display_name"])
            audit("LOGIN", "user", row["id"], "Successful login")
            return redirect(request.args.get("next") or url_for("dashboard"))
        flash("Invalid username or password.", "error")
    return render_template("login.html")

@app.route("/logout", methods=["POST"])
@login_required
def logout():
    audit("LOGOUT", "user", session.get("user_id"), "User logged out")
    session.clear()
    return redirect(url_for("login"))

@app.route("/dashboard")
@require("dashboard")
def dashboard():
    db = get_db()
    stats = {
        "students": db.execute("SELECT COUNT(*) FROM students WHERE status='Active'").fetchone()[0],
        "teachers": db.execute("SELECT COUNT(*) FROM teachers WHERE status='Active'").fetchone()[0],
        "fees": db.execute("SELECT COALESCE(SUM(amount),0) FROM fee_payments WHERE substr(paid_date,1,7)=?", (date.today().strftime("%Y-%m"),)).fetchone()[0],
        "expenses": db.execute("SELECT COALESCE(SUM(amount),0) FROM expenses WHERE substr(expense_date,1,7)=?", (date.today().strftime("%Y-%m"),)).fetchone()[0],
        "absent": db.execute("SELECT COUNT(*) FROM attendance WHERE attend_date=? AND status='Absent'", (date.today().isoformat(),)).fetchone()[0],
    }
    recent = db.execute("""SELECT f.receipt_no, f.paid_date, f.amount, s.first_name||' '||s.last_name AS student
        FROM fee_payments f JOIN students s ON s.id=f.student_id ORDER BY f.id DESC LIMIT 5""").fetchall()
    return render_template("dashboard.html", stats=stats, recent=recent)

@app.route("/students", methods=["GET","POST"])
@require("students")
def students():
    db = get_db()
    if request.method == "POST":
        try:
            db.execute("""INSERT INTO students(admission_no,first_name,last_name,class_name,section,dob,gender,parent_name,parent_phone,parent_email,address,admission_date,status,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                request.form["admission_no"].strip(), request.form["first_name"].strip(), request.form.get("last_name","").strip(),
                request.form["class_name"].strip(), request.form.get("section","").strip(), request.form.get("dob",""),
                request.form.get("gender",""), request.form.get("parent_name","").strip(), request.form.get("parent_phone","").strip(),
                request.form.get("parent_email","").strip(), request.form.get("address","").strip(), request.form.get("admission_date",date.today().isoformat()),
                request.form.get("status","Active"), datetime.now().isoformat(timespec="seconds")))
            db.commit()
            new_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            audit("CREATE","student",new_id,request.form["admission_no"])
            flash("Student saved.", "success")
        except sqlite3.IntegrityError:
            flash("Admission number already exists or a required value is missing.", "error")
        return redirect(url_for("students"))
    q = request.args.get("q","").strip()
    rows = db.execute("""SELECT * FROM students WHERE admission_no LIKE ? OR first_name LIKE ? OR last_name LIKE ? OR class_name LIKE ?
        ORDER BY class_name,section,first_name LIMIT 500""", tuple([f"%{q}%"]*4)).fetchall()
    return render_template("students.html", rows=rows, q=q)

@app.route("/students/<int:student_id>/status", methods=["POST"])
@require("students")
def student_status(student_id):
    db=get_db()
    status=request.form.get("status","Inactive")
    if status not in ("Active","Inactive","Transferred"): abort(400)
    db.execute("UPDATE students SET status=? WHERE id=?", (status,student_id)); db.commit()
    audit("UPDATE","student",student_id,"status="+status)
    flash("Student status updated.", "success")
    return redirect(url_for("students"))

@app.route("/teachers", methods=["GET","POST"])
@require("teachers")
def teachers():
    db=get_db()
    if request.method=="POST":
        try:
            db.execute("""INSERT INTO teachers(employee_no,name,phone,email,subject,joining_date,salary,status,created_at)
                VALUES(?,?,?,?,?,?,?,?,?)""", (request.form["employee_no"].strip(),request.form["name"].strip(),
                request.form.get("phone","").strip(),request.form.get("email","").strip(),request.form.get("subject","").strip(),
                request.form.get("joining_date",""),float(request.form.get("salary") or 0),request.form.get("status","Active"),
                datetime.now().isoformat(timespec="seconds")))
            db.commit(); new_id=db.execute("SELECT last_insert_rowid()").fetchone()[0]
            audit("CREATE","teacher",new_id,request.form["employee_no"]); flash("Teacher saved.","success")
        except (sqlite3.IntegrityError,ValueError):
            flash("Employee number must be unique and salary must be numeric.","error")
        return redirect(url_for("teachers"))
    rows=db.execute("SELECT * FROM teachers ORDER BY name LIMIT 500").fetchall()
    return render_template("teachers.html",rows=rows)

@app.route("/attendance", methods=["GET","POST"])
@require("attendance")
def attendance():
    db=get_db()
    day=request.values.get("day",date.today().isoformat())
    if request.method=="POST":
        day=request.form.get("attend_date",date.today().isoformat())
        for s in db.execute("SELECT id FROM students WHERE status='Active'").fetchall():
            status=request.form.get(f"student_{s['id']}")
            if status in ("Present","Absent","Late","Leave"):
                db.execute("""INSERT INTO attendance(student_id,attend_date,status,note,marked_by) VALUES(?,?,?,?,?)
                    ON CONFLICT(student_id,attend_date) DO UPDATE SET status=excluded.status,note=excluded.note,marked_by=excluded.marked_by""",
                    (s["id"],day,status,"",session.get("user_id")))
        db.commit(); audit("UPSERT","attendance",day,"Bulk attendance saved"); flash("Attendance saved.","success")
        return redirect(url_for("attendance",day=day))
    rows=db.execute("""SELECT s.*, a.status AS today_status FROM students s LEFT JOIN attendance a ON a.student_id=s.id AND a.attend_date=?
        WHERE s.status='Active' ORDER BY s.class_name,s.section,s.first_name""",(day,)).fetchall()
    return render_template("attendance.html",rows=rows,day=day)

@app.route("/teacher-attendance", methods=["GET","POST"])
@require("teacher_attendance")
def teacher_attendance():
    db=get_db(); day=request.values.get("day",date.today().isoformat())
    if request.method=="POST":
        day=request.form.get("attend_date",date.today().isoformat())
        for t in db.execute("SELECT id FROM teachers WHERE status='Active'").fetchall():
            status=request.form.get(f"teacher_{t['id']}")
            if status in ("Present","Absent","Late","Leave"):
                db.execute("""INSERT INTO teacher_attendance(teacher_id,attend_date,status,note) VALUES(?,?,?,?)
                    ON CONFLICT(teacher_id,attend_date) DO UPDATE SET status=excluded.status,note=excluded.note""",(t["id"],day,status,""))
        db.commit(); audit("UPSERT","teacher_attendance",day,"Bulk teacher attendance saved")
        flash("Teacher attendance saved.","success"); return redirect(url_for("teacher_attendance",day=day))
    rows=db.execute("""SELECT t.*, a.status AS today_status FROM teachers t LEFT JOIN teacher_attendance a
        ON a.teacher_id=t.id AND a.attend_date=? WHERE t.status='Active' ORDER BY t.name""",(day,)).fetchall()
    return render_template("teacher_attendance.html",rows=rows,day=day)

@app.route("/fees", methods=["GET","POST"])
@require("fees")
def fees():
    db=get_db()
    if request.method=="POST":
        try:
            receipt=request.form.get("receipt_no","").strip() or "RCT-"+secrets.token_hex(4).upper()
            db.execute("""INSERT INTO fee_payments(student_id,paid_date,amount,fee_type,payment_mode,receipt_no,note,created_by)
                VALUES(?,?,?,?,?,?,?,?)""",(int(request.form["student_id"]),request.form.get("paid_date",date.today().isoformat()),
                float(request.form["amount"]),request.form["fee_type"].strip(),request.form.get("payment_mode","Cash"),receipt,
                request.form.get("note","").strip(),session.get("user_id")))
            db.commit(); new_id=db.execute("SELECT last_insert_rowid()").fetchone()[0]
            audit("CREATE","fee_payment",new_id,receipt); flash(f"Payment recorded. Receipt: {receipt}","success")
        except (ValueError,sqlite3.IntegrityError,KeyError):
            flash("Could not save payment. Check the student, amount, and receipt number.","error")
        return redirect(url_for("fees"))
    students=db.execute("SELECT id,admission_no,first_name,last_name,class_name FROM students WHERE status='Active' ORDER BY class_name,first_name").fetchall()
    rows=db.execute("""SELECT f.*,s.first_name||' '||s.last_name AS student,s.admission_no FROM fee_payments f
        JOIN students s ON s.id=f.student_id ORDER BY f.id DESC LIMIT 300""").fetchall()
    total=db.execute("SELECT COALESCE(SUM(amount),0) FROM fee_payments").fetchone()[0]
    return render_template("fees.html",students=students,rows=rows,total=total)

@app.route("/expenses", methods=["GET","POST"])
@require("expenses")
def expenses():
    db=get_db()
    if request.method=="POST":
        try:
            voucher=request.form.get("voucher_no","").strip() or "VCH-"+secrets.token_hex(4).upper()
            db.execute("""INSERT INTO expenses(expense_date,category,description,amount,payment_mode,voucher_no,created_by)
                VALUES(?,?,?,?,?,?,?)""",(request.form.get("expense_date",date.today().isoformat()),request.form["category"].strip(),
                request.form["description"].strip(),float(request.form["amount"]),request.form.get("payment_mode","Cash"),voucher,session.get("user_id")))
            db.commit(); new_id=db.execute("SELECT last_insert_rowid()").fetchone()[0]
            audit("CREATE","expense",new_id,voucher); flash("Expense recorded.","success")
        except (ValueError,sqlite3.IntegrityError,KeyError):
            flash("Could not save expense. Check amount and voucher number.","error")
        return redirect(url_for("expenses"))
    rows=db.execute("SELECT * FROM expenses ORDER BY id DESC LIMIT 300").fetchall()
    total=db.execute("SELECT COALESCE(SUM(amount),0) FROM expenses").fetchone()[0]
    return render_template("expenses.html",rows=rows,total=total)

@app.route("/exams", methods=["GET","POST"])
@require("exams")
def exams():
    db=get_db()
    if request.method=="POST":
        try:
            db.execute("INSERT INTO exams(name,class_name,exam_date,max_marks,academic_year,notes) VALUES(?,?,?,?,?,?)",
                (request.form["name"].strip(),request.form["class_name"].strip(),request.form["exam_date"],
                 float(request.form.get("max_marks") or 100),request.form.get("academic_year",""),request.form.get("notes","")))
            db.commit(); new_id=db.execute("SELECT last_insert_rowid()").fetchone()[0]
            audit("CREATE","exam",new_id,request.form["name"]); flash("Exam scheduled.","success")
        except (ValueError,sqlite3.IntegrityError):
            flash("Could not save exam. Check the date and maximum marks.","error")
        return redirect(url_for("exams"))
    rows=db.execute("SELECT * FROM exams ORDER BY exam_date DESC,id DESC LIMIT 300").fetchall()
    return render_template("exams.html",rows=rows)

@app.route("/results", methods=["GET","POST"])
@require("results")
def results():
    db=get_db()
    if request.method=="POST":
        try:
            exam_id=int(request.form["exam_id"]); student_id=int(request.form["student_id"])
            marks=float(request.form["marks"]); maximum=float(request.form["max_marks"])
            if marks < 0 or maximum <= 0 or marks > maximum: raise ValueError()
            db.execute("""INSERT INTO results(exam_id,student_id,subject,marks,max_marks,remarks) VALUES(?,?,?,?,?,?)
                ON CONFLICT(exam_id,student_id,subject) DO UPDATE SET marks=excluded.marks,max_marks=excluded.max_marks,remarks=excluded.remarks""",
                (exam_id,student_id,request.form["subject"].strip(),marks,maximum,request.form.get("remarks","").strip()))
            db.commit(); audit("UPSERT","result",f"{exam_id}:{student_id}",request.form["subject"]); flash("Result saved.","success")
        except (ValueError,sqlite3.IntegrityError,KeyError):
            flash("Could not save result. Marks must be between zero and maximum marks.","error")
        return redirect(url_for("results"))
    exams=db.execute("SELECT * FROM exams ORDER BY exam_date DESC").fetchall()
    students=db.execute("SELECT id,admission_no,first_name,last_name,class_name FROM students WHERE status='Active' ORDER BY class_name,first_name").fetchall()
    rows=db.execute("""SELECT r.*,e.name AS exam_name,s.first_name||' '||s.last_name AS student,s.admission_no
        FROM results r JOIN exams e ON e.id=r.exam_id JOIN students s ON s.id=r.student_id ORDER BY r.id DESC LIMIT 300""").fetchall()
    return render_template("results.html",exams=exams,students=students,rows=rows)

@app.route("/reports")
@require("reports")
def reports():
    db=get_db()
    month=request.args.get("month",date.today().strftime("%Y-%m"))
    income=db.execute("SELECT COALESCE(SUM(amount),0) FROM fee_payments WHERE substr(paid_date,1,7)=?",(month,)).fetchone()[0]
    expense=db.execute("SELECT COALESCE(SUM(amount),0) FROM expenses WHERE substr(expense_date,1,7)=?",(month,)).fetchone()[0]
    attendance=db.execute("""SELECT status,COUNT(*) AS n FROM attendance WHERE substr(attend_date,1,7)=? GROUP BY status""",(month,)).fetchall()
    byclass=db.execute("""SELECT class_name,COUNT(*) AS n FROM students WHERE status='Active' GROUP BY class_name ORDER BY class_name""").fetchall()
    return render_template("reports.html",month=month,income=income,expense=expense,net=income-expense,attendance=attendance,byclass=byclass)

@app.route("/audit")
@require("audit")
def audit_page():
    rows=get_db().execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT 300").fetchall()
    return render_template("audit.html",rows=rows)

@app.route("/settings", methods=["GET","POST"])
@require("dashboard")
def settings():
    db=get_db()
    if session.get("role") != "admin": abort(403)
    if request.method=="POST":
        for key in ("school_name","academic_year"):
            db.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(key,request.form.get(key,"").strip()))
        db.commit(); audit("UPDATE","settings","","School settings updated"); flash("Settings saved.","success")
        return redirect(url_for("settings"))
    values={r["key"]:r["value"] for r in db.execute("SELECT key,value FROM settings")}
    return render_template("settings.html",values=values)

@app.route("/change-password", methods=["GET","POST"])
@login_required
def change_password():
    if request.method=="POST":
        old=request.form.get("old_password",""); new=request.form.get("new_password","")
        row=get_db().execute("SELECT password_hash FROM users WHERE id=?",(session["user_id"],)).fetchone()
        if not row or not verify_pw(old,row["password_hash"]):
            flash("Current password is incorrect.","error")
        elif len(new)<12:
            flash("Use a new password with at least 12 characters.","error")
        else:
            get_db().execute("UPDATE users SET password_hash=? WHERE id=?",(pw_hash(new),session["user_id"])); get_db().commit()
            audit("UPDATE","user",session["user_id"],"Password changed"); flash("Password changed.","success")
            return redirect(url_for("dashboard"))
    return render_template("change_password.html")

@app.errorhandler(403)
def forbidden(e):
    return render_template("error.html", code=403, message="You do not have permission to access this section."), 403
@app.errorhandler(404)
def missing(e):
    return render_template("error.html", code=404, message="The requested page was not found."), 404

if __name__ == "__main__":
    init_db()
    # Local prototype only. Use a production WSGI server and HTTPS for deployment.
    app.run(host=os.environ.get("SCHOOL_ERP_HOST","127.0.0.1"), port=int(os.environ.get("PORT","5000")), debug=False)
