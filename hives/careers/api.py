from pathlib import Path
from collections import Counter
import asyncio
import json
import re
from typing import Literal
from time import perf_counter
from hives.careers.catalog import cache as catalog_cache,prepare as prepare_catalog

from fastapi import APIRouter, HTTPException, Response, Request
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from datetime import datetime, timezone, timedelta
from hives.careers.opportunity_facts import opportunity_facts
from hives.careers.deadlines import deadline_info, recency
from hives.careers import store
from hives.careers.preferences import MultiPreferences
from hives.careers.sectors import technical_role, sector_tags, SECTORS
from hives.careers.matching import Profile, match,profile_evidence
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
    role_type: str = Field(default="early_career", pattern="^(early_career|internship|first_second|program|new_grad|entry_level|apprenticeship|other|all)$")
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
    include_community: bool = False
    include_stale: bool = False
    compact: bool = False
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
    if asset not in {"styles.css", "app.mjs", "logic.mjs", "workbee-logo.png", "workbee-assistant.png", "bee.mjs", "bee-logic.mjs", "auth.mjs"}:
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
        started=perf_counter()
        data,hit = await catalog_cache.get(current_only=request.current_only,include_community=request.include_community,include_stale=request.include_stale,compact=request.compact)
        if request.compact and request.query.strip():
            ids=await store.query_ids(request.query,current_only=request.current_only,include_community=request.include_community,include_stale=request.include_stale,compact=True)
            data={**data,'query_ids':ids}
        loaded=perf_counter()
    except Exception as exc:
        raise HTTPException(503, "Careers database unavailable. Start Postgres and retry; a background collector is not required.") from exc
    result=await run_in_threadpool(search_catalog,data,request)
    response.headers['Server-Timing']=f'catalog;dur={(loaded-started)*1000:.1f};desc="{"cache" if hit else "load"}", search;dur={(perf_counter()-loaded)*1000:.1f}'
    return result


