"""In-memory resume extraction. Worker reads stdin; only a review draft leaves it."""
import io
import json
import re
import subprocess
import sys
import zipfile

from hives.careers.matching import Profile, SkillEvidence, mentions, SKILLS, skills_in
from hives.careers.qualifications import degrees_in, majors_in

MAX_UPLOAD = 4 * 1024 * 1024
MAX_TEXT = 60000
MAX_XML = 2 * 1024 * 1024
FORMATS = {"pdf", "docx", "txt"}


class ResumeError(ValueError):
    pass


def extract_text(data, file_format):
    if not data or len(data) > MAX_UPLOAD:
        raise ResumeError("Use a non-empty resume up to 4 MB.")
    if file_format == "txt":
        try:
            text = data.decode("utf-8-sig")
        except UnicodeError as exc:
            raise ResumeError("Text must be UTF-8. Export your resume as PDF, DOCX, or paste its text.") from exc
        if "\x00" in text:
            raise ResumeError("This is not a supported text file.")
    elif file_format == "docx":
        from defusedxml.ElementTree import fromstring
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                entries = archive.infolist()
                if len(entries) > 2000 or sum(e.file_size for e in entries) > 12 * 1024 * 1024:
                    raise ResumeError("DOCX content is too large. Export a simpler resume or paste its text.")
                info = archive.getinfo("word/document.xml")
                if info.file_size > MAX_XML or info.flag_bits & 1:
                    raise ResumeError("Use a smaller, unencrypted DOCX file.")
                with archive.open(info) as document:
                    xml = document.read(MAX_XML + 1)
                if len(xml) > MAX_XML:
                    raise ResumeError("DOCX document is too large.")
                root = fromstring(xml, forbid_dtd=True, forbid_entities=True, forbid_external=True)
                ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
                text = "\n".join(" ".join(node.text or "" for node in paragraph.iter(ns + "t")) for paragraph in root.iter(ns + "p"))
        except ResumeError:
            raise
        except Exception as exc:
            raise ResumeError("Could not read this DOCX. Export it again or paste the resume text.") from exc
    elif file_format == "pdf":
        from pypdf import PdfReader
        if not data.startswith(b"%PDF-"):
            raise ResumeError("This file is not a PDF. Choose a PDF, DOCX, or text file.")
        try:
            reader = PdfReader(io.BytesIO(data), strict=True)
            if reader.is_encrypted:
                raise ResumeError("Password-protected PDFs are not supported. Upload an unlocked copy or paste text.")
            if len(reader.pages) > 10:
                raise ResumeError("Use a resume with 10 pages or fewer.")
            parts, size = [], 0
            for page in reader.pages:
                contents = page.get_contents()
                if contents is not None and len(contents.get_data()) > 4 * 1024 * 1024:
                    raise ResumeError("PDF page content is too complex. Export a simpler PDF or paste text.")
                value = page.extract_text() or ""
                size += len(value)
                if size > MAX_TEXT:
                    raise ResumeError("Resume text is too long. Use up to 60,000 characters.")
                parts.append(value)
            text = "\n".join(parts)
        except ResumeError:
            raise
        except Exception as exc:
            raise ResumeError("Could not read this PDF. Export it again or paste the resume text.") from exc
    else:
        raise ResumeError("Supported formats are PDF, DOCX, and UTF-8 text.")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", text)
    if len(text) > MAX_TEXT:
        raise ResumeError("Resume text is too long. Use up to 60,000 characters.")
    if len(text.strip()) < 20:
        raise ResumeError("No readable resume text found. Scanned/image-only PDFs need OCR first; paste their text instead.")
    return text


