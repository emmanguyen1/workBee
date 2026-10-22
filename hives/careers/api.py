from pathlib import Path
from collections import Counter
import asyncio
from typing import Literal

from fastapi import APIRouter, HTTPException, Response, Request
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from hives.careers import store
from hives.careers.matching import Profile, match
from hives.careers.taxonomy import FIELDS, career_field, role_type, location_matches
from hives.careers.resume import import_resume, MAX_UPLOAD, ResumeError
from hives.careers.simplify import deduplicate
from hives.careers.branding import company_brand

router = APIRouter()
resume_slots = asyncio.Semaphore(2)
PRIVATE_HEADERS = {"Cache-Control": "no-store"}


class Search(BaseModel):
    profile: Profile = Field(default_factory=Profile)
    query: str = Field(default="", max_length=200)
    role_type: str = Field(default="early_career", pattern="^(early_career|internship|new_grad|entry_level|apprenticeship|other|all)$")
    career_field: str = Field(default="all", pattern="^(all|" + "|".join(FIELDS) + ")$")
    location: str = Field(default="", max_length=150)
    workplace: str = Field(default="all", pattern="^(all|remote|hybrid|onsite|unspecified)$")
    company: str = Field(default="", max_length=100)
    sort: str = Field(default="fit", pattern="^(fit|newest)$")
    comparable_only: bool = False
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=30, ge=1, le=100)


@router.get("/hivepath", response_class=HTMLResponse)
@router.get("/careers", response_class=HTMLResponse)
async def careers():
    return Path(__file__).with_name("page.html").read_text()


@router.get("/careers/assets/{asset}")
async def careers_asset(asset: str):
    if asset not in {"styles.css", "app.mjs", "logic.mjs"}:
        raise HTTPException(404, "Asset not found")
    media = "text/css" if asset.endswith(".css") else "text/javascript"
    return FileResponse(Path(__file__).with_name("static") / asset, media_type=media, headers={"Cache-Control": "no-cache"})


@router.post("/api/careers/resume")
async def resume(request: Request, response: Response, format: Literal["pdf", "docx", "txt"]):
    response.headers.update(PRIVATE_HEADERS)
    async with resume_slots:
        chunks, size = [], 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > MAX_UPLOAD:
                raise HTTPException(413, "Resume must be 4 MB or smaller.", headers=PRIVATE_HEADERS)
            chunks.append(chunk)
        try:
            return await run_in_threadpool(import_resume, b"".join(chunks), format)
        except ResumeError as exc:
            raise HTTPException(422, str(exc), headers=PRIVATE_HEADERS) from exc


class ManualMatch(BaseModel):
    profile: Profile
    description: str = Field(min_length=20, max_length=100000)
    location: str = Field(default="", max_length=500)


@router.post("/api/careers/match")
async def manual_match(request: ManualMatch, response: Response):
    response.headers.update(PRIVATE_HEADERS)
    return await run_in_threadpool(match, {"description": request.description, "location": request.location}, request.profile)


@router.post("/api/careers/search")
async def search(request: Search, response: Response):
    response.headers["Cache-Control"] = "no-store"
    try:
        data = await store.catalog()
    except Exception as exc:
        raise HTTPException(503, "Careers database unavailable. Start Postgres and the careers collector.") from exc
    return await run_in_threadpool(search_catalog, data, request)


def search_catalog(data, request):
    jobs, catalog = [], []
    for job in deduplicate(data["jobs"]):
        # Reclassify legacy snapshots without requiring a database migration.
        job = {**job, "career_field": job.get("career_field", "other") if job.get("source") == "simplify" else career_field(job["title"], job.get("department", "")),
               "role_type": "internship" if job["role_type"] == "internship" else role_type(job["title"]),
               "locations": job.get("locations") or [job["location"]],
               "workplace": job.get("workplace", "unspecified").lower()}
        catalog.append(job)
    fields = Counter(j["career_field"] for j in catalog)
    types = Counter(j["role_type"] for j in catalog)
    facets = {"fields": [{"value": k, "label": v, "count": fields[k]} for k, v in FIELDS.items()],
              "companies": sorted({j["company"] for j in catalog}),
              "locations": sorted({v for j in catalog for v in j["locations"] if v}),
              "role_types": dict(types)}
    for job in catalog:
        if request.role_type == "early_career" and job["role_type"] == "other":
            continue
        if request.role_type not in {"all", "early_career"} and job["role_type"] != request.role_type:
            continue
        if request.career_field != "all" and job["career_field"] != request.career_field:
            continue
        if request.company and job["company"] != request.company:
            continue
        if request.workplace != "all" and job["workplace"] != request.workplace:
            continue
        if not location_matches(request.location, [*job["locations"], *job.get("countries", [])]):
            continue
        text = " ".join([job["title"], job["company"], *job["locations"], job["description"]]).casefold()
        if not all(word in text for word in request.query.casefold().split()):
            continue
        if request.sort == "newest" and not request.comparable_only:
            jobs.append(job)
            continue
        result = match(job, request.profile)
        if request.comparable_only and not result["comparable"]:
            continue
        jobs.append({**job, "match": result})
    if request.sort == "newest":
        jobs.sort(key=lambda j: j.get("first_seen", ""), reverse=True)
    else:
        jobs.sort(key=lambda job: (job["match"]["has_conflict"], job["match"]["score"] is None, -(job["match"]["score"] or 0), -job["match"]["qualification_summary"]["matched"]))
    page = jobs[request.offset:request.offset + request.limit]
    if request.sort == "newest" and not request.comparable_only:
        page = [{**j, "match": match(j, request.profile)} for j in page]
    page = [{**job, **company_brand(job["company"])} for job in page]
    return {"jobs": page, "total": len(jobs), "boards": data["boards"], "facets": facets,
            "profile_skills": [s.skill for s in request.profile.skills],
            "catalog_total": len(catalog), "early_career_total": len(catalog) - types["other"]}
