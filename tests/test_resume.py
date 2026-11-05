import io
import unittest
import zipfile
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import ValidationError
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject

from hives.careers.app import app
from hives.careers.matching import Profile, SkillEvidence, match, requirements
from hives.careers.resume import build_draft, extract_text, import_resume, MAX_UPLOAD, ResumeError


TEXT = """Education
Pursuing Bachelor of Science in Computer Science
Expected graduation: May 2028
GPA: 3.60/4.0
Projects
Built a Python API with PostgreSQL and Docker for a student club.
Skills: JavaScript, SQL
"""


def docx(xml):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("word/document.xml", xml)
    return output.getvalue()


def pdf(text="Python SQL student resume", encrypted=False, pages=1):
    writer = PdfWriter()
    for _ in range(pages):
        page = writer.add_blank_page(612, 792)
        font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})})
        content = DecodedStreamObject()
        content.set_data(f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode())
        page[NameObject("/Contents")] = content
    if encrypted:
        writer.encrypt("test-password")
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


class ResumeTests(unittest.TestCase):
    def test_text_draft_preserves_evidence_and_does_not_infer_private_details(self):
        data = build_draft(extract_text(TEXT.encode(), "txt"))
        draft = data["draft"]
        self.assertEqual(draft["graduation_year"], 2028)
        self.assertEqual(draft["gpa"], 3.6)
        self.assertEqual(draft["degree_level"], "bachelor")
        self.assertEqual(draft["major"], "Computer Science")
        self.assertEqual(draft["degree_status"], "in_progress")
        python = next(s for s in draft["skills"] if s["skill"] == "Python")
        self.assertIn("Built a Python API", python["evidence"])
        for field in ["needs_sponsorship", "enrolled", "experience_years", "available_from"]:
            self.assertIsNone(draft[field])

    def test_ambiguous_education_is_not_silently_selected(self):
        draft = build_draft(TEXT + "\nMaster of Science in Finance\nExpected graduation: 2030\n")
        self.assertIsNone(draft["draft"]["graduation_year"])
        self.assertEqual(draft["draft"]["degree_level"], "")
        self.assertTrue(any("Multiple degree" in w for w in draft["warnings"]))
        unscaled = build_draft("Resume skills Python\nGPA: 3.8\n")
        self.assertIsNone(unscaled["draft"]["gpa"])
        scrum = build_draft("Experience\nScrum Master\nBuilt a Python project\n")
        self.assertEqual(scrum["draft"]["degree_level"], "")
        office = build_draft("Skills\nMS Office and Excel\nBuilt a budget model for Finance\n")
        self.assertEqual(office["draft"]["degree_level"], "")

    def test_docx_paragraphs_and_unsafe_xml(self):
        xml = b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Education Python SQL</w:t></w:r></w:p><w:p><w:r><w:t>Built a project with Docker</w:t></w:r></w:p></w:body></w:document>'
        text = extract_text(docx(xml), "docx")
        self.assertIn("Education Python SQL\nBuilt a project", text)
        with self.assertRaises(ResumeError):
            extract_text(docx(b'<!DOCTYPE x [<!ENTITY test "secret">]><x>&test;</x>'), "docx")
        with self.assertRaises(ResumeError):
            extract_text(b"not a document", "docx")

    def test_pdf_text_encryption_and_page_limit(self):
        self.assertIn("Python SQL", extract_text(pdf(), "pdf"))
        for value in [pdf(encrypted=True), pdf(pages=11), b"not a pdf"]:
            with self.assertRaises(ResumeError):
                extract_text(value, "pdf")
        writer = PdfWriter()
        writer.add_blank_page(612, 792)
        blank = io.BytesIO()
        writer.write(blank)
        with self.assertRaisesRegex(ResumeError, "No readable"):
            extract_text(blank.getvalue(), "pdf")

    def test_limits_and_worker_roundtrip(self):
        for value in [b"", b"x" * (MAX_UPLOAD + 1), b"x" * 60001]:
            with self.assertRaises(ResumeError):
                extract_text(value, "txt")
        self.assertEqual(import_resume(TEXT.encode(), "txt")["draft"]["graduation_year"], 2028)
        with self.assertRaisesRegex(ResumeError, "took too long"):
            import subprocess
            with patch("hives.careers.resume.subprocess.run", side_effect=subprocess.TimeoutExpired("worker", 15)):
                import_resume(TEXT.encode(), "txt")

    def test_import_endpoint_is_private_and_never_calls_store(self):
        with patch("hives.careers.api.store.catalog", side_effect=AssertionError("must not access profiles or jobs")), TestClient(app) as client:
            response = client.post("/api/careers/resume?format=txt", content=TEXT.encode())
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["cache-control"], "no-store")
            self.assertIn("draft", response.json())
            self.assertNotIn("resume_text", response.json())
            bad = client.post("/api/careers/resume?format=pdf", content=b"secret invalid file")
            self.assertEqual(bad.status_code, 422)
            self.assertEqual(bad.headers["cache-control"], "no-store")
            self.assertNotIn("secret invalid", bad.text)
            large = client.post("/api/careers/resume?format=txt", content=b"x" * (MAX_UPLOAD + 1))
            self.assertEqual(large.status_code, 413)