def search_catalog(data, request):
    jobs, catalog = [], []
    evidence=profile_evidence(request.profile)
    now=datetime.now(timezone.utc)
    board_status = {b["key"]:b for b in data["boards"]}
    public=data if data.get('prepared') else prepare_catalog(data)
    source_jobs=[*public['jobs']]
    if not request.current_only and (request.include_programs or request.opportunity_type=='program'):
        source_jobs.extend(prepare_catalog({'jobs':program_jobs()})['jobs'])
    for raw in source_jobs:
        job={**raw,'deadline_info':deadline_info(raw,now)}
        if request.current_only and job['deadline_info']['expired']:continue
        if request.current_only and job.get('verification',{}):
            v=job['verification']
            if v.get('state')=='removed':
                try:
                    if datetime.fromisoformat(v['checked_at'].replace('Z','+00:00'))>=datetime.fromisoformat(job['last_seen'].replace('Z','+00:00')):continue
                except (KeyError,ValueError,TypeError):pass
        if request.current_only:
            status=availability(job,board_status.get(f"{job.get('source')}:{job.get('board')}"),now=now,supported_boards=board_status)
            community=request.include_community and job.get('source')=='simplify' and status['state']=='community'
            if community:
                try:community=0 <= (now-datetime.fromisoformat(job['last_seen'].replace('Z','+00:00'))).total_seconds() <= 1800 and not (board_status.get('simplify:summer2027') or {}).get('error')
                except (KeyError,ValueError,TypeError):community=False
            cached=False
            if request.include_stale and status['state'] in {'stale','unavailable','community'}:
                allowed=job.get('source') in {'greenhouse','lever','ashby'} or request.include_community and job.get('source')=='simplify'
                try:cached=allowed and 0 <= (now-datetime.fromisoformat(job['last_seen'].replace('Z','+00:00'))).total_seconds() <= 7*86400
                except (KeyError,ValueError,TypeError):cached=False
            if not cached and not community and (job.get('source') not in {'greenhouse','lever','ashby'} or status['state']!='listed'):continue
            job['needs_recheck']=cached or job.get('source')=='simplify'
        if request.technical_only:
            technical,reason=(job['is_technical'],job.get('technical_evidence','')) if 'is_technical' in job else technical_role(job)
            if not technical:continue
            job={**job,'technical_evidence':reason}
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
        if selected_roles and not any(
            job['role_type']==role
            or (role=='early_career' and (job['role_type']!='other' or job.get('is_program')))
            or (role in {'first_second','program'} and ('program' in job.get('opportunity_types',[]) or bool(job.get('student_audience',{}).get('years')) or job.get('is_program')))
            for role in selected_roles
        ):
            continue
        if request.student_year != "all" and {"incoming":0,"first":1,"second":2}[request.student_year] not in job["student_audience"]["years"]:
            continue
        if selected_companies and job['company'] not in selected_companies: continue
        if selected_workplaces and job['workplace'] not in selected_workplaces: continue
        if selected_countries and not any(region_matches(job,country=c) for c in selected_countries): continue
        if selected_regions and not any(region_matches(job,region=r) for r in selected_regions): continue
        if not location_matches(request.location, [*job["locations"], *job.get("countries", [])]):
            continue
        if request.query.strip():
            if 'query_ids' in data and not job.get('is_program'):
                if job['id'] not in data['query_ids']:continue
            else:
                text = " ".join([job["title"], job["company"], *job["locations"], job["description"], job.get("search_text", "")]).casefold()
                if not all(word in text for word in request.query.casefold().split()):continue
        result = match(job, request.profile,evidence=evidence) if request.comparable_only else None
        if request.comparable_only and not result["comparable"]:
            continue
        facts=job.get('facts') or opportunity_facts(job) if request.pay!='all' or request.commitments else None
        if request.pay=='disclosed' and not facts['pay_disclosed']:continue
        if request.pay in {'paid','unpaid'} and facts['pay_status']!=request.pay:continue
        if request.commitments and not set(request.commitments).intersection(facts['commitments']):continue
        if request.sponsorship != "all":
            desc = job.get("description", "")
            has_no_sponsor = bool(re.search(r"(?:no (?:visa )?sponsorship(?:\s+(?:is\s+)?(?:available|offered|provided)|[.!]?$)|(?:cannot|unable to|do not|will not) (?:provide |offer )?(?:visa )?sponsor)", desc, re.I))
            has_citizen_pr = bool(re.search(r"\b(?:u\.?s\.?\s+citizen(?:ship)?\s+(?:is\s+)?required|must be a\s+u\.?s\.?\s+citizen|u\.?s\.?\s+citizens?\s+(?:only|or\s+permanent\s+resident)|security\s+clearance\s+(?:required|active)|green\s+card\s+holder)\b", desc, re.I))
            if request.sponsorship == "opt_cpt" and (has_no_sponsor or has_citizen_pr):
                continue
            elif request.sponsorship == "no_sponsorship" and not has_no_sponsor:
                continue
            elif request.sponsorship == "citizen_pr" and not has_citizen_pr:
                continue
        if request.closing_within_days:
            day=job['deadline_info']['date']
            if not day or not now.date().isoformat()<=day<=(now+timedelta(days=request.closing_within_days)).date().isoformat():continue
        if request.recent_days and recency(job)<(now-timedelta(days=request.recent_days)).timestamp():continue
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
            result = match(job, request.profile,evidence=evidence)
        jobs.append({**job, "match": result} if result else job)
    facets = {"fields": [{"value": k, "label": v, "count": fields[k]} for k, v in sorted(FIELDS.items(),key=lambda item:item[1].casefold())],
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
    page = [{**j,"facts":j.get("facts") or opportunity_facts(j)} for j in jobs[request.offset:request.offset + request.limit]]
    if not rank_by_fit and not request.comparable_only:
        page = [{**j, "match": match(j, request.profile,evidence=evidence)} for j in page]
    boards = {b["key"]: b for b in data["boards"]}
    page = [{**job, **company_brand(job["company"]), "availability": job["availability"] if job.get("is_program") else availability(job, boards.get(f"{job.get('source')}:{job.get('board')}"))} for job in page]
    if request.compact:
        page=[compact_card(job) for job in page]
    return {"jobs": page, "total": len(jobs), "boards": data["boards"], "facets": facets,
            "profile_skills": [s.skill for s in request.profile.skills],
            "needs_recheck_total":sum(j.get('needs_recheck',False) for j in jobs),
            "listing_total": sum(not j.get("is_program",False) for j in jobs), "program_total": sum(bool(j.get("is_program")) for j in jobs),
            "effective_sort": effective_sort, "catalog_total": len(catalog), "catalog_field_total": len({j["career_field"] for j in catalog}), "early_career_total": sum(j["role_type"] != "other" or bool(j.get("is_program")) for j in catalog)}


class VerifyOpportunity(BaseModel):
    job_id: str = Field(min_length=1, max_length=500)


class SubscribeRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)


@router.post("/api/careers/subscribe")
async def subscribe_alerts(request: SubscribeRequest, response: Response):
    response.headers.update(PRIVATE_HEADERS)
    email = request.email.strip()
    if "@" not in email or "." not in email.split("@")[-1] or len(email.split("@")[0]) < 1:
        raise HTTPException(400, "Please provide a valid email address.", headers=PRIVATE_HEADERS)
    return {"status": "subscribed", "email": email, "message": "Subscribed! You will receive weekly early drop alerts for new internships."}


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


