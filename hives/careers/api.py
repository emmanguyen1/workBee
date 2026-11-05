from pathlib import Path
from collections import Counter
import asyncio
from typing import Literal

from fastapi import APIRouter, HTTPException, Response, Request
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from hives.careers.deadlines import deadline_info, recency
from hives.careers import store
from hives.careers.preferences import MultiPreferences
from hives.careers.sectors import technical_role, sector_tags, SECTORS
from hives.careers.matching import Profile, match
from hives.careers.taxonomy import FIELDS, career_field, role_type, location_matches, opportunity_types, talent_pool
from hives.careers.resume import import_resume, MAX_UPLOAD, ResumeError
from hives.careers.simplify import deduplicate
from hives.careers.geography import geography, region_matches, COUNTRIES, REGIONS
from hives.careers.branding import company_brand, DOMAINS
from hives.careers.programs import program_catalog, student_years, program_jobs
from hives.careers.availability import availability, verify

router = APIRouter()
resume_slots = asyncio.Semaphore(2)
PRIVATE_HEADERS = {"Cache-Control": "no-store"}


class Search(MultiPreferences):
    profile: Profile = Field(default_factory=Profile)
    query: str = Field(default="", max_length=200)
    role_type: str = Field(default="early_career", pattern="^(early_career|internship|new_grad|entry_level|apprenticeship|other|all)$")
    career_field: str = Field(default="all", pattern="^(all|" + "|".join(FIELDS) + ")$")
    location: str = Field(default="", max_length=150)  # Legacy API clients only
    country: str = Field(default="", max_length=10)
    region: str = Field(default="", max_length=10)
    workplace: str = Field(default="all", pattern="^(all|remote|hybrid|onsite|unspecified)$")
    company: str = Field(default="", max_length=100)
    sort: str = Field(default="fit", pattern="^(fit|relevance|newest|deadline|company)$")
    student_year: Literal["all", "incoming", "first", "second"] = "all"
    technical_only: bool = False
    current_only: bool = False
    include_programs: bool = False
    program_status: Literal["all", "application_window", "watch"] = "all"
    comparable_only: bool = False
    opportunity_type: Literal["all", "internship", "job", "research", "lab", "program"] = "all"
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=30, ge=1, le=100)


@router.get("/", response_class=HTMLResponse)
@router.get("/hivepath", response_class=HTMLResponse)
@router.get("/careers", response_class=HTMLResponse)
async def careers():
    return Path(__file__).with_name("page.html").read_text()