class ChecklistTests(unittest.TestCase):
    def test_alternatives_do_not_swallow_conjunctive_requirements(self):
        checks = requirements("Requirements\nPython or Java, and SQL required\nPython, Java, or C++ preferred")
        self.assertEqual(checks[0]["skills"], ["Python", "Java"])
        self.assertEqual(checks[1]["skills"], ["SQL"])
        self.assertEqual(checks[2]["skills"], ["Python", "Java", "C++"])
        result = match({"description": "Requirements\nPython or Java and SQL", "location": ""}, Profile(skills=[SkillEvidence(skill="Java")]))
        self.assertEqual(result["score"], 50)
        self.assertEqual(result["qualification_summary"]["required_skill_gaps"], 1)

    def test_degree_major_experience_and_availability_have_source_evidence(self):
        job = {"description": "Requirements\nMust be pursuing a bachelor's or master's degree in Computer Science or Mathematics.\nMinimum 2 years of professional experience required.\nMust start on June 1, 2027.", "location": ""}
        profile = Profile(degree_level="bachelor", degree_status="in_progress", major="Computer Science", experience_years=3, available_from="2027-05-15")
        result = match(job, profile)
        by_name = {c["criterion"]: c for c in result["eligibility"]}
        self.assertEqual(by_name["Degree / program"]["status"], "matches")
        self.assertEqual(by_name["Field of study"]["status"], "matches")
        self.assertEqual(by_name["Relevant experience"]["status"], "unknown")
        self.assertEqual(by_name["Availability"]["status"], "matches")
        self.assertIn("bachelor", by_name["Degree / program"]["quote"])
        self.assertIn("Bachelor", by_name["Degree / program"]["evidence"])

    def test_unearned_degree_related_major_and_preferences_do_not_reject(self):
        job = {"description": "Requirements\nA completed bachelor's degree in Computer Science or a related field is required.\nPreferred qualifications\nMinimum GPA of 3.8 preferred", "location": ""}
        result = match(job, Profile(degree_level="bachelor", degree_status="in_progress", major="Physics", gpa=3))
        self.assertFalse(result["has_conflict"])
        self.assertTrue(all(c["status"] == "unknown" for c in result["eligibility"]))
        other_scale = match({"description": "Minimum GPA of 3.5/5.0 required", "location": ""}, Profile(gpa=3.8))
        self.assertEqual(other_scale["eligibility"][0]["status"], "unknown")

    def test_date_validation_and_sponsorship_negation(self):
        with self.assertRaises(ValidationError):
            Profile(available_from="2027-07-01", available_until="2027-06-01")
        result = match({"description": "No sponsorship needed to participate in this workshop.", "location": ""}, Profile(needs_sponsorship=True))
        self.assertFalse(result["has_conflict"])

    def test_start_and_end_dates_are_compared_separately(self):
        job = {"description": "Requirements\nStart date: June 1, 2027; end date: August 31, 2027.", "location": ""}
        result = match(job, Profile(available_from="2027-05-01", available_until="2027-07-01"))
        dates = [c for c in result["eligibility"] if c["criterion"] == "Availability"]
        self.assertEqual([c["status"] for c in dates], ["matches", "conflict"])

    def test_unrecognized_authorization_requirement_stays_visible(self):
        result = match({"description": "Requirements\nMust have authorization to work in Canada.", "location": ""}, Profile(needs_sponsorship=False))
        check = next(c for c in result["eligibility"] if c["criterion"] == "Other stated qualification")
        self.assertEqual(check["status"], "unknown")
        self.assertIn("Canada", check["quote"])


if __name__ == "__main__":
    unittest.main()
