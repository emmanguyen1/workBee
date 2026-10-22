"""Bounded public employer feeds. No user-provided URLs or credentials."""
import re
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

import httpx
import yaml

from hives.careers.taxonomy import career_field, role_type
from hives.careers.matching import requirements


class TextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1
        if tag in {"p", "li", "br", "h1", "h2", "h3", "h4", "div"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)
        if tag in {"p", "li", "h1", "h2", "h3", "h4", "div"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def plain(value):
    parser = TextParser()
    parser.feed(unescape(value or ""))
    return "\n".join(line.strip() for line in "".join(parser.parts).splitlines() if line.strip())


def safe_url(value):
    parsed = urlparse(value or "")
    return value if parsed.scheme == "https" and parsed.hostname and not parsed.username else ""


def employers():
    path = Path(__file__).with_name("employers.yml")
    return yaml.safe_load(path.read_text())["employers"]


def normalize(employer, raw):
    source = employer["source"]
    countries = []
    if source == "greenhouse":
        description = plain(raw.get("content", ""))
        location = raw.get("location", {}).get("name", "")
        url = raw.get("absolute_url")
        published = None  # updated_at is not a publication date
        employment = ""
        workplace = "unspecified"
        locations = [location]
        department = ", ".join(d.get("name", "") for d in raw.get("departments", []))
    elif source == "lever":
        sections = [raw.get("description", "")]
        sections.extend(f"<h3>{s.get('text', '')}</h3>{s.get('content', '')}" for s in raw.get("lists", []))
        sections.append(raw.get("additional", ""))
        description = plain("\n".join(sections))
        categories = raw.get("categories", {})
        location = categories.get("location", "")
        url = raw.get("applyUrl") or raw.get("hostedUrl")
        published = None
        employment = categories.get("commitment", "")
        workplace = raw.get("workplaceType", "unspecified")
        locations = categories.get("allLocations") or [location]
        department = categories.get("department") or categories.get("team", "")
    else:
        description = raw.get("descriptionPlain") or plain(raw.get("descriptionHtml", ""))
        location = raw.get("location", "")
        url = raw.get("applyUrl") or raw.get("jobUrl")
        published = raw.get("publishedAt")
        employment = raw.get("employmentType", "")
        workplace = raw.get("workplaceType", "unspecified")
        locations = [location, *(r.get("location", "") for r in raw.get("secondaryLocations", []))]
        department = raw.get("department", "")
        addresses = [raw.get("address") or {}, *((r.get("address") or {}) for r in raw.get("secondaryLocations", []))]
        countries = list(dict.fromkeys(a.get("postalAddress", {}).get("addressCountry") for a in addresses if a.get("postalAddress", {}).get("addressCountry")))
    title = raw["title"] if source != "lever" else raw["text"]
    locations = list(dict.fromkeys(v for v in locations if isinstance(v, str) and v))
    workplace = str(workplace or "unspecified").lower().replace("-", "")
    workplace = {"onsite": "onsite", "remote": "remote", "hybrid": "hybrid"}.get(workplace, "unspecified")
    if workplace == "unspecified":
        if re.search(r"\bhybrid\b", location, re.I):
            workplace = "hybrid"
        elif re.search(r"\bremote\b", location, re.I):
            workplace = "remote"
    return {
        "id": f"{source}:{employer['board']}:{raw['id']}",
        "source": source, "board": employer["board"], "company": employer["name"],
        "title": title, "location": location, "workplace": workplace,
        "locations": locations, "department": department,
        "countries": countries,
        "career_field": career_field(title, department),
        "role_type": role_type(title, employment), "description": description[:100000],
        "requirements": requirements(description[:100000]),
        "requirements_version": 2,
        "apply_url": safe_url(url), "published_at": published,
        "source_updated_at": raw.get("updated_at"),
    }


async def fetch_board(client: httpx.AsyncClient, employer):
    source, board = employer["source"], employer["board"]
    if not re.fullmatch(r"[A-Za-z0-9_-]+", board):
        raise ValueError("Invalid employer board identifier")
    if source == "simplify":
        from hives.careers.simplify import DATA_URL, normalize_list
        response = await client.get(DATA_URL)
        response.raise_for_status()
        return normalize_list(response.json())
    if source == "greenhouse":
        response = await client.get(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs", params={"content": "true"})
        response.raise_for_status()
        rows = response.json()["jobs"]
    elif source == "ashby":
        response = await client.get(f"https://api.ashbyhq.com/posting-api/job-board/{board}")
        response.raise_for_status()
        rows = response.json()["jobs"]
        rows = [row for row in rows if row.get("isListed", True)]
    elif source == "lever":
        rows = []
        for page in range(30):
            response = await client.get(f"https://api.lever.co/v0/postings/{board}", params={"mode": "json", "skip": page * 100, "limit": 100})
            response.raise_for_status()
            batch = response.json()
            if not isinstance(batch, list):
                raise ValueError("Unexpected Lever response")
            rows.extend(batch)
            if len(batch) < 100:
                break
        else:
            raise ValueError("Employer feed exceeded pagination limit")
    else:
        raise ValueError("Unsupported employer source")
    if not isinstance(rows, list):
        raise ValueError("Unexpected employer response")
    # Reject the entire snapshot on malformed data; never close jobs on a partial feed.
    return [normalize(employer, row) for row in rows]
