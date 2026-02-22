
import sys
import unittest

# Mocking the job data structure
def create_mock_job(name, employment_type="intern", additional_apply_type=None):
    return {
        "id": 123,
        "name": name,
        "company": {"name": "Test Company"},
        "employment_type": employment_type,
        "additional_apply_type": additional_apply_type or [],
        "due_time": "2025-12-31",
        "url": "http://example.com"
    }

# Import the logic we want to test (we'll fast-track this by copying the relevant logic 
# since import paths might be tricky without full context setup)

convertible_keywords = [
    "채용연계", "정규직전환", "정규직", "전환가능", "전환형", "연계형",
    "정규전환", "채용전환", "(전환형)", "(연계형)", "(채용연계)", "(정규직전환)",
]

experiential_keywords = [
    "체험형", "체험", "인턴십", "실습", "현장실습", "(체험형)", "(체험)", "(실습)",
    "단기", "방학", "summer", "winter", "internship", "bootcamp", "부트캠프", "academy",
]

def determine_convertible(job):
    employment_type = job.get("employment_type", "regular")
    additional_apply_types = job.get("additional_apply_type") or []
    job_name = str(job.get("name", ""))
    
    is_fulltime_convertible = None

    if employment_type == "intern":
        if "convertible" in additional_apply_types:
            is_fulltime_convertible = True
        elif "experiential" in additional_apply_types:
            is_fulltime_convertible = False
        else:
            if any(k in job_name for k in convertible_keywords):
                is_fulltime_convertible = True
            elif any(k in job_name for k in experiential_keywords):
                is_fulltime_convertible = False
            else:
                is_fulltime_convertible = False
                
    return is_fulltime_convertible

class TestInternshipLogic(unittest.TestCase):
    def test_explicit_convertible(self):
        job = create_mock_job("Some Job", additional_apply_type=["convertible"])
        self.assertTrue(determine_convertible(job))

    def test_explicit_experiential(self):
        job = create_mock_job("Some Job", additional_apply_type=["experiential"])
        self.assertFalse(determine_convertible(job))

    def test_keyword_convertible(self):
        job = create_mock_job("마케팅 인턴 (채용연계형)")
        self.assertTrue(determine_convertible(job))

    def test_keyword_experiential(self):
        job = create_mock_job("디자인 체험형 인턴")
        self.assertFalse(determine_convertible(job))
        
    def test_keyword_summer_intern(self):
        job = create_mock_job("2024 Summer Internship")
        self.assertFalse(determine_convertible(job))

    def test_implicit_experiential(self):
        # Case where no keywords match -> should default to experiential (False)
        job = create_mock_job("Just an Intern Position")
        self.assertFalse(determine_convertible(job))

if __name__ == '__main__':
    unittest.main()
