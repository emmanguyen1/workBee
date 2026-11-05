"""Conservative, inspectable rules; scores describe evidence, never hiring odds."""
import re
from functools import lru_cache
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator, field_validator
from hives.careers.geography import preferred_matches
from hives.careers.qualifications import qualification_checks, requirement_lines

REQUIREMENTS_VERSION = 3


SKILLS = {
    "Python": ["python"], "Java": ["java"], "JavaScript": ["javascript", "js"],
    "TypeScript": ["typescript"], "SQL": ["sql"], "PostgreSQL": ["postgresql", "postgres"],
    "React": ["react", "react.js", "reactjs"], "Node.js": ["node.js", "nodejs"],
    "C++": ["c++"], "C#": ["c#"], "Go": ["golang"], "Rust": ["rust"],
    "Docker": ["docker"], "Kubernetes": ["kubernetes", "k8s"],
    "AWS": ["aws", "amazon web services"], "Git": ["git"],
    "Linux": ["linux"], "Excel": ["excel"], "Figma": ["figma"],
    "TensorFlow": ["tensorflow"], "PyTorch": ["pytorch"], "Swift": ["swift"],
    "PowerPoint": ["powerpoint"], "Word": ["microsoft word"], "Google Sheets": ["google sheets"],
    "Tableau": ["tableau"], "Power BI": ["power bi", "powerbi"], "Salesforce": ["salesforce"],
    "HubSpot": ["hubspot"], "SEO": ["seo", "search engine optimization"],
    "Google Analytics": ["google analytics", "ga4"], "Google Ads": ["google ads", "adwords"],
    "Email marketing": ["email marketing"], "Social media": ["social media"],
    "Copywriting": ["copywriting"], "Market research": ["market research"],
    "Financial modeling": ["financial modeling", "financial modelling"],
    "Accounting": ["accounting"], "Bookkeeping": ["bookkeeping"], "QuickBooks": ["quickbooks"],
    "Adobe Photoshop": ["photoshop"], "Adobe Illustrator": ["adobe illustrator"],
    "Adobe InDesign": ["indesign"], "Adobe Premiere": ["premiere pro"],
    "User research": ["user research", "ux research"], "Prototyping": ["prototyping"],
    "AutoCAD": ["autocad"], "SolidWorks": ["solidworks"], "MATLAB": ["matlab"],
    "CAD": ["cad"], "LabVIEW": ["labview"], "Circuit design": ["circuit design"],
    "Project management": ["project management"], "Jira": ["jira"], "SAP": ["sap"],
    "Supply chain": ["supply chain"], "Inventory management": ["inventory management"],
    "Customer service": ["customer service"], "CRM": ["crm", "customer relationship management"],
    "Recruiting": ["recruiting", "recruitment"], "Workday": ["workday"],
    "Technical writing": ["technical writing"], "Public speaking": ["public speaking"],
    "Data analysis": ["data analysis"], "Statistics": ["statistics", "statistical analysis"],
    "Laboratory techniques": ["laboratory techniques", "lab techniques"], "PCR": ["pcr"],
    "Pandas": ["pandas"], "NumPy": ["numpy"], "Scikit-learn": ["scikit-learn", "sklearn"],
    "FastAPI": ["fastapi"], "Django": ["django"], "Flask": ["flask"],
    "HTML": ["html", "html5"], "CSS": ["css", "css3"], "GitHub": ["github"],
}


class SkillEvidence(BaseModel):
    skill: str = Field(max_length=60)
    evidence: str = Field(default="", max_length=1000)


class Profile(BaseModel):
    skills: list[SkillEvidence] = Field(default_factory=list, max_length=60)
    graduation_year: int | None = Field(default=None, ge=2020, le=2040)
    enrolled: bool | None = None
    needs_sponsorship: bool | None = None
    location: str = Field(default="", max_length=100)
    gpa: float | None = Field(default=None, ge=0, le=4)
    degree_level: Literal["", "associate", "bachelor", "master", "doctorate", "other"] = ""
    degree_status: Literal["", "in_progress", "completed"] = ""
    major: str = Field(default="", max_length=100)
    experience_years: float | None = Field(default=None, ge=0, le=60)
    available_from: date | None = None
    available_until: date | None = None

    @field_validator("skills", mode="before")
    @classmethod
    def normalize_skills(cls, values):
        """Accept comma/semicolon/newline lists without splitting evidence prose."""
        if isinstance(values, str):
            values = [{"skill": line.split("|", 1)[0], "evidence": line.split("|", 1)[1].strip() if "|" in line else ""} for line in values.splitlines()]
        if not isinstance(values, list):
            return values
        normalized = {}
        for item in values:
            if isinstance(item, SkillEvidence):
                item = item.model_dump()
            if not isinstance(item, dict) or not isinstance(item.get("skill"), str):
                return values
            for raw in re.split(r"[,;\n]", item["skill"]):
                if raw.strip():
                    name = canonical(raw.strip())
                    previous = normalized.get(name.casefold())
                    evidence = item.get("evidence", "")
                    if previous is None or (not previous["evidence"] and evidence):
                        normalized[name.casefold()] = {"skill": name, "evidence": evidence}
        return list(normalized.values())

    @model_validator(mode="after")
    def valid_availability(self):
        if self.available_from and self.available_until and self.available_until < self.available_from:
            raise ValueError("Availability end must be on or after the start date")
        return self


