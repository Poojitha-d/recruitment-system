# AI-based Recruitment System (HireAI) 🚀

An intelligent, web-based recruitment and applicant tracking platform powered by **Python (Flask)**, **SQLite**, and **Machine Learning / NLP (scikit-learn)**.

The system automates candidate resume screening, computes objective match scores using vectorization and cosine similarity, identifies domain-specific skill gaps, and manages the end-to-end recruitment lifecycle across three distinct roles: **Candidate**, **Company (Recruiter)**, and **Interviewer**.

---

## 🌟 Key Features

### 1. Role-Based Authentication & Access Control
- **Candidates**: Upload PDF resumes, explore active job listings with live match scores, apply to jobs, track application status, and view skill gap feedback.
- **Companies**: Publish job openings, view all applicants, analyze pipeline distribution charts, override candidate statuses (Shortlist, Reject, Pending), and assign interviewers.
- **Interviewers**: View scheduled interviews, assess candidates, and submit structured feedback with mandatory validation notes.
- **Security**: SHA-256 password hashing, role verification decorators, and session idle timeout (30-minute expiry).

### 2. AI-Driven Resume Screening & Match Scoring
- Extracts textual content from uploaded PDF resumes using `PyPDF2`.
- Vectorizes resume and job descriptions using `scikit-learn`'s `CountVectorizer`.
- Computes mathematical similarity using `cosine_similarity`, yielding an objective **0–100% Match Score**.
- **Automated Screening Thresholds**:
  - **Shortlisted**: Score $\ge$ 60%
  - **Under Screening**: 30% $\le$ Score < 60%
  - **Rejected**: Score < 30%

### 3. Skill Gap Detection
- Analyzes candidate resumes against curated tech domain skill sets (Python, Web Development, Data Science, Machine Learning, Java, DevOps).
- Highlights missing keywords to guide candidate profile improvement (e.g., *"Consider adding: pandas, numpy, flask"*).

### 4. Interactive Recruiter Dashboard
- **Metric Cards**: Total Jobs, Total Applicants, Shortlisted Candidates, and Scheduled Interviews.
- **Pipeline Breakdown Chart**: Real-time interactive Chart.js doughnut chart showing candidate distribution across all recruitment stages.

### 5. Interview Management
- Recruiters can schedule interviews for shortlisted candidates by choosing an assigned interviewer and datetime.
- Interviewers review candidates and submit final decisions (`Selected` or `Rejected`) with mandatory evaluation notes.
- Input validation prevents submitting empty or whitespace feedback (resolves test case `RS_24`).

---

## 🏗️ Tech Stack

- **Backend**: Python 3.10+, Flask 3.x, Gunicorn
- **Machine Learning / NLP**: scikit-learn (CountVectorizer, cosine_similarity), NumPy
- **PDF Processing**: PyPDF2
- **Database**: SQLite3 (`database.db`)
- **Frontend**: HTML5, Jinja2 Templates, Vanilla JavaScript, Chart.js
- **Styling**: Modern Glassmorphic CSS Design System (`static/style.css`)

---

## 📁 Project Structure

```
recruitment-system/
├── app.py                 # Core Flask application with AI matching & routes
├── requirements.txt       # Production & development Python dependencies
├── Procfile               # Web server process entrypoint (Gunicorn)
├── .env.example           # Template for environment variables
├── .gitignore             # Excludes databases, uploaded files, and venv
├── test_app.py            # Automated test suite covering RS_1 to RS_27
├── templates/             # Jinja2 HTML templates
│   ├── index.html         # Landing / Hero page
│   ├── login.html         # User login with role selector
│   ├── register.html      # User registration
│   ├── dashboard.html     # Role-based dashboard with analytics
│   └── interview.html     # Interview scheduling & feedback portal
├── static/
│   └── style.css          # Custom glassmorphic CSS styling
└── uploads/               # Destination folder for uploaded candidate resumes
```

---

## 🚀 Quickstart & Local Setup

### 1. Prerequisites
- Python 3.8 or higher installed on your system.
- Git installed.

### 2. Clone the Repository
```bash
git clone https://github.com/Poojitha-d/recruitment-system.git
cd recruitment-system
```

### 3. Create & Activate Virtual Environment
```bash
# Windows
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

### 5. Run the Application
```bash
python app.py
```
Open your browser and navigate to: `http://localhost:5001`

---

## 🧪 Running the Test Suite

The project includes an automated test suite based on Python's `unittest` module covering all test cases specified in the academic project report (`RS_1` through `RS_27`):

```bash
python -m unittest test_app.py -v
```

### Test Coverage Highlights:
- **RS_1 – RS_7 (Authentication)**: Valid registration, duplicate rejection, login validation, session persistence, unauthorized route protection (`RS_6`), and session timeout (`RS_7`).
- **RS_8 – RS_11 (Job Management)**: Job posting, empty job title rejection (`RS_9`), job browsing, and keyword search filtering.
- **RS_12 – RS_15 (Applications)**: Application submission, duplicate application block (`RS_13`), candidate application list, and company applicant tracking.
- **RS_16 – RS_20 (AI Features)**: PDF upload, non-PDF rejection (`RS_17`), CountVectorizer + cosine similarity match calculation (`RS_18`), skill-gap keyword analysis (`RS_19`), and automatic status thresholds (`RS_20`).
- **RS_21 – RS_24 (Interviews)**: Interview scheduling, queue retrieval, feedback submission, and empty feedback rejection (`RS_24`).
- **RS_25 – RS_27 (Database & Security)**: Data persistence, SHA-256 password hashing (`RS_26`), and session state retention.

---

## ☁️ Deployment Guide

### Deploying to Render.com (Recommended)
1. Push your repository to GitHub.
2. Sign in to [Render](https://render.com/) and click **New +** > **Web Service**.
3. Connect your `recruitment-system` repository.
4. Configure the service settings:
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
5. Under **Environment Variables**, add:
   - `SECRET_KEY`: (Generate a secure random string)
   - `PYTHON_VERSION`: `3.10.11`
6. Click **Create Web Service**. Render will build and deploy the application with a public `https://*.onrender.com` URL.

---

## 🔒 Environment Variables

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | `hireai_secret_123` | Flask session cryptographic signing key |
| `PORT` | `5001` | Application port |
| `FLASK_ENV` | `production` | Environment mode |