def build_draft(text):
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines() if line.strip()]
    skills = []
    warnings = ["Review and correct these suggestions before using them for matching.",
                "Work authorization, sponsorship needs, experience duration, and availability were not inferred."]
    recognized = skills_in(text)
    if len(recognized) > 60:
        warnings.append("More than 60 known skills found; review the first 60 suggestions and choose the most relevant ones.")
    for skill in recognized[:60]:
        contexts = [line for line in lines if any(mentions(line, a) for a in SKILLS[skill])]
        context = next((line for line in contexts if re.search(r"built|developed|designed|created|analy[sz]ed|implemented|managed", line, re.I)), contexts[0])
        # Contact details are not useful skill evidence.
        context = re.sub(r"\S+@\S+|https?://\S+", "", context)
        skills.append(SkillEvidence(skill=skill, evidence=context[:1000].strip()))
    values, fields = {"skills": skills}, []
    education, in_education = [], False
    for line in lines:
        if re.fullmatch(r"education|academic background|academic qualifications|academics", line, re.I):
            in_education = True
        elif re.fullmatch(r"(?:technical )?skills|projects|(?:work |professional )?experience|summary|certifications", line, re.I):
            in_education = False
        spelled_out = re.search(r"\bdegree\b|bachelor|master(?:['’]s| of)|doctorate|doctoral|\bPh\.?D\b", line, re.I)
        abbreviation = re.search(r"\b[BM]\.?[SA]\.?(?:\s|$)", line, re.I)
        office_software = re.search(r"\bM\.?S\.?\s+(?:Office|Excel|Word|PowerPoint|Access|Outlook|Teams|Project)\b", line, re.I)
        if degrees_in(line) and not office_software and (spelled_out or (abbreviation and (in_education or majors_in(line)))):
            education.append(line)
    levels = {level for line in education for level in degrees_in(line)}
    if len(levels) == 1:
        values["degree_level"] = next(iter(levels))
        fields.append({"field": "Degree / program", "quote": education[0][:1000]})
    elif levels:
        warnings.append("Multiple degree levels found; select the program you want to match against.")
    majors = list(dict.fromkeys(major for line in education for major in majors_in(line)))
    if majors:
        values["major"] = ", ".join(majors)[:100]
    if any(re.search(r"pursuing|in progress|currently enrolled", line, re.I) for line in education):
        values["degree_status"] = "in_progress"
    elif any(re.search(r"awarded|completed|earned", line, re.I) for line in education):
        values["degree_status"] = "completed"
    years = {}
    for line in lines:
        found = re.search(r"(?:expected(?: graduation)?|anticipated(?: graduation)?|graduation(?: date)?)\s*[:\-]?\s*(?:(?:[A-Za-z]+)\s+)?(20\d{2})\b", line, re.I)
        if found and 2020 <= int(found[1]) <= 2040:
            years[int(found[1])] = line
    if len(years) == 1:
        values["graduation_year"] = next(iter(years))
        fields.append({"field": "Graduation year", "quote": next(iter(years.values()))[:1000]})
    elif years:
        warnings.append("Multiple graduation years found; choose the correct one manually.")
    gpas = {}
    for line in lines:
        gpa = re.search(r"\bGPA\s*[:\-]?\s*([0-4](?:\.\d+)?)\s*/\s*4(?:\.0+)?\b", line, re.I)
        if gpa and float(gpa[1]) <= 4:
            gpas[float(gpa[1])] = line
    if len(gpas) == 1:
        values["gpa"] = next(iter(gpas))
        fields.append({"field": "GPA", "quote": next(iter(gpas.values()))[:1000]})
    elif any(re.search(r"\bGPA\b", line, re.I) for line in lines):
        warnings.append("GPA was ambiguous or its 4.0 scale was not explicit; enter it manually if applicable.")
    if not skills:
        warnings.append("No known skill names recognized. You can enter additional skills and evidence manually.")
    return {"draft": Profile(**values).model_dump(mode="json"), "fields": fields, "warnings": warnings}


def import_resume(data, file_format):
    """Bound parser runtime in a separate process; no uploaded file is written."""
    try:
        result = subprocess.run([sys.executable, "-m", "hives.careers.resume", file_format], input=data, capture_output=True, timeout=15)
    except subprocess.TimeoutExpired as exc:
        raise ResumeError("Resume processing took too long. Export a simpler file or paste its text.") from exc
    if result.returncode != 0:
        raise ResumeError("Could not process this resume within the resource limits. Try a simpler file or pasted text.")
    try:
        payload = json.loads(result.stdout)
    except (ValueError, UnicodeError) as exc:
        raise ResumeError("Could not process this resume. Try pasted text instead.") from exc
    if "error" in payload:
        raise ResumeError(payload["error"])
    return payload


def main():
    # Resource limits are applied in the child process, never in the web server.
    if sys.platform == "linux":
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
    try:
        data = sys.stdin.buffer.read(MAX_UPLOAD + 1)
        payload = build_draft(extract_text(data, sys.argv[1]))
    except ResumeError as exc:
        payload = {"error": str(exc)}
    except Exception:
        payload = {"error": "Could not read this resume. Export it again or paste its text."}
    sys.stdout.write(json.dumps(payload))


if __name__ == "__main__":
    main()
