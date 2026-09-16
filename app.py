import os
import sqlite3
import hashlib
import time
from datetime import timedelta
from functools import wraps

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    session,
    flash,
    url_for,
    abort
)
from werkzeug.utils import secure_filename
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import PyPDF2

# ----------------- APP CONFIGURATION -----------------
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5 MB max upload
app.secret_key = os.environ.get("SECRET_KEY", "hireai_secret_123")
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database.db")

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ----------------- DATABASE HELPERS -----------------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode('utf-8')).hexdigest()

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        role TEXT,
        password TEXT
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job TEXT,
        company TEXT
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        job TEXT,
        status TEXT DEFAULT 'Pending',
        match_score REAL DEFAULT 0,
        feedback TEXT DEFAULT ''
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS interviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        app_id INTEGER,
        candidate TEXT,
        job TEXT,
        interview_time TEXT,
        interviewer TEXT,
        feedback TEXT DEFAULT '',
        result TEXT DEFAULT ''
    )""")

    # Safe migrations for existing databases
    for col, definition in [
        ("password", "TEXT DEFAULT ''"),
        ("match_score", "REAL DEFAULT 0"),
        ("feedback", "TEXT DEFAULT ''"),
    ]:
        try:
            cur.execute(f"ALTER TABLE applications ADD COLUMN {col} {definition}")
        except sqlite3.OperationalError:
            pass

    try:
        cur.execute("ALTER TABLE users ADD COLUMN password TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()

init_db()

# ----------------- SESSION & AUTH DECORATORS -----------------
@app.before_request
def check_session_timeout():
    if 'username' in session:
        last_active = session.get('last_active')
        now = time.time()
        timeout_seconds = app.config['PERMANENT_SESSION_LIFETIME'].total_seconds()
        if last_active and (now - last_active > timeout_seconds):
            session.clear()
            flash("⚠️ Session timed out due to inactivity. Please login again.")
            return redirect(url_for('login'))
        session['last_active'] = now

def login_required(allowed_roles=None):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'username' not in session or 'role' not in session:
                flash("🔒 Access restricted. Please log in first.")
                return redirect(url_for('login'))
            if allowed_roles and session.get('role') not in allowed_roles:
                flash("⛔ You do not have permission to access that resource.")
                return redirect(url_for('dashboard', username=session['username'], role=session['role']))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ----------------- AI MATCHING & SKILL GAP -----------------
def calculate_match(resume: str, job_desc: str) -> float:
    if not resume or not job_desc or not resume.strip() or not job_desc.strip():
        return 0.0
    try:
        texts = [resume, job_desc]
        cv = CountVectorizer().fit_transform(texts)
        similarity = cosine_similarity(cv)[0][1]
        return round(float(similarity * 100), 2)
    except Exception:
        return 0.0

def get_skill_gap(resume_text: str, job_title: str) -> str:
    """Keyword-based skill gap detection across major tech domains."""
    skill_keywords = {
        "python": ["python", "flask", "django", "pandas", "numpy"],
        "web": ["html", "css", "javascript", "react", "nodejs"],
        "data": ["sql", "excel", "tableau", "powerbi", "analytics"],
        "ml": ["machine learning", "tensorflow", "sklearn", "ai", "deep learning"],
        "java": ["java", "spring", "maven", "hibernate"],
        "devops": ["docker", "kubernetes", "aws", "ci/cd", "linux"],
    }
    resume_lower = resume_text.lower() if resume_text else ""
    job_lower = job_title.lower() if job_title else ""

    relevant = []
    for category, skills in skill_keywords.items():
        if category in job_lower or any(s in job_lower for s in skills):
            relevant = skills
            break

    if not relevant:
        relevant = ["communication", "teamwork", "problem solving"]

    missing = [s for s in relevant if s not in resume_lower]
    if missing:
        return "Consider adding: " + ", ".join(missing[:3])
    return "Great match! No major skill gaps."

def extract_text_from_pdf(filepath: str) -> str:
    text = ""
    try:
        with open(filepath, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + " "
    except Exception as e:
        app.logger.error(f"Error extracting PDF text: {e}")
    return text.strip()

def get_candidate_latest_resume_text(username: str) -> str:
    folder = app.config['UPLOAD_FOLDER']
    if not os.path.exists(folder):
        return ""
    # Filter files starting with candidate's username prefix or sorted
    user_files = [f for f in os.listdir(folder) if f.startswith(f"{username}_") and f.lower().endswith('.pdf')]
    if not user_files:
        # Fallback to general user uploads if any
        user_files = [f for f in os.listdir(folder) if f.lower().endswith('.pdf')]
    if user_files:
        latest = sorted(user_files)[-1]
        return extract_text_from_pdf(os.path.join(folder, latest))
    return ""

# ----------------- PUBLIC & AUTH ROUTES -----------------
@app.route('/')
def home():
    return render_template("index.html")

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        role = request.form.get('role', '').strip()
        username = request.form.get('username', '').strip()
        raw_password = request.form.get('password', '').strip()

        if not username or not raw_password or not role:
            flash("❌ All fields are required.")
            return render_template("register.html")

        if role not in ['candidate', 'company', 'interviewer']:
            flash("❌ Invalid role selected.")
            return render_template("register.html")

        if len(raw_password) < 4:
            flash("❌ Password must be at least 4 characters long.")
            return render_template("register.html")

        conn = get_db()
        existing = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if existing:
            conn.close()
            flash("❌ Username already taken. Try another.")
            return render_template("register.html")

        hashed_pw = hash_password(raw_password)
        conn.execute("INSERT INTO users (username, role, password) VALUES (?, ?, ?)",
                     (username, role, hashed_pw))
        conn.commit()
        conn.close()
        flash("✅ Registered successfully! Please login.")
        return redirect(url_for('login'))

    return render_template("register.html")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        role = request.form.get('role', '').strip()
        username = request.form.get('username', '').strip()
        raw_password = request.form.get('password', '').strip()

        if not username or not raw_password or not role:
            flash("❌ Please enter username, password, and role.")
            return render_template("login.html")

        hashed_pw = hash_password(raw_password)
        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ? AND role = ? AND password = ?",
            (username, role, hashed_pw)
        ).fetchone()
        conn.close()

        if user:
            session.permanent = True
            session['username'] = username
            session['role'] = role
            session['last_active'] = time.time()
            flash(f"👋 Welcome back, {username}!")
            return redirect(url_for('dashboard', username=username, role=role))
        else:
            flash("❌ Invalid credentials. Please try again!")
            return render_template("login.html")

    return render_template("login.html")

@app.route('/logout')
def logout():
    session.clear()
    flash("✅ Logged out successfully!")
    return redirect(url_for('home'))

# ----------------- DASHBOARD ROUTE -----------------
@app.route('/dashboard/<username>/<role>', methods=['GET', 'POST'])
@login_required()
def dashboard(username, role):
    # Enforce current authenticated user session
    if session.get('username') != username or session.get('role') != role:
        return redirect(url_for('dashboard', username=session['username'], role=session['role']))

    conn = get_db()
    search_query = request.args.get('search', '').strip().lower()

    # --- COMPANY: POST JOB ---
    if role == "company" and request.method == 'POST':
        if request.form.get('action') == 'post_job':
            job_title = request.form.get('job', '').strip()
            if not job_title or len(job_title) < 2:
                flash("❌ Job title cannot be empty.")
            else:
                conn.execute("INSERT INTO jobs (job, company) VALUES (?, ?)", (job_title, username))
                conn.commit()
                flash("✅ Job posted successfully!")

    # --- CANDIDATE: UPLOAD RESUME ---
    resume_text = ""
    if role == "candidate" and request.method == 'POST':
        if request.form.get('action') == 'upload_resume':
            file = request.files.get('resume')
            if not file or file.filename == '':
                flash("❌ No file selected.")
            elif not file.filename.lower().endswith('.pdf'):
                flash("❌ Invalid file type. Only PDF resumes are accepted.")
            else:
                safe_name = secure_filename(file.filename)
                unique_filename = f"{username}_{int(time.time())}_{safe_name}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                file.save(filepath)

                resume_text = extract_text_from_pdf(filepath)
                if not resume_text:
                    flash("⚠️ Uploaded PDF had no readable text. Scanned images may not be readable.")

                # Re-score all existing applications for candidate
                apps = conn.execute(
                    "SELECT id, job FROM applications WHERE username = ?", (username,)
                ).fetchall()
                for a in apps:
                    score = calculate_match(resume_text, a["job"])
                    gap = get_skill_gap(resume_text, a["job"])
                    new_status = "Shortlisted" if score >= 60 else (
                        "Under Screening" if score >= 30 else "Rejected"
                    )
                    conn.execute(
                        "UPDATE applications SET match_score = ?, feedback = ?, status = ? WHERE id = ?",
                        (score, gap, new_status, a["id"])
                    )
                conn.commit()
                flash("✅ Resume uploaded! AI has screened your applications.")

    # --- RETRIEVE JOBS & MATCH SCORES ---
    jobs_data = conn.execute("SELECT job, company FROM jobs").fetchall()

    if role == "candidate" and not resume_text:
        resume_text = get_candidate_latest_resume_text(username)

    matches = []
    for job_row in jobs_data:
        job = job_row["job"]
        company = job_row["company"]

        # Search filter
        if search_query and (search_query not in job.lower()) and (search_query not in company.lower()):
            continue

        score = calculate_match(resume_text, job) if resume_text else 0.0
        matches.append((job, company, score))

    # --- RETRIEVE APPLICATIONS ---
    stats = {}
    if role == "company":
        applications = conn.execute(
            "SELECT id, username, job, status, match_score, feedback FROM applications ORDER BY id DESC"
        ).fetchall()
        # Compute company metrics
        total_jobs = conn.execute("SELECT COUNT(*) FROM jobs WHERE company = ?", (username,)).fetchone()[0]
        total_apps = len(applications)
        shortlisted = sum(1 for a in applications if a['status'] == 'Shortlisted')
        interviews_count = conn.execute("SELECT COUNT(*) FROM interviews").fetchone()[0]
        status_counts = {
            "Pending": sum(1 for a in applications if a['status'] == 'Pending'),
            "Under Screening": sum(1 for a in applications if a['status'] == 'Under Screening'),
            "Shortlisted": shortlisted,
            "Interview Scheduled": sum(1 for a in applications if a['status'] == 'Interview Scheduled'),
            "Selected": sum(1 for a in applications if a['status'] == 'Selected'),
            "Rejected": sum(1 for a in applications if a['status'] == 'Rejected'),
        }
        stats = {
            "total_jobs": total_jobs,
            "total_apps": total_apps,
            "shortlisted": shortlisted,
            "interviews_count": interviews_count,
            "status_counts": status_counts
        }
    else:
        applications = conn.execute(
            "SELECT id, username, job, status, match_score, feedback FROM applications WHERE username = ? ORDER BY id DESC",
            (username,)
        ).fetchall()

    conn.close()
    return render_template(
        "dashboard.html",
        username=username,
        role=role,
        jobs=matches,
        applications=applications,
        search_query=search_query,
        stats=stats
    )

# ----------------- APPLICATION FLOW -----------------
@app.route('/apply/<username>/<path:job>')
@login_required(allowed_roles=['candidate'])
def apply(username, job):
    if session.get('username') != username:
        return redirect(url_for('dashboard', username=session['username'], role=session['role']))

    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM applications WHERE username = ? AND job = ?", (username, job)
    ).fetchone()

    if existing:
        conn.close()
        flash("⚠️ You already applied for this job!")
        return redirect(url_for('dashboard', username=username, role='candidate'))

    # Calculate initial AI score and status if candidate already uploaded a resume
    resume_text = get_candidate_latest_resume_text(username)
    if resume_text:
        score = calculate_match(resume_text, job)
        gap = get_skill_gap(resume_text, job)
        status = "Shortlisted" if score >= 60 else ("Under Screening" if score >= 30 else "Rejected")
    else:
        score = 0.0
        gap = "Upload your resume to receive AI match score and skill-gap feedback."
        status = "Under Screening"

    conn.execute(
        "INSERT INTO applications (username, job, status, match_score, feedback) VALUES (?, ?, ?, ?, ?)",
        (username, job, status, score, gap)
    )
    conn.commit()
    conn.close()

    flash(f"✅ Applied successfully! Application status: {status}")
    return redirect(url_for('dashboard', username=username, role='candidate'))

@app.route('/update_status/<int:app_id>/<new_status>/<company>')
@login_required(allowed_roles=['company'])
def update_status(app_id, new_status, company):
    if session.get('username') != company:
        return redirect(url_for('dashboard', username=session['username'], role=session['role']))

    valid_statuses = ['Shortlisted', 'Rejected', 'Pending', 'Under Screening']
    if new_status not in valid_statuses:
        flash("❌ Invalid status provided.")
        return redirect(url_for('dashboard', username=company, role='company'))

    conn = get_db()
    conn.execute("UPDATE applications SET status = ? WHERE id = ?", (new_status, app_id))
    conn.commit()
    conn.close()
    flash(f"✅ Status updated to {new_status}!")
    return redirect(url_for('dashboard', username=company, role='company'))

# ----------------- INTERVIEW ROUTES -----------------
@app.route('/interviews/<username>/<role>', methods=['GET', 'POST'])
@login_required(allowed_roles=['company', 'interviewer'])
def interviews(username, role):
    if session.get('username') != username or session.get('role') != role:
        return redirect(url_for('interviews', username=session['username'], role=session['role']))

    conn = get_db()
    shortlisted = []
    interviewers = []
    interviews_list = []

    if role == 'company':
        # Applications shortlisted and not yet assigned an interview
        shortlisted = conn.execute("""
            SELECT a.id, a.username, a.job
            FROM applications a
            WHERE a.status = 'Shortlisted'
            AND a.id NOT IN (SELECT app_id FROM interviews WHERE app_id IS NOT NULL)
        """).fetchall()

        interviewers_rows = conn.execute(
            "SELECT username FROM users WHERE role = 'interviewer'"
        ).fetchall()
        interviewers = [i["username"] for i in interviewers_rows]

        # Scheduled interviews for company overview
        interviews_list = conn.execute("""
            SELECT id, candidate, job, interview_time, interviewer, feedback, result
            FROM interviews ORDER BY id DESC
        """).fetchall()

    elif role == 'interviewer':
        interviews_list = conn.execute("""
            SELECT id, candidate, job, interview_time, feedback, result
            FROM interviews WHERE interviewer = ? ORDER BY id DESC
        """, (username,)).fetchall()

    conn.close()
    return render_template(
        "interview.html",
        username=username,
        role=role,
        shortlisted=shortlisted,
        interviewers=interviewers,
        interviews=interviews_list
    )

@app.route('/schedule_interview/<int:app_id>', methods=['POST'])
@login_required(allowed_roles=['company'])
def schedule_interview(app_id):
    interview_time = request.form.get('interview_time', '').strip()
    interviewer = request.form.get('interviewer', '').strip()

    if not interview_time or not interviewer:
        flash("❌ Interview time and interviewer are required.")
        company = session.get('username', '')
        return redirect(url_for('interviews', username=company, role='company'))

    conn = get_db()
    app_row = conn.execute(
        "SELECT username, job FROM applications WHERE id = ?", (app_id,)
    ).fetchone()

    if app_row:
        conn.execute("""
            INSERT INTO interviews (app_id, candidate, job, interview_time, interviewer)
            VALUES (?, ?, ?, ?, ?)
        """, (app_id, app_row["username"], app_row["job"], interview_time, interviewer))

        conn.execute(
            "UPDATE applications SET status = 'Interview Scheduled' WHERE id = ?",
            (app_id,)
        )
        conn.commit()
        flash(f"✅ Interview scheduled with {interviewer}!")

    conn.close()
    company = session.get('username', '')
    return redirect(url_for('interviews', username=company, role='company'))

@app.route('/submit_feedback/<int:interview_id>', methods=['POST'])
@login_required(allowed_roles=['interviewer'])
def submit_feedback(interview_id):
    result = request.form.get('result', '').strip()
    feedback = request.form.get('feedback', '').strip()

    # Empty feedback validation (Fixes test case RS_24 from academic report)
    if not feedback:
        flash("❌ Feedback cannot be empty. Please provide evaluation notes.")
        interviewer = session.get('username', '')
        return redirect(url_for('interviews', username=interviewer, role='interviewer'))

    if result not in ['Selected', 'Rejected']:
        flash("❌ Invalid interview result.")
        interviewer = session.get('username', '')
        return redirect(url_for('interviews', username=interviewer, role='interviewer'))

    conn = get_db()
    interview = conn.execute(
        "SELECT app_id, candidate, job FROM interviews WHERE id = ?", (interview_id,)
    ).fetchone()

    if interview:
        conn.execute(
            "UPDATE interviews SET feedback = ?, result = ? WHERE id = ?",
            (feedback, result, interview_id)
        )
        if interview["app_id"]:
            conn.execute(
                "UPDATE applications SET status = ?, feedback = ? WHERE id = ?",
                (result, feedback, interview["app_id"])
            )
        conn.commit()
        flash(f"✅ Feedback submitted! Candidate marked as {result}.")

    conn.close()
    interviewer = session.get('username', '')
    return redirect(url_for('interviews', username=interviewer, role='interviewer'))

# ----------------- ENTRY POINT -----------------
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5001))
    app.run(debug=True, host='0.0.0.0', port=port)
