# AI-based Recruitment System (HireAI) 

An intelligent, web-based recruitment and applicant tracking platform powered by **Python (Flask)**, **SQLite**, and **Machine Learning / NLP (scikit-learn)**.
The system automates candidate resume screening, computes objective match scores using vectorization and cosine similarity, identifies domain-specific skill gaps, and manages the end-to-end recruitment lifecycle across three distinct roles: **Candidate**, **Company (Recruiter)**, and **Interviewer**.


## Key Features

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

## Tech Stack

- **Backend**: Python 3.10+, Flask 3.x, Gunicorn
- **Machine Learning / NLP**: scikit-learn (CountVectorizer, cosine_similarity), NumPy
- **PDF Processing**: PyPDF2
- **Database**: SQLite3 (`database.db`)
- **Frontend**: HTML5, Jinja2 Templates, Vanilla JavaScript, Chart.js
- **Styling**: Modern Glassmorphic CSS Design System (`static/style.css`)