def mentions(text, alias):
    return bool(re.search(r"(?<![\w+#])" + re.escape(alias) + r"(?![\w+#])", text, re.I))


def canonical(skill):
    for name, aliases in SKILLS.items():
        if skill.casefold() in [name.casefold(), *aliases]:
            return name
    return skill.strip()


def skills_in(text):
    return [name for name, aliases in SKILLS.items() if any(mentions(text, alias) for alias in aliases)]


def alternative_groups(line, skills):
    """Keep conjunctive requirements outside adjacent alternative lists."""
    spans = []
    for name in skills:
        matches = [m for alias in SKILLS[name] if (m := re.search(r"(?<![\w+#])" + re.escape(alias) + r"(?![\w+#])", line, re.I))]
        if matches:
            first = min(matches, key=lambda m: (m.start(), -m.end()))
            spans.append((first.start(), first.end(), name))
    spans.sort()
    groups, run, has_or = [], [], False
    def flush():
        groups.extend([run.copy()] if has_or else [[name] for name in run])
    for index, (start, end, name) in enumerate(spans):
        if index:
            gap = line[spans[index - 1][1]:start]
            is_or = bool(re.fullmatch(r"\s*,?\s*(?:or|/)\s*", gap, re.I))
            if not is_or and not re.fullmatch(r"\s*,\s*", gap):
                flush()
                run, has_or = [], False
            has_or = has_or or is_or
        run.append(name)
    if run:
        flush()
    return groups


@lru_cache(maxsize=512)
def requirements(description):
    result = []
    candidates = {name: aliases for name, aliases in SKILLS.items() if any(mentions(description, a) for a in aliases)}
    for line, kind in requirement_lines(description):
        skills = [name for name, aliases in candidates.items() if any(mentions(line, a) for a in aliases)]
        if not skills:
            continue
        groups = alternative_groups(line, skills)
        for group in groups:
            result.append({"skills": group, "kind": kind, "quote": line[:1200]})
    unique = {}
    for item in result:
        key = (tuple(item["skills"]), item["kind"])
        unique.setdefault(key, item)
    return list(unique.values())


def match(job, profile: Profile):
    evidence = {canonical(s.skill): s.evidence for s in profile.skills}
    checks = []
    extracted = job.get("requirements") if job.get("requirements_version") == REQUIREMENTS_VERSION else None
    for requirement in extracted if extracted is not None else requirements(job["description"]):
        supported = [s for s in requirement["skills"] if s in evidence]
        checks.append({**requirement, "status": "supported" if supported else "no_evidence",
                       "evidence": [{"skill": s, "text": evidence[s] or "Self-reported skill; add a project or coursework example."} for s in supported]})
    weighted = [(c, 2 if c["kind"] == "required" else 1) for c in checks if c["kind"] != "mentioned"]
    total = sum(w for _, w in weighted)
    score = round(100 * sum(w for c, w in weighted if c["status"] == "supported") / total) if total and evidence else None
    if not job["description"].strip():
        assessment = "requirements_unavailable"
    elif not total:
        assessment = "unrecognized_requirements"
    elif not evidence:
        assessment = "needs_profile"
    else:
        assessment = "assessed"
    eligibility = qualification_checks(job["description"], profile, skill_quotes=[c["quote"] for c in checks])
    location = "unknown"
    if profile.location and job.get("location"):
        location = "matches" if preferred_matches(profile.location, job) else "review"
    gaps = [" or ".join(c["skills"]) for c in checks if c["kind"] == "required" and c["status"] == "no_evidence"]
    next_steps = [f"Add a real project, coursework, or work example for {gap}, if you have one." for gap in gaps[:3]]
    next_steps.extend(f"Confirm {c['criterion'].lower()}: {c['explanation']}" for c in eligibility if c["status"] != "matches")
    summary = {"matched": sum(c["status"] == "matches" for c in eligibility),
               "conflicts": sum(c["status"] == "conflict" for c in eligibility),
               "unclear": sum(c["status"] == "unknown" for c in eligibility), "required_skill_gaps": len(gaps)}
    breakdown = {
        "required": {"matched": sum(c["status"] == "supported" for c in checks if c["kind"] == "required"), "total": sum(c["kind"] == "required" for c in checks)},
        "preferred": {"matched": sum(c["status"] == "supported" for c in checks if c["kind"] == "preferred"), "total": sum(c["kind"] == "preferred" for c in checks)},
        "earned_weight": sum(w for c, w in weighted if c["status"] == "supported"),
        "total_weight": total,
        "self_reported": sum(c["status"] == "supported" and not any(evidence.get(s) for s in c["skills"]) for c in checks if c["kind"] != "mentioned"),
        "missing_required": gaps,
    }
    return {"breakdown": breakdown, "score": score, "assessment": assessment, "comparable": bool(total), "checks": checks, "eligibility": eligibility, "location_fit": location,
            "qualification_summary": summary, "next_steps": next_steps[:5],
            "has_conflict": any(c["status"] == "conflict" for c in eligibility),
            "note": "Rule-based evidence coverage, not hiring probability. Review the full description for unrecognized requirements."}
