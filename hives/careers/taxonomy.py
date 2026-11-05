"""Explicit title signals; ambiguous seniority and geography remain unspecified."""
import re
from functools import lru_cache

ROLE_TYPES = {"early_career", "internship", "new_grad", "entry_level", "apprenticeship", "other", "all"}
FIELDS = {
    "healthcare":"Healthcare & clinical care", "business":"Business & consulting",
    "education":"Education & training", "environment":"Environment & sustainability",
    "real_estate":"Real estate & construction", "hospitality":"Hospitality & tourism",
    "public_service":"Public service & community",
    "software": "Software & IT", "data": "Data & analytics", "design": "Design & creative",
    "product": "Product & programs", "marketing": "Marketing & communications",
    "sales": "Sales & business development", "finance": "Finance & accounting",
    "people": "HR & recruiting", "legal": "Legal & policy", "operations": "Operations & supply chain",
    "engineering": "Hardware & engineering", "science": "Life & physical sciences",
    "support": "Customer support & success", "other": "Other / unclassified",
}
FIELD_RULES = [
    ("healthcare",r"\bnurs\w*|\bclinical\b|\bpatient\b|physician|pharmacist|medical assistant|healthcare|health care|therapist|mental health|care coordinat|care manager|care navigation"),
    ("education",r"\bteacher\b|\bteaching\b|curriculum|instructional|academic advisor|education specialist|learning and development|training specialist"),
    ("environment",r"sustainab|environmental|ecolog|conservation|renewable|climate (?:policy|scientist|analyst)"),
    ("real_estate",r"real estate|construction|property manag|architectural|urban planning|building inspector"),
    ("hospitality",r"hospitality|hotel|restaurant|culinary|tourism|guest services|event coordinator"),
    ("public_service",r"social worker|community (?:outreach|organizer|engagement)|public service|nonprofit|fundraising|grant writer"),
    ("people", r"recruit|human resources|\bhr\b|people (?:operations|partner|team)"),
    ("legal", r"legal|counsel|compliance|public policy|government affairs"),
    ("marketing", r"marketing|communications|public relations|copywrit|social media|content (?:creat|strateg|design)|brand"),
    ("finance", r"financ|accountant|accounting|audit|treasury|investment|actuar|tax analyst"),
    ("sales", r"\bsales\b|business development|account executive|partnerships"),
    ("support", r"customer (?:support|success|service)|technical support|client service"),
    ("engineering", r"mechanical|electrical|hardware|manufactur|aerospace|avionics|civil engineer|robotics|firmware|test engineer"),
    ("design", r"\bdesign(?:er)?\b|\bux\b|\bui\b|creative|animation|illustrat"),
    ("business",r"business (?:analyst|operations|strategy|management)|\bconsultant\b|corporate strategy|chief of staff|management trainee|strategy (?:analyst|associate)|strategic operations"),
    ("data", r"\bdata\b|analytics|business intelligence|machine learning|\bai\b|quantitative"),
    ("software", r"software|developer|backend|frontend|full.?stack|devops|security engineer|\bsre\b|\bit\b|cybersecurity|infrastructure"),
    ("science", r"scientist|research|clinical|biology|biolog|chemist|laboratory|healthcare|medical"),
    ("operations", r"operations|supply chain|logistics|procurement|purchasing|warehouse|facilities|quality assurance"),
    ("product", r"product|program|project manag"),
    ("engineering", r"\bengineer(?:ing)?\b"),
]


@lru_cache(maxsize=8192)
def career_field(title, department=""):
    # Prefer title over an employer's broad department label.
    for text in (title, department):
        for key, pattern in FIELD_RULES:
            if re.search(pattern, text, re.I):
                return key
    return "other"


def location_matches(query, locations):
    """Match words and common explicit aliases, never infer a remote job is worldwide."""
    def normalize(value):
        value = value.casefold()
        for pattern, replacement in [
            (r"\b(?:united states(?: of america)?|u\.?s\.?a\.?|u\.s\.|us)\b", "united states"),
            (r"\b(?:united kingdom|u\.?k\.?)\b", "united kingdom"),
            (r"\bnyc\b", "new york"),
        ]:
            value = re.sub(pattern, replacement, value)
        return re.sub(r"[^\w]+", " ", value).strip()
    tokens = normalize(query).split()
    if not tokens:
        return True
    return any(all(re.search(r"\b" + re.escape(word) + r"\b", normalize(location)) for word in tokens) for location in locations)


@lru_cache(maxsize=8192)
def role_type(title, employment=""):
    if re.search(r"\b(intern(ship)?|co[ -]?op)\b", f"{title} {employment}", re.I):
        return "internship"
    if re.search(r"\bapprentic\w*\b", title, re.I):
        return "apprenticeship"
    if re.search(r"\b(new[ -]?grad(uate)?|early[ -]?career|university graduate)\b|\bgraduate (?:engineer|analyst|trainee|program(?:me)?|associate|consultant)\b", title, re.I):
        return "new_grad"
    if re.search(r"\b(entry[ -]?level|junior|jr\.?|trainee)\b", title, re.I):
        return "entry_level"
    return "other"


@lru_cache(maxsize=8192)
def opportunity_types(title, stage):
    kinds = ["internship"] if stage == "internship" else ["job"]
    if re.search(r"\bresearch(?:er)?\b|\bpost[ -]?doc\w*\b|\bfellow(?:ship|s)?\b|\bREU\b|\b(?:young investigator|predoctoral|postbaccalaureate)\b", title, re.I):
        kinds.append("research")
    return kinds


def talent_pool(title):
    return bool(re.search(r"talent (?:pool|network|community)|general (?:interest|application)|expression of interest|interested in (?:an? )?internship|don.t see what you.re looking for", title, re.I))