@router.get("/careers/assets/{asset}")
async def careers_asset(asset: str):
    if asset not in {"styles.css", "app.mjs", "logic.mjs", "workbee-logo.png"}:
        raise HTTPException(404, "Asset not found")
    media = "image/png" if asset.endswith(".png") else "text/css" if asset.endswith(".css") else "text/javascript"
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
    board_status = {b["key"]:b for b in data["boards"]}
    source_jobs = [*data["jobs"], *(program_jobs() if not request.current_only and (request.include_programs or request.opportunity_type == "program") else [])]
    for job in deduplicate(source_jobs):
        job={**job,"deadline_info":deadline_info(job)}
        if request.current_only and job["deadline_info"]["expired"]:continue
        if request.current_only:
            status = availability(job, board_status.get(f"{job.get('source')}:{job.get('board')}"), supported_boards=board_status)
            if job.get("source") not in {"greenhouse", "lever", "ashby"} or status["state"] != "listed":
                continue
        if talent_pool(job["title"]):
            continue
        if request.technical_only:
            technical,reason=technical_role(job)
            if not technical:continue
            job={**job,"technical_evidence":reason}
        job={**job,"sectors":sector_tags(job)}
        # Reclassify legacy snapshots without requiring a database migration.
        job = {**job, "career_field": job.get("career_field", "other") if job.get("source") in {"simplify", "program"} else career_field(job["title"], job.get("department", "")),
               "role_type": job["role_type"] if job.get("is_program") else "internship" if job["role_type"] == "internship" else role_type(job["title"]),
               "locations": job.get("locations") or [job["location"]],
               "workplace": job.get("workplace", "unspecified").lower()}
        job["student_audience"] = job["student_audience"] if job.get("is_program") else student_years(job)
        job["geography"] = geography(job)
        catalog.append(job)
    selected_fields=request.career_fields or ([] if request.career_field=='all' else [request.career_field])
    selected_types=request.opportunity_types or ([] if request.opportunity_type=='all' else [request.opportunity_type])
    selected_roles=request.role_types or ([] if request.role_type=='all' else [request.role_type])
    selected_companies=request.companies or ([request.company] if request.company else [])
    selected_countries=request.countries or ([request.country] if request.country else [])
    selected_regions=request.regions or ([request.region] if request.region else [])
    selected_workplaces=request.workplaces or ([] if request.workplace=='all' else [request.workplace])
    rank_by_fit = request.sort in {"fit","relevance"} and bool(request.profile.model_dump(exclude_defaults=True))
    types = Counter(j["role_type"] for j in catalog)
    fields, categories, sectors = Counter(), Counter(), Counter()
    for job in catalog:
        job["opportunity_types"] = job["opportunity_types"] if job.get("is_program") else list(opportunity_types(job["title"], job["role_type"]))
        if request.current_only and not job.get("is_program") and job["student_audience"]["years"] and "program" not in job["opportunity_types"]:
            job["opportunity_types"].append("program")
        if job.get("is_program") and request.program_status != "all":
            if (job["status"] == "application_window") != (request.program_status == "application_window"):
                continue
        if selected_roles and not any(job['role_type']==role or (role=='early_career' and (job['role_type']!='other' or job.get('is_program'))) for role in selected_roles):
            continue
        if request.student_year != "all" and {"incoming":0,"first":1,"second":2}[request.student_year] not in job["student_audience"]["years"]:
            continue
        if selected_companies and job['company'] not in selected_companies: continue
        if selected_workplaces and job['workplace'] not in selected_workplaces: continue
        if selected_countries and not any(region_matches(job,country=c) for c in selected_countries): continue
        if selected_regions and not any(region_matches(job,region=r) for r in selected_regions): continue
        if not location_matches(request.location, [*job["locations"], *job.get("countries", [])]):
            continue
        text = " ".join([job["title"], job["company"], *job["locations"], job["description"], job.get("search_text", "")]).casefold()
        if not all(word in text for word in request.query.casefold().split()):
            continue
        result = match(job, request.profile) if request.comparable_only else None
        if request.comparable_only and not result["comparable"]:
            continue
        # Sector counts exclude only the sector selections.
        if (not selected_fields or job["career_field"] in selected_fields) and (not selected_types or set(selected_types).intersection(job["opportunity_types"])):
            sectors.update(job["sectors"])
        if request.sectors and not set(request.sectors).intersection(job["sectors"]):continue
        # Each facet respects every active filter except its own selection.
        if not selected_fields or job["career_field"] in selected_fields:
            categories.update(job["opportunity_types"])
            categories["all"] += 1
        if selected_types and not set(selected_types).intersection(job["opportunity_types"]):
            continue
        fields[job["career_field"]] += 1
        if selected_fields and job["career_field"] not in selected_fields:
            continue
        if rank_by_fit and result is None:
            result = match(job, request.profile)
        jobs.append({**job, "match": result} if result else job)
    facets = {"fields": [{"value": k, "label": v, "count": fields[k]} for k, v in FIELDS.items()],
              "field_total": sum(fields.values()),
              "sectors": [{"value":key,"label":label,"count":sectors[key]} for key,label in sorted(SECTORS.items(),key=lambda item:item[1].casefold())],
              "opportunity_types": dict(categories),
              "companies": sorted({j["company"] for j in catalog}),
              "countries": [{"value":code,"label":COUNTRIES.get(code, code)} for code in sorted({c for j in catalog for c in j["geography"]["countries"]}, key=lambda c:COUNTRIES.get(c, c))],
              "regions": [{"value":code,"label":REGIONS[code],"country":code.split("-")[0]} for code in sorted({r for j in catalog for r in j["geography"]["regions"]}, key=lambda r:REGIONS[r])],
              "role_types": dict(types)}
    effective_sort='relevance' if rank_by_fit else request.sort if request.sort in {'deadline','company'} else 'newest'
    if effective_sort=='deadline':jobs.sort(key=lambda j:(not bool(j['deadline_info']['date']),j['deadline_info']['date'] or '9999',-recency(j)))
    elif effective_sort=='company':jobs.sort(key=lambda j:(j['company'].casefold(),j['title'].casefold()))
    elif not rank_by_fit:
        jobs.sort(key=recency, reverse=True)
    else:
        jobs.sort(key=lambda job: (job["match"]["has_conflict"], job["match"]["score"] is None, -(job["match"]["score"] or 0), -job["match"]["qualification_summary"]["matched"], -job["match"]["breakdown"]["with_examples"]))
    page = jobs[request.offset:request.offset + request.limit]
    if not rank_by_fit and not request.comparable_only:
        page = [{**j, "match": match(j, request.profile)} for j in page]
    boards = {b["key"]: b for b in data["boards"]}
    page = [{**job, **company_brand(job["company"]), "availability": job["availability"] if job.get("is_program") else availability(job, boards.get(f"{job.get('source')}:{job.get('board')}"))} for job in page]
    return {"jobs": page, "total": len(jobs), "boards": data["boards"], "facets": facets,
            "profile_skills": [s.skill for s in request.profile.skills],
            "listing_total": sum(not j.get("is_program",False) for j in jobs), "program_total": sum(bool(j.get("is_program")) for j in jobs),
            "effective_sort": effective_sort, "catalog_total": len(catalog), "catalog_field_total": len({j["career_field"] for j in catalog}), "early_career_total": sum(j["role_type"] != "other" or bool(j.get("is_program")) for j in catalog)}


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


@router.get('/careers/logos/{asset}')
async def employer_logo(asset: str):
    if asset not in {domain+'.png' for domain in DOMAINS.values()}:
        raise HTTPException(404, 'Logo unavailable')
    path = Path(__file__).with_name('static') / 'logos' / asset
    if not path.is_file(): raise HTTPException(404, 'Logo unavailable')
    return FileResponse(path, media_type='image/png', headers={'Cache-Control':'public, max-age=86400'})


@router.get('/api/careers/programs')
async def early_college_programs(response: Response):
    response.headers.update(PRIVATE_HEADERS)
    return {'programs': program_catalog(), 'note': 'Program research is separate from live job counts. Confirm current eligibility and availability on the official page.'}


@router.get('/account',response_class=HTMLResponse)
async def account_page(response: Response):
    response.headers.update(PRIVATE_HEADERS)
    return Path(__file__).with_name('account.html').read_text()
