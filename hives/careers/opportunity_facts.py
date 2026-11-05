"""Conservative decision facts from explicit employer wording, never estimated pay."""
import re
from functools import lru_cache

MONEY=re.compile(r'(?:[$£€]\s?\d[\d,.]*(?:\s?[kK])?|\b(?:USD|CAD|GBP|EUR)\s?\d[\d,.]*)')
PAY_CONTEXT=re.compile(r'salary|compensation|stipend|hourly|per hour|/hour|/hr|per annum|per year|annually|pay (?:range|rate)|base pay|wage',re.I)

@lru_cache(maxsize=8192)
def facts(title,description):
    text=title+'\n'+description
    unpaid=re.search(r'\bunpaid (?:internship|position|role)\b|\b(?:internships?|positions?|roles?) (?:are|is|will be) unpaid\b',text,re.I)
    paid=re.search(r'\bpaid (?:internship|position|role)\b|\b(?:internships?|positions?|roles?) (?:are|is|will be) paid\b',text,re.I)
    quotes=[line[max(0,MONEY.search(line).start()-120):MONEY.search(line).start()+580] for line in description.splitlines() if MONEY.search(line) and PAY_CONTEXT.search(line) and not re.search(r'budget|fundrais|revenue|donat|insurance coverage|sign.on|referral bonus',line,re.I)]
    state='unknown' if unpaid and (paid or quotes) else 'unpaid' if unpaid else 'paid' if paid or quotes else 'unknown'
    commitments=[key for key,pattern in [('part_time',r'\bpart[ -]time\b'),('full_time',r'\bfull[ -]time\b'),('temporary',r'\b(?:fixed[ -]term|temporary|seasonal)\b')] if re.search(pattern,text,re.I)]
    return {'pay_status':state,'pay_disclosed':bool(quotes),'pay_quote':quotes[0] if quotes else (unpaid or paid).group(0) if unpaid or paid else '', 'commitments':commitments}


def opportunity_facts(job):
    return facts(job['title'],job.get('description',''))
