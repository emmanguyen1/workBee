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
from hives.careers.taxonomy import FIELDS, career_field, role_type, location_matches, opportunity_types, talent_pool
from hives.careers.resume import import_resume, MAX_UPLOAD, ResumeError
from hives.careers.simplify import deduplicate
from hives.careers.branding import company_brand
from hives.careers.availability import availability, verify

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
    opportunity_type: Literal["all", "internship", "job", "research"] = "all"
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
        if talent_pool(job["title"]):
            continue
        # Reclassify legacy snapshots without requiring a database migration.
        job = {**job, "career_field": job.get("career_field", "other") if job.get("source") == "simplify" else career_field(job["title"], job.get("department", "")),
               "role_type": "internship" if job["role_type"] == "internship" else role_type(job["title"]),
               "locations": job.get("locations") or [job["location"]],
               "workplace": job.get("workplace", "unspecified").lower()}
        catalog.append(job)
    rank_by_fit = request.sort == "fit" and bool(request.profile.model_dump(exclude_defaults=True))
    types = Counter(j["role_type"] for j in catalog)
    fields, categories = Counter(), Counter()
    for job in catalog:
        job["opportunity_types"] = opportunity_types(job["title"], job["role_type"])
        if request.role_type == "early_career" and job["role_type"] == "other":
            continue
        if request.role_type not in {"all", "early_career"} and job["role_type"] != request.role_type:
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
        result = match(job, request.profile) if request.comparable_only else None
        if request.comparable_only and not result["comparable"]:
            continue
        # Each facet respects every active filter except its own selection.
        if request.career_field == "all" or job["career_field"] == request.career_field:
            categories.update(job["opportunity_types"])
            categories["all"] += 1
        if request.opportunity_type != "all" and request.opportunity_type not in job["opportunity_types"]:
            continue
        fields[job["career_field"]] += 1
        if request.career_field != "all" and job["career_field"] != request.career_field:
            continue
        if rank_by_fit and result is None:
            result = match(job, request.profile)
        jobs.append({**job, "match": result} if result else job)
    facets = {"fields": [{"value": k, "label": v, "count": fields[k]} for k, v in FIELDS.items()],
              "field_total": sum(fields.values()),
              "opportunity_types": dict(categories),
              "companies": sorted({j["company"] for j in catalog}),
              "locations": sorted({v for j in catalog for v in j["locations"] if v}),
              "role_types": dict(types)}
    if not rank_by_fit:
        jobs.sort(key=lambda j: j.get("first_seen", ""), reverse=True)
    else:
        jobs.sort(key=lambda job: (job["match"]["has_conflict"], job["match"]["score"] is None, -(job["match"]["score"] or 0), -job["match"]["qualification_summary"]["matched"]))
    page = jobs[request.offset:request.offset + request.limit]
    if not rank_by_fit and not request.comparable_only:
        page = [{**j, "match": match(j, request.profile)} for j in page]
    boards = {b["key"]: b for b in data["boards"]}
    page = [{**job, **company_brand(job["company"]), "availability": availability(job, boards.get(f"{job.get('source')}:{job.get('board')}"))} for job in page]
    return {"jobs": page, "total": len(jobs), "boards": data["boards"], "facets": facets,
            "profile_skills": [s.skill for s in request.profile.skills],
            "effective_sort": "fit" if rank_by_fit else "newest", "catalog_total": len(catalog), "catalog_field_total": len({j["career_field"] for j in catalog}), "early_career_total": len(catalog) - types["other"]}


class VerifyOpportunity(BaseModel):
    job_id: str = Field(min_length=1, max_length=500)


@router.post("/api/careers/verify")
async def verify_opportunity(request: VerifyOpportunity, response: Response):
    response.headers.update(PRIVATE_HEADERS)
    try:
        job = await store.get_job(request.job_id)
    except Exception as exc:
        raise HTTPException(503, "Careers database unavailable", headers=PRIVATE_HEADERS) from exc
    if not job:
        raise HTTPException(404, "Opportunity not found", headers=PRIVATE_HEADERS)
    result = await verify(job)
    if result.get('checked_at') and result['state'] != 'unsupported':
        try:
            await store.save_verification(request.job_id, result)
        except Exception as exc:
            raise HTTPException(503, "Source checked, but the result could not be saved. Please try again.", headers=PRIVATE_HEADERS) from exc
    return result
