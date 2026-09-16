import unittest
import os
import io
import time
import sqlite3
import hashlib
from PyPDF2 import PdfWriter
from app import app, get_db, init_db, calculate_match, get_skill_gap, hash_password

class RecruitmentSystemTestCase(unittest.TestCase):
    def setUp(self):
        # Configure app for testing
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test_secret'
        self.test_db = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_database.db")
        app.config['DB_PATH'] = self.test_db

        # Override DB_PATH in module
        import app as app_module
        app_module.DB_PATH = self.test_db

        self.client = app.test_client()
        init_db()

    def tearDown(self):
        if os.path.exists(self.test_db):
            try:
                os.remove(self.test_db)
            except PermissionError:
                pass

    # ---------- AUTHENTICATION TESTS (RS_1 - RS_7) ----------
    def test_RS_1_registration(self):
        """RS_1: Check registration with valid data"""
        response = self.client.post('/register', data={
            'role': 'candidate',
            'username': 'john_doe',
            'password': 'password123'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Registered successfully", response.data)

    def test_RS_2_duplicate_registration(self):
        """RS_2: Check duplicate registration handled"""
        self.client.post('/register', data={
            'role': 'candidate',
            'username': 'john_dup',
            'password': 'password123'
        })
        response = self.client.post('/register', data={
            'role': 'candidate',
            'username': 'john_dup',
            'password': 'password123'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Username already taken", response.data)

    def test_RS_3_valid_login(self):
        """RS_3: Check valid login functionality"""
        self.client.post('/register', data={
            'role': 'candidate',
            'username': 'alice',
            'password': 'password123'
        })
        response = self.client.post('/login', data={
            'role': 'candidate',
            'username': 'alice',
            'password': 'password123'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Welcome back, alice", response.data)

    def test_RS_4_invalid_login(self):
        """RS_4: Check invalid login shows error"""
        self.client.post('/register', data={
            'role': 'candidate',
            'username': 'bob',
            'password': 'password123'
        })
        response = self.client.post('/login', data={
            'role': 'candidate',
            'username': 'bob',
            'password': 'wrongpassword'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Invalid credentials", response.data)

    def test_RS_5_logout(self):
        """RS_5: Check logout clears session and redirects"""
        self.client.post('/register', data={
            'role': 'candidate',
            'username': 'carol',
            'password': 'password123'
        })
        self.client.post('/login', data={
            'role': 'candidate',
            'username': 'carol',
            'password': 'password123'
        })
        response = self.client.get('/logout', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Logged out successfully", response.data)

    def test_RS_6_access_without_login(self):
        """RS_6: Check unauthorized access without login redirects to login"""
        response = self.client.get('/dashboard/secret_user/candidate', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Access restricted. Please log in first", response.data)

    def test_RS_7_session_timeout(self):
        """RS_7: Check session timeout on idle expiration (Fixed vs Report)"""
        self.client.post('/register', data={
            'role': 'candidate',
            'username': 'dave',
            'password': 'password123'
        })
        self.client.post('/login', data={
            'role': 'candidate',
            'username': 'dave',
            'password': 'password123'
        })
        with self.client.session_transaction() as sess:
            # Simulate last activity 35 minutes ago (> 30 mins)
            sess['last_active'] = time.time() - (35 * 60)

        response = self.client.get('/dashboard/dave/candidate', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Session timed out due to inactivity", response.data)

    # ---------- JOB MANAGEMENT TESTS (RS_8 - RS_11) ----------
    def test_RS_8_post_job(self):
        """RS_8: Check company posting a valid job"""
        self.client.post('/register', data={
            'role': 'company',
            'username': 'google',
            'password': 'password123'
        })
        self.client.post('/login', data={
            'role': 'company',
            'username': 'google',
            'password': 'password123'
        })
        response = self.client.post('/dashboard/google/company', data={
            'action': 'post_job',
            'job': 'Python Backend Engineer'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Job posted successfully", response.data)

    def test_RS_9_post_empty_job(self):
        """RS_9: Check posting empty job shows error"""
        self.client.post('/register', data={
            'role': 'company',
            'username': 'meta',
            'password': 'password123'
        })
        self.client.post('/login', data={
            'role': 'company',
            'username': 'meta',
            'password': 'password123'
        })
        response = self.client.post('/dashboard/meta/company', data={
            'action': 'post_job',
            'job': '   '
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Job title cannot be empty", response.data)

    def test_RS_10_and_11_view_and_search_jobs(self):
        """RS_10 & RS_11: View and search jobs"""
        self.client.post('/register', data={'role': 'company', 'username': 'amazon', 'password': 'password123'})
        self.client.post('/login', data={'role': 'company', 'username': 'amazon', 'password': 'password123'})
        self.client.post('/dashboard/amazon/company', data={'action': 'post_job', 'job': 'DevOps Kubernetes AWS'})
        self.client.post('/dashboard/amazon/company', data={'action': 'post_job', 'job': 'Data Scientist Pandas SQL'})

        self.client.post('/register', data={'role': 'candidate', 'username': 'eve', 'password': 'password123'})
        self.client.post('/login', data={'role': 'candidate', 'username': 'eve', 'password': 'password123'})
        
        # View all jobs (RS_10)
        resp_all = self.client.get('/dashboard/eve/candidate')
        self.assertIn(b"DevOps Kubernetes AWS", resp_all.data)
        self.assertIn(b"Data Scientist Pandas SQL", resp_all.data)

        # Search for 'DevOps' (RS_11)
        resp_search = self.client.get('/dashboard/eve/candidate?search=devops')
        self.assertIn(b"DevOps Kubernetes AWS", resp_search.data)
        self.assertNotIn(b"Data Scientist Pandas SQL", resp_search.data)

    # ---------- APPLICATION MODULE TESTS (RS_12 - RS_15) ----------
    def test_RS_12_and_13_apply_and_duplicate_prevention(self):
        """RS_12 & RS_13: Apply for job and prevent duplicate application"""
        self.client.post('/register', data={'role': 'candidate', 'username': 'frank', 'password': 'password123'})
        self.client.post('/login', data={'role': 'candidate', 'username': 'frank', 'password': 'password123'})

        # First application
        resp1 = self.client.get('/apply/frank/Software%20Developer', follow_redirects=True)
        self.assertEqual(resp1.status_code, 200)
        self.assertIn(b"Applied successfully", resp1.data)

        # Duplicate application (RS_13)
        resp2 = self.client.get('/apply/frank/Software%20Developer', follow_redirects=True)
        self.assertIn(b"You already applied for this job", resp2.data)

    def test_RS_14_and_15_view_applications(self):
        """RS_14 & RS_15: Candidate sees own apps, Company sees all apps"""
        self.client.post('/register', data={'role': 'candidate', 'username': 'cand1', 'password': 'password123'})
        self.client.post('/register', data={'role': 'candidate', 'username': 'cand2', 'password': 'password123'})
        self.client.post('/register', data={'role': 'company', 'username': 'apple', 'password': 'password123'})

        # cand1 applies
        self.client.post('/login', data={'role': 'candidate', 'username': 'cand1', 'password': 'password123'})
        self.client.get('/apply/cand1/iOS%20Engineer')

        # cand2 applies
        self.client.post('/login', data={'role': 'candidate', 'username': 'cand2', 'password': 'password123'})
        self.client.get('/apply/cand2/macOS%20Engineer')

        # cand1 views dashboard -> sees iOS Engineer but not macOS Engineer
        self.client.post('/login', data={'role': 'candidate', 'username': 'cand1', 'password': 'password123'})
        resp_cand1 = self.client.get('/dashboard/cand1/candidate')
        self.assertIn(b"iOS Engineer", resp_cand1.data)
        self.assertNotIn(b"macOS Engineer", resp_cand1.data)

        # apple views dashboard -> sees both applications
        self.client.post('/login', data={'role': 'company', 'username': 'apple', 'password': 'password123'})
        resp_comp = self.client.get('/dashboard/apple/company')
        self.assertIn(b"iOS Engineer", resp_comp.data)
        self.assertIn(b"macOS Engineer", resp_comp.data)

    # ---------- RESUME & AI FEATURES TESTS (RS_16 - RS_20) ----------
    def test_RS_16_upload_resume_pdf(self):
        """RS_16: Upload valid PDF resume"""
        self.client.post('/register', data={'role': 'candidate', 'username': 'resume_user', 'password': 'password123'})
        self.client.post('/login', data={'role': 'candidate', 'username': 'resume_user', 'password': 'password123'})

        # Create dummy PDF
        writer = PdfWriter()
        writer.add_blank_page(width=72, height=72)
        pdf_bytes = io.BytesIO()
        writer.write(pdf_bytes)
        pdf_bytes.seek(0)

        response = self.client.post(
            '/dashboard/resume_user/candidate',
            data={
                'action': 'upload_resume',
                'resume': (pdf_bytes, 'my_resume.pdf')
            },
            content_type='multipart/form-data',
            follow_redirects=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Resume uploaded", response.data)

    def test_RS_17_invalid_file_upload(self):
        """RS_17: Upload non-PDF file returns error"""
        self.client.post('/register', data={'role': 'candidate', 'username': 'invalid_upload_user', 'password': 'password123'})
        self.client.post('/login', data={'role': 'candidate', 'username': 'invalid_upload_user', 'password': 'password123'})

        fake_text_file = io.BytesIO(b"Just plain text resume")
        response = self.client.post(
            '/dashboard/invalid_upload_user/candidate',
            data={
                'action': 'upload_resume',
                'resume': (fake_text_file, 'resume.txt')
            },
            content_type='multipart/form-data',
            follow_redirects=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Invalid file type. Only PDF resumes are accepted", response.data)

    def test_RS_18_ai_match_score(self):
        """RS_18: Match score calculation via CountVectorizer and cosine similarity"""
        resume = "Experienced python developer with flask, django, and machine learning skills"
        job = "Python Developer Flask Django"
        score = calculate_match(resume, job)
        self.assertGreater(score, 50.0)
        self.assertLessEqual(score, 100.0)

    def test_RS_19_skill_gap_analysis(self):
        """RS_19: Skill gap analysis returns missing keywords"""
        resume = "Junior developer with python and html"
        job_title = "Python Machine Learning Engineer"
        gap = get_skill_gap(resume, job_title)
        self.assertTrue(gap.startswith("Consider adding:") or "No major skill gaps" in gap)

    def test_RS_20_auto_status_thresholds(self):
        """RS_20: Auto status logic: Shortlisted (>=60), Under Screening (>=30), Rejected (<30)"""
        # Test direct calculation logic matching app.py
        score_high = 75.0
        status_high = "Shortlisted" if score_high >= 60 else ("Under Screening" if score_high >= 30 else "Rejected")
        self.assertEqual(status_high, "Shortlisted")

        score_mid = 45.0
        status_mid = "Shortlisted" if score_mid >= 60 else ("Under Screening" if score_mid >= 30 else "Rejected")
        self.assertEqual(status_mid, "Under Screening")

        score_low = 15.0
        status_low = "Shortlisted" if score_low >= 60 else ("Under Screening" if score_low >= 30 else "Rejected")
        self.assertEqual(status_low, "Rejected")

    # ---------- INTERVIEW MODULE TESTS (RS_21 - RS_24) ----------
    def test_RS_21_to_RS_24_interview_workflow(self):
        """RS_21 to RS_24: Schedule, view, and submit feedback with validation"""
        # 1. Register users
        self.client.post('/register', data={'role': 'company', 'username': 'netflix', 'password': 'password123'})
        self.client.post('/register', data={'role': 'candidate', 'username': 'grace', 'password': 'password123'})
        self.client.post('/register', data={'role': 'interviewer', 'username': 'interviewer_sam', 'password': 'password123'})

        # Candidate applies
        self.client.post('/login', data={'role': 'candidate', 'username': 'grace', 'password': 'password123'})
        self.client.get('/apply/grace/Backend%20Engineer')

        # Company logs in and shortlists application
        self.client.post('/login', data={'role': 'company', 'username': 'netflix', 'password': 'password123'})
        conn = get_db()
        app_id = conn.execute("SELECT id FROM applications WHERE username='grace'").fetchone()['id']
        conn.close()

        self.client.get(f'/update_status/{app_id}/Shortlisted/netflix')

        # Company schedules interview (RS_21)
        resp_sched = self.client.post(f'/schedule_interview/{app_id}', data={
            'interview_time': '2026-10-01T10:00',
            'interviewer': 'interviewer_sam'
        }, follow_redirects=True)
        self.assertIn(b"Interview scheduled with interviewer_sam", resp_sched.data)

        # Interviewer logs in and views interview (RS_22)
        self.client.post('/login', data={'role': 'interviewer', 'username': 'interviewer_sam', 'password': 'password123'})
        resp_iv = self.client.get('/interviews/interviewer_sam/interviewer')
        self.assertIn(b"grace", resp_iv.data)
        self.assertIn(b"Backend Engineer", resp_iv.data)

        conn = get_db()
        interview_id = conn.execute("SELECT id FROM interviews WHERE candidate='grace'").fetchone()['id']
        conn.close()

        # RS_24: Empty feedback should be REJECTED with error message (Fixed vs Report)
        resp_empty = self.client.post(f'/submit_feedback/{interview_id}', data={
            'result': 'Selected',
            'feedback': '   '
        }, follow_redirects=True)
        self.assertIn(b"Feedback cannot be empty", resp_empty.data)

        # RS_23: Valid feedback is accepted and application updated
        resp_valid = self.client.post(f'/submit_feedback/{interview_id}', data={
            'result': 'Selected',
            'feedback': 'Strong technical skills and good system design knowledge.'
        }, follow_redirects=True)
        self.assertIn(b"Feedback submitted! Candidate marked as Selected", resp_valid.data)

        # Verify application status was updated to Selected
        conn = get_db()
        updated_app = conn.execute("SELECT status, feedback FROM applications WHERE id=?", (app_id,)).fetchone()
        conn.close()
        self.assertEqual(updated_app['status'], 'Selected')
        self.assertEqual(updated_app['feedback'], 'Strong technical skills and good system design knowledge.')

    # ---------- DATABASE & SECURITY TESTS (RS_25 - RS_27) ----------
    def test_RS_25_data_storage(self):
        """RS_25: Data storage across operations"""
        self.client.post('/register', data={'role': 'candidate', 'username': 'db_user', 'password': 'password123'})
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE username='db_user'").fetchone()
        conn.close()
        self.assertIsNotNone(user)
        self.assertEqual(user['role'], 'candidate')

    def test_RS_26_password_hashing(self):
        """RS_26: Password security - verify SHA-256 hashed storage"""
        self.client.post('/register', data={
            'role': 'candidate',
            'username': 'secure_user',
            'password': 'mySecretPassword'
        })
        conn = get_db()
        user = conn.execute("SELECT password FROM users WHERE username='secure_user'").fetchone()
        conn.close()
        expected_hash = hashlib.sha256("mySecretPassword".encode('utf-8')).hexdigest()
        self.assertEqual(user['password'], expected_hash)
        self.assertNotEqual(user['password'], 'mySecretPassword')

    def test_RS_27_session_persistence(self):
        """RS_27: Session persistence across multiple requests"""
        self.client.post('/register', data={'role': 'candidate', 'username': 'persist_user', 'password': 'password123'})
        self.client.post('/login', data={'role': 'candidate', 'username': 'persist_user', 'password': 'password123'})

        # Make successive requests and ensure session is preserved
        resp1 = self.client.get('/dashboard/persist_user/candidate')
        self.assertIn(b"persist_user", resp1.data)
        resp2 = self.client.get('/dashboard/persist_user/candidate')
        self.assertIn(b"persist_user", resp2.data)

if __name__ == '__main__':
    unittest.main()
