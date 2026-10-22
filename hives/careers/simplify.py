"""Community-list discovery with explicit attribution and no invented qualifications."""
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs, parse_qsl, urlencode

from hives.careers.feeds import safe_url
from hives.careers.taxonomy import career_field

SOURCE_URL = "https://github.com/SimplifyJobs/Summer2027-Internships"
DATA_URL = "https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/dev/.github/scripts/listings.json"


def timestamp(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat() if isinstance(value, (int, float)) else None


def normalize_list(rows):
    if not isinstance(rows, list) or not rows:
        raise ValueError("Unexpected Simplify listing format")
    jobs = []
    for row in rows:
        if not isinstance(row, dict) or not all(key in row for key in ("id", "active", "is_visible", "terms", "title", "company_name", "url", "locations")):
            raise ValueError("Incomplete Simplify snapshot")
        if row["active"] is not True or row["is_visible"] is not True or "Summer 2027" not in row["terms"]:
            continue
        locations = row["locations"]
        if not isinstance(locations, list) or not all(isinstance(v, str) for v in locations):
            raise ValueError("Invalid Simplify locations")
        url = safe_url(row["url"])
        if not url:
            continue
        category = row.get("category", "")
        field = {"Software": "software", "Software Engineering": "software", "Hardware": "engineering", "Hardware Engineering": "engineering", "AI/ML/Data": "data", "Data Science, AI & Machine Learning": "data", "Quant": "finance", "Quantitative Finance": "finance", "Product": "product", "Product Management": "product"}.get(category, career_field(row["title"]))
        jobs.append({"id": f"simplify:summer2027:{row['id']}", "source": "simplify", "board": "summer2027",
                     "company": row["company_name"], "title": row["title"], "location": locations[0] if locations else "",
                     "locations": locations, "countries": [], "workplace": "remote" if locations and all(v.lower() == "remote" for v in locations) else "unspecified",
                     "department": category, "career_field": field, "role_type": "internship", "description": "",
                     "requirements": [], "requirements_version": 2, "requirements_available": False,
                     "apply_url": url, "published_at": timestamp(row.get("date_posted")), "source_updated_at": timestamp(row.get("date_updated")),
                     "source_url": SOURCE_URL, "attribution": "Pitt CSC & Simplify · Summer 2027 internship list",
                     "listing_status": "community_listed", "terms": ["Summer 2027"]})
    return jobs


def application_key(job):
    url = urlparse(job.get("apply_url", ""))
    host, path = (url.hostname or "").lower(), url.path.rstrip("/")
    parts = path.strip("/").split("/")
    if host in {"boards.greenhouse.io", "job-boards.greenhouse.io"}:
        if len(parts) >= 3 and parts[-2] == "jobs":
            return "greenhouse:" + parts[0].lower() + ":" + parts[-1]
        query = parse_qs(url.query)
        if query.get("for") and query.get("token"):
            return "greenhouse:" + query["for"][0].lower() + ":" + query["token"][0]
    if host in {"jobs.lever.co", "jobs.eu.lever.co", "jobs.ashbyhq.com"} and len(parts) >= 2:
        return host + ":" + parts[0].lower() + ":" + parts[1]
    meaningful = [(k, v) for k, v in parse_qsl(url.query) if not k.lower().startswith("utm_") and k.lower() not in {"gh_src", "source", "ref"}]
    return (host + path + "?" + urlencode(sorted(meaningful)), job["company"].casefold(), job["title"].casefold()) if host else (job["id"],)


def deduplicate(jobs):
    selected = {}
    for job in jobs:
        key = application_key(job)
        previous = selected.get(key)
        if previous is None:
            selected[key] = job
            continue
        primary, secondary = (job, previous) if previous.get("source") == "simplify" and job.get("source") != "simplify" else (previous, job)
        references = [*primary.get("source_references", []), *secondary.get("source_references", [])]
        if secondary.get("source_url"):
            references.append({"url": secondary["source_url"], "label": secondary.get("attribution", secondary["source"])})
        selected[key] = {**primary, "alternate_ids": list(dict.fromkeys([*primary.get("alternate_ids", []), secondary["id"]])),
                         "source_references": [dict(values) for values in dict.fromkeys(tuple(r.items()) for r in references)]}
    return list(selected.values())