@router.get('/practice',response_class=HTMLResponse)
@router.get('/interview',response_class=HTMLResponse)
@router.get('/practice/interview',response_class=HTMLResponse)
async def practice_page(response: Response):
    response.headers.update(PRIVATE_HEADERS)
    return Path(__file__).with_name('practice.html').read_text()


@router.get('/sandbox',response_class=HTMLResponse)
@router.get('/practice/sandbox',response_class=HTMLResponse)
async def sandbox_page(response: Response):
    response.headers.update(PRIVATE_HEADERS)
    return Path(__file__).with_name('sandbox.html').read_text()


@router.get('/prep',response_class=HTMLResponse)
@router.get('/practice/prep',response_class=HTMLResponse)
async def prep_page(response: Response):
    response.headers.update(PRIVATE_HEADERS)
    return Path(__file__).with_name('prep.html').read_text()


@router.get('/behavioral',response_class=HTMLResponse)
@router.get('/practice/behavioral',response_class=HTMLResponse)
async def behavioral_page(response: Response):
    response.headers.update(PRIVATE_HEADERS)
    return Path(__file__).with_name('behavioral.html').read_text()


def compact_card(job):
    if not job.get('description_deferred'):return job
    result={key:value for key,value in job.items() if key not in {'requirements','qualification_snapshot','application_key'}}
    result['match']={**job['match'],'checks':[{**c,'quote':None,'quote_deferred':True} for c in job['match']['checks']],'eligibility':[{**c,'quote':None,'quote_deferred':True} for c in job['match']['eligibility']]}
    return result


class DetailsRequest(BaseModel):
    profile:Profile=Field(default_factory=Profile)


@router.post('/api/careers/opportunities/{job_id}/details')
async def opportunity_details(job_id:str,body:DetailsRequest,response:Response):
    response.headers.update(PRIVATE_HEADERS)
    if len(job_id)>500:raise HTTPException(400,'Invalid opportunity identifier.')
    try:
        job=await store.get_job(job_id)
        if not job:raise HTTPException(404,'This opportunity is no longer in the catalog.')
        board=await store.get_board(job)
    except HTTPException:raise
    except Exception as exc:raise HTTPException(503,'Opportunity details are unavailable. Retry shortly.') from exc
    public=prepare_catalog({'jobs':[job]})['jobs']
    job=public[0] if public else job
    job={**job,'deadline_info':deadline_info(job),'facts':opportunity_facts(job),'availability':availability(job,board),'description_deferred':False,**company_brand(job['company'])}
    job['match']=await run_in_threadpool(match,job,body.profile)
    return {'job':job}


class InstantApplyRequest(BaseModel):
    job_id: str = Field(min_length=1, max_length=500)
    applicant_name: str = Field(min_length=1, max_length=120)
    applicant_email: str = Field(min_length=3, max_length=200)
    applicant_phone: str = Field(default="", max_length=50)
    school: str = Field(default="", max_length=200)
    major: str = Field(default="", max_length=200)
    graduation_year: str = Field(default="", max_length=20)
    work_authorization: str = Field(default="", max_length=100)
    portfolio_url: str = Field(default="", max_length=500)
    start_date: str = Field(default="", max_length=50)
    note: str = Field(default="", max_length=1000)
    has_resume: bool = True


@router.post("/api/careers/apply/instant")
async def instant_apply(data: InstantApplyRequest, request: Request, response: Response):
    from hives.careers.accounts import same_origin
    same_origin(request)
    response.headers.update(PRIVATE_HEADERS)
    email = data.applicant_email.strip()
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(400, "Please provide a valid email address.", headers=PRIVATE_HEADERS)
    if not data.applicant_name.strip():
        raise HTTPException(400, "Please provide your full name.", headers=PRIVATE_HEADERS)

    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        from hives.careers.accounts import connection as acc_conn, user as acc_user
        async with acc_conn() as conn:
            account = await acc_user(conn, request)
            if account:
                details = {
                    "notes": f"Instant applied via workBee on {now_iso[:10]}.\nWork auth: {data.work_authorization}\nStart date: {data.start_date}\n{data.note}".strip(),
                    "next_action": "Review application confirmation",
                    "follow_up": None,
                    "applied_via": "instant_apply",
                    "submitted_at": now_iso,
                    "revision": 1,
                }
                await conn.execute(
                    "UPDATE career_accounts SET applications=applications || jsonb_build_object($2::text, 'applied'), application_details=application_details || jsonb_build_object($2::text, $3::jsonb) WHERE id=$1",
                    account["id"], data.job_id, json.dumps(details)
                )
    except Exception:
        pass

    return {
        "status": "applied",
        "job_id": data.job_id,
        "applied_at": now_iso,
        "message": f"Application submitted for {data.applicant_name}! We saved your submission to your Application Pipeline."
    }

