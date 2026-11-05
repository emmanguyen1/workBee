"""Evidence-backed checks. Unknown wording is never treated as a rejection."""
import re
from datetime import date, datetime
from functools import lru_cache

DEGREES = {
    "associate": r"associate(?:['’]s)?(?:\s+degree|\s+of|\s+in)",
    "bachelor": r"bachelor(?:['’]s)?|\bB\.?S\.?\b|\bB\.?A\.?\b|undergraduate",
    "master": r"master(?:['’]s)?|\bM\.?S\.?\b|\bM\.?B\.?A\.?\b",
    "doctorate": r"doctorate|doctoral|\bPh\.?D\.?\b",
}
MAJORS = {
    "Computer Science": ["computer science", "cs"],
    "Computer Engineering": ["computer engineering"],
    "Electrical Engineering": ["electrical engineering"],
    "Mechanical Engineering": ["mechanical engineering"],
    "Data Science": ["data science"], "Mathematics": ["mathematics", "math"],
    "Statistics": ["statistics"], "Business": ["business", "business administration"],
    "Finance": ["finance"], "Accounting": ["accounting"], "Economics": ["economics"],
    "Marketing": ["marketing"], "Communications": ["communications", "communication"],
    "Design": ["design", "graphic design"], "Biology": ["biology", "biological sciences"],
    "Chemistry": ["chemistry"], "Psychology": ["psychology"], "English": ["english"],
}


def degrees_in(text):
    return [key for key, pattern in DEGREES.items() if re.search(pattern, text, re.I)]


def majors_in(text):
    return [name for name, aliases in MAJORS.items() if any(re.search(r"\b" + re.escape(a) + r"\b", text, re.I) for a in aliases)]


def requirement_lines(description):
    section = "mentioned"
    for raw in description.splitlines():
        line = raw.strip(" •-\t")
        if not line:
            continue
        if len(line) < 100:
            if re.search(r"nice to have|preferred qualifications|bonus points|bonus qualifications|preferred skills", line, re.I):
                section = "preferred"
            elif re.search(r"qualifications|requirements|what you.bring|skills you.ll need|what you.ll need|what we.re looking for|who you are|about you", line, re.I):
                section = "required"
            elif re.fullmatch(r"(?:about.*|responsibilities|benefits|what you.ll do|what you.ll achieve|compensation)[: ]*", line, re.I):
                section = "mentioned"
        kind = section
        if re.search(r"preferred|nice to have|bonus|a plus", line, re.I):
            kind = "preferred"
        elif re.search(r"\b(must|required|minimum|at least|proficien\w*|experience with|knowledge of)\b", line, re.I):
            kind = "required"
        if re.search(r"not required|no .{0,35}experience (?:is )?(?:required|necessary)", line, re.I):
            kind = "mentioned"
        yield line, kind


