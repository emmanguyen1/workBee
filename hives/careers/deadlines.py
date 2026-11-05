"""Explicit application deadlines only; never infer from internship/start dates."""
import re
from datetime import datetime, timezone
from functools import lru_cache

MARKER=re.compile(r'\b(?:application(?:s)?\s+(?:deadline|close(?:s)?|due)|apply\s+by|closing\s+date|deadline\s+to\s+apply)\b',re.I)
DATE=re.compile(r'\b20\d{2}-\d{2}-\d{2}\b|\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2}(?:st|nd|rd|th)?,?\s+20\d{2}\b',re.I)


def parse_date(value):
    try:
        parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
        return parsed.date().isoformat(),parsed.isoformat() if 'T' in value and parsed.tzinfo else None
    except (ValueError,TypeError,AttributeError):pass
    value=re.sub(r'(\d)(st|nd|rd|th)',r'\1',str(value)).replace(',','')
    for fmt in ('%B %d %Y','%b %d %Y'):
        try:return datetime.strptime(value,fmt).date().isoformat(),None
        except ValueError:pass
    return None,None


@lru_cache(maxsize=512)
def extract_deadline(description, explicit=''):
    candidates={}
    if explicit:
        day,at=parse_date(explicit)
        if day:candidates[day]={'date':day,'at':at,'quote':'Employer-provided application deadline','source':'employer_field'}
    if not candidates:
        for marker in MARKER.finditer(description):
            segment=description[marker.start():marker.end()+110].split('\n')[0]
            for found in DATE.finditer(segment):
                day,at=parse_date(found.group())
                if day:candidates[day]={'date':day,'at':at,'quote':segment[:500],'source':'posting_text'}
    if len(candidates)==1:return next(iter(candidates.values()))
    return {'date':None,'at':None,'quote':'Multiple deadline dates; confirm with employer.' if candidates else '', 'source':'ambiguous' if candidates else 'not_provided'}


def deadline_info(job,now=None):
    now=now or datetime.now(timezone.utc)
    stored=job.get('deadline_info') or extract_deadline(job.get('description',''),str(job.get('application_deadline') or ''))
    result=dict(stored);day=result.get('date');at=result.get('at')
    result['expired']=(now>datetime.fromisoformat(at)) if at else bool(day and now.date().isoformat()>day)
    result['timezone_note']='Employer cutoff time provided' if at else 'Date only; cutoff time/timezone not specified' if day else 'Deadline not provided'
    return result


def recency(job):
    for key in ('published_at','first_seen'):
        value=job.get(key)
        if not value:continue
        try:
            parsed=datetime.fromisoformat(str(value).replace('Z','+00:00'))
            return (parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)).timestamp()
        except ValueError:pass
    return 0
