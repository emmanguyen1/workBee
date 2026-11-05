"""Source-backed early-college directory, separate from feed-listed job counts."""
from datetime import date, datetime, timezone
from pathlib import Path
import yaml
from hives.careers.branding import company_brand


def program_catalog(now=None):
    now = now or datetime.now(timezone.utc)
    today = now.date()
    rows = yaml.safe_load(Path(__file__).with_name('programs.yml').read_text())['programs']
    result = []
    for row in rows:
        status = row['status']
        deadline = date.fromisoformat(row['deadline']) if row.get('deadline') else None
        expired = now > datetime.fromisoformat(row['deadline_at']) if row.get('deadline_at') else bool(deadline and today > deadline)
        if expired: status = 'closed'
        elif status == 'application_window':
            if row.get('opens_on') and today < date.fromisoformat(row['opens_on']): status = 'upcoming'
            elif not 0 <= (today-date.fromisoformat(row['checked_on'])).days <= 30: status = 'needs_review'
        labels = {'application_window':'Published window open · confirm with provider','closed':'Published cycle closed','check_postings':'Check individual postings','notify_only':'Session notifications only','needs_review':'Status needs rechecking','upcoming':'Published window not yet open'}
        result.append({**row, **company_brand(row['company']), 'status':status, 'status_label':labels[status], 'days_until_deadline':(deadline-today).days if deadline else None})
    result.sort(key=lambda p:(p['status']!='application_window', p['status']=='closed', p.get('deadline','9999')))
    return result


def student_years(job):
    """Return explicit class-year wording, without inferring from graduation dates."""
    import re
    if job.get('role_type') != 'internship':
        return {'years': [], 'evidence': []}
    years, evidence = set(), []
    for line in job.get('description','').splitlines():
        if re.search(r'\b(?:not|no|excluding|except|ineligible)\b', line, re.I): continue
        # Long prose/benefits and mentor references are not class-year requirements.
        if len(line)>1200 or re.search(r'\b(?:mentor|teach|supervis)\w*\b', line, re.I): continue
        if re.search(r'\b(?:master|masters|graduate student|phd|doctoral)\b',line,re.I): continue
        if not re.search(r'student|undergraduat|college|universit|freshm|sophom',line,re.I): continue
        found=[]
        if re.search(r'\bfreshm[ae]n\b|\bfirst[ -]year\b|\bfirst (?:or|and) second[ -]year\b',line,re.I): found.append(1)
        if re.search(r'\bsophomores?\b|\bsecond[ -]year\b',line,re.I): found.append(2)
        if found:
            years.update(found); evidence.append(line[:600])
    return {'years':sorted(years),'evidence':evidence[:3]}


def program_jobs(now=None):
    from hives.careers.geography import COUNTRIES
    result=[]
    for program in program_catalog(now):
        internship='internship' in program['kind'].lower()
        categories=['program']
        if internship: categories.append('internship')
        if 'research' in program['kind'].lower(): categories.append('research')
        result.append({**program, 'is_program':True, 'source':'program', 'board':'early-college',
                       'description':'', 'career_field':program['field'], 'role_type':'internship' if internship else 'other',
                       'location':' / '.join(COUNTRIES.get(c,c) for c in program['countries']) or 'Check the session location',
                       'locations':[COUNTRIES.get(c,c) for c in program['countries']], 'workplace':'unspecified',
                       'opportunity_types':categories, 'student_audience':{'years':program['years'],'evidence':[program['eligibility']]},
                       'first_seen':program['checked_on'], 'last_seen':None,
                       'search_text':' '.join([program['summary'],program['eligibility'],program['cycle']]),
                       'availability':{'state':program['status'],'label':program['status_label'],'checked_at':None,
                                       'verification_supported':False,'note':'Manually researched program; check the official source.'}})
    return result