def explicit_date(text):
    match = re.search(r"\b20\d{2}-\d{2}-\d{2}\b", text)
    if match:
        try:
            return date.fromisoformat(match[0])
        except ValueError:
            return None
    match = re.search(r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(20\d{2})\b", text, re.I)
    if match:
        try:
            return datetime.strptime(" ".join(match.groups()), "%B %d %Y").date()
        except ValueError:
            return None
    return None


@lru_cache(maxsize=512)
def qualification_rules(description):
    rules = []
    def add(criterion, line, kind, **values):
        rules.append({"criterion": criterion, "quote": line[:1200], "kind": kind, **values})
    for line, kind in requirement_lines(description):
        minimum = re.search(r"\b(?:minimum|min\.?)\s+(?:cumulative\s+)?GPA\s*(?:of|:)?\s*(\d(?:\.\d+)?)|\bGPA\s+(?:of\s+)?at least\s+(\d(?:\.\d+)?)", line, re.I)
        if minimum:
            threshold = float(next(v for v in minimum.groups() if v is not None))
            scale = re.search(r"(?:/|out of)\s*(\d(?:\.\d+)?)", line)
            if 0 <= threshold <= 4:
                add("Minimum GPA (4.0 scale)", line, kind, minimum=threshold, ambiguous_scale=bool(scale and float(scale[1]) != 4))
        if re.search(r"(?:currently|must be) enrolled", line, re.I):
            add("Enrollment", line, "preferred" if kind == "preferred" else "required")
        if re.search(r"(?:no (?:visa )?sponsorship(?:\s+(?:is\s+)?(?:available|offered|provided)|[.!]?$)|(?:cannot|unable to|do not|will not) (?:provide |offer )?(?:visa )?sponsor)", line, re.I):
            add("Sponsorship", line, "preferred" if kind == "preferred" else "required")
        years = re.search(r"graduat\w*.{0,60}?(20\d{2})\s*(?:-|–|to|and)\s*(20\d{2})", line, re.I)
        if years:
            start, end = map(int, years.groups())
            if start <= end:
                add("Graduation window", line, "preferred" if kind == "preferred" else "required", start=start, end=end)
        degrees = degrees_in(line)
        if degrees and re.search(r"degree|pursuing|enrolled|student|bachelor|master|doctor", line, re.I):
            add("Degree / program", line, kind, degrees=degrees,
                pursuing=bool(re.search(r"pursuing|enrolled|student|working toward", line, re.I)),
                earned=bool(re.search(r"completed|earned|hold(?:ing)?|have a", line, re.I)),
                alternative=bool(re.search(r"equivalent|or .{0,30}experience", line, re.I)))
        majors = majors_in(line)
        if majors and re.search(r"degree|major(?:ing)?|studying|study|bachelor|master|doctor", line, re.I):
            add("Field of study", line, kind, majors=majors)
        experience = re.search(r"\b(\d{1,2})(?:\+|\s*[-–]\s*\d{1,2})?\s+years?(?:['’])?\s+(?:(?:of|relevant|professional|industry|work)\s+){0,3}experience\b", line, re.I)
        if experience:
            add("Relevant experience", line, kind, minimum=int(experience[1]), alternative=bool(re.search(r"\bor\b", line, re.I)))
        markers = list(re.finditer(r"start date|starting on|must (?:be available|start)|end date|ending on", line, re.I))
        if markers:
            for index, marker in enumerate(markers):
                segment = line[marker.start():markers[index + 1].start() if index + 1 < len(markers) else len(line)]
                when = explicit_date(segment)
                if when:
                    add("Availability", line, kind, date=when.isoformat(), end=bool(re.search(r"end date|ending on", marker[0], re.I)))
        elif re.search(r"\b(?:summer|fall|spring|winter)\s+20\d{2}\b", line, re.I) and len(line) < 250:
            add("Availability", line, kind, date=None)
    return rules


def qualification_checks(description, profile, skill_quotes=()):
    checks = []
    for rule in qualification_rules(description):
        criterion, status, evidence, explanation = rule["criterion"], "unknown", "Not supplied in your profile.", "Confirm this requirement with the employer."
        if criterion == "Minimum GPA (4.0 scale)" and profile.gpa is not None:
            evidence = f"Your GPA: {profile.gpa:g}/4.0"
            if not rule["ambiguous_scale"]:
                status = "matches" if profile.gpa >= rule["minimum"] else "conflict"
                explanation = "Compared with the stated minimum on a 4.0 scale."
            else:
                explanation = "Employer appears to use a different GPA scale."
        elif criterion == "Enrollment" and profile.enrolled is not None:
            status = "matches" if profile.enrolled else "conflict"
            evidence = "Currently enrolled" if profile.enrolled else "Not currently enrolled"
            explanation = "Compared with the explicit enrollment statement."
        elif criterion == "Sponsorship" and profile.needs_sponsorship is not None:
            status = "conflict" if profile.needs_sponsorship else "matches"
            evidence = "Employer sponsorship needed" if profile.needs_sponsorship else "Employer sponsorship not needed"
            explanation = "Only compares sponsorship needs; it does not establish work authorization."
        elif criterion == "Graduation window" and profile.graduation_year is not None:
            status = "matches" if rule["start"] <= profile.graduation_year <= rule["end"] else "conflict"
            evidence = f"Graduation year: {profile.graduation_year}"
            explanation = "Year-only comparison; confirm exact graduation dates."
        elif criterion == "Degree / program" and profile.degree_level:
            evidence = f"{profile.degree_level.title()} · {profile.degree_status or 'completion status not specified'}"
            level_matches = profile.degree_level in rule["degrees"]
            if level_matches and ((rule["pursuing"] and profile.degree_status == "in_progress") or (not rule["pursuing"] and profile.degree_status == "completed")):
                status = "matches"
            explanation = "Check whether the employer requires a current program or an earned degree. Other education/experience pathways may qualify."
        elif criterion == "Field of study" and profile.major:
            evidence = f"Your field of study: {profile.major}"
            if set(majors_in(profile.major)) & set(rule["majors"]):
                status = "matches"
            explanation = "Related fields may qualify; an unmatched major needs review rather than automatic exclusion."
        elif criterion == "Relevant experience" and profile.experience_years is not None:
            evidence = f"Self-reported relevant experience: {profile.experience_years:g} years"
            # Duration alone cannot establish the employer's required kind of experience.
            status = "unknown"
            explanation = f"The listing mentions {rule['minimum']}+ years. Confirm relevance, professional versus academic experience, and alternative qualification pathways."
        elif criterion == "Availability" and rule["date"]:
            when = date.fromisoformat(rule["date"])
            supplied = profile.available_until if rule["end"] else profile.available_from
            if supplied:
                status = "matches" if (supplied >= when if rule["end"] else supplied <= when) else "conflict"
                evidence = f"Available {'until' if rule['end'] else 'from'}: {supplied.isoformat()}"
                explanation = "Compared with the explicit employer date; confirm working hours and the full internship period."
        elif criterion == "Availability":
            explanation = "A season is mentioned without exact dates; confirm start and end dates."
        # Preferences and contextual mentions are not eligibility blockers.
        if status == "conflict" and rule["kind"] != "required":
            status = "unknown"
            explanation += " This was not identified as a required qualification."
        checks.append({"criterion": criterion, "status": status, "quote": rule["quote"], "kind": rule["kind"], "evidence": evidence, "explanation": explanation})
    covered = {c["quote"] for c in checks} | set(skill_quotes)
    for line, kind in requirement_lines(description):
        if kind not in {"required", "preferred"} or line[:1200] in covered or not 25 <= len(line) <= 1200:
            continue
        if re.search(r"ability|experience|knowledge|familiarity|proficien|communication|comfortable|willing|eligible|authorization|citizenship|clearance", line, re.I):
            checks.append({"criterion": "Other stated qualification", "status": "unknown", "kind": kind,
                           "quote": line, "evidence": "Not automatically assessed.",
                           "explanation": "Review this requirement against your actual experience and confirm any eligibility details with the employer."})
            covered.add(line)
    for criterion in ("Enrollment", "Sponsorship", "Graduation window"):
        if not any(c["criterion"] == criterion for c in checks):
            checks.append({"criterion": criterion, "status": "unknown", "kind": "unspecified", "quote": "No explicit rule recognized. Check the employer description.", "evidence": "", "explanation": "Missing information does not establish eligibility or ineligibility."})
    return checks
