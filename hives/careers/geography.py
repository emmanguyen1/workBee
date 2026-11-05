"""Conservative country/region facets; city-only locations remain unspecified."""
import re

US_STATES = dict(item.split(':') for item in (
    'AL:Alabama|AK:Alaska|AZ:Arizona|AR:Arkansas|CA:California|CO:Colorado|CT:Connecticut|DE:Delaware|DC:District of Columbia|FL:Florida|GA:Georgia|HI:Hawaii|ID:Idaho|IL:Illinois|IN:Indiana|IA:Iowa|KS:Kansas|KY:Kentucky|LA:Louisiana|ME:Maine|MD:Maryland|MA:Massachusetts|MI:Michigan|MN:Minnesota|MS:Mississippi|MO:Missouri|MT:Montana|NE:Nebraska|NV:Nevada|NH:New Hampshire|NJ:New Jersey|NM:New Mexico|NY:New York|NC:North Carolina|ND:North Dakota|OH:Ohio|OK:Oklahoma|OR:Oregon|PA:Pennsylvania|RI:Rhode Island|SC:South Carolina|SD:South Dakota|TN:Tennessee|TX:Texas|UT:Utah|VT:Vermont|VA:Virginia|WA:Washington|WV:West Virginia|WI:Wisconsin|WY:Wyoming|PR:Puerto Rico'
).split('|'))
CA_PROVINCES = dict(item.split(':') for item in 'AB:Alberta|BC:British Columbia|MB:Manitoba|NB:New Brunswick|NL:Newfoundland and Labrador|NS:Nova Scotia|NT:Northwest Territories|NU:Nunavut|ON:Ontario|PE:Prince Edward Island|QC:Quebec|SK:Saskatchewan|YT:Yukon'.split('|'))
COUNTRIES = {'US':'United States','CA':'Canada','GB':'United Kingdom','DE':'Germany','FR':'France','IN':'India','AU':'Australia','SG':'Singapore','JP':'Japan','CN':'China','IE':'Ireland','NL':'Netherlands','CH':'Switzerland','ES':'Spain','IT':'Italy','BR':'Brazil','MX':'Mexico','IL':'Israel','KR':'South Korea','NZ':'New Zealand','SE':'Sweden','DK':'Denmark','NO':'Norway','FI':'Finland','PL':'Poland','PT':'Portugal','AT':'Austria','BE':'Belgium','AE':'United Arab Emirates','ZA':'South Africa','PH':'Philippines','TW':'Taiwan','HK':'Hong Kong','ID':'Indonesia','MY':'Malaysia','VN':'Vietnam','TH':'Thailand','AR':'Argentina','CL':'Chile','CO':'Colombia','CZ':'Czechia','RO':'Romania','HU':'Hungary','GR':'Greece','TR':'Turkey','SA':'Saudi Arabia','EG':'Egypt','NG':'Nigeria','KE':'Kenya','PK':'Pakistan','BD':'Bangladesh','UA':'Ukraine'}
ALIASES = {'usa':'US','u.s.':'US','u.s.a.':'US','united states of america':'US','uk':'GB','u.k.':'GB','england':'GB','scotland':'GB','wales':'GB','northern ireland':'GB','czech republic':'CZ'}
REGIONS = {**{'US-'+code:name for code,name in US_STATES.items()}, **{'CA-'+code:name for code,name in CA_PROVINCES.items()}}


def country_code(text):
    value = str(text).strip()
    if value.upper() in COUNTRIES:
        return value.upper()
    return ALIASES.get(value.casefold()) or next((code for code,name in COUNTRIES.items() if name.casefold()==value.casefold()), None)


def geography(job):
    countries, regions = set(), set()
    for raw in job.get('countries', []):
        code = country_code(raw)
        if code: countries.add(code)
        elif re.fullmatch(r'[A-Z]{2}', str(raw)): countries.add(str(raw))
    declared = countries.copy()
    for location in job.get('locations') or [job.get('location', '')]:
        # Exact pieces avoid mistaking 'Remote' for OR or 'India' for IN.
        pieces = [p.strip() for p in re.split(r'[,;|/()]|\s+[–—-]\s+', location) if p.strip()]
        explicit = {code for p in pieces if (code := country_code(p)) and (len(p)>2 or p.upper() not in US_STATES)}
        # Country abbreviations at the end of a multi-part address have context.
        if len(pieces)>1 and pieces[-1].upper() in {'US','USA','UK','GB','CA'}:
            # CA alone after a US city is a state, not evidence of Canada.
            if pieces[-1].upper()!='CA' or 'CA' in countries or any(p in CA_PROVINCES for p in pieces[:-1]):
                code=country_code(pieces[-1])
                if code: explicit.add(code)
        if not explicit and len(declared)==1: explicit=declared.copy()
        for piece in pieces:
            for prefix, names in [('US',US_STATES),('CA',CA_PROVINCES)]:
                if explicit and prefix not in explicit: continue
                abbreviated = {p for p in pieces if p in names}
                for code,name in names.items():
                    if piece==code and prefix=='US' and code in COUNTRIES and code!='CA' and 'US' not in explicit:
                        continue  # Ambiguous country/state codes need explicit US context.
                    if abbreviated and code not in abbreviated: continue
                    if piece.casefold()==name.casefold() or (piece==code and (len(pieces)>1 or prefix in countries)):
                        regions.add(prefix+'-'+code);countries.add(prefix)
        countries.update(explicit)
    return {'countries':sorted(countries), 'regions':sorted(regions)}


def region_matches(job, country='', region=''):
    place=job.get('geography') or geography(job)
    if country=='unknown': return not place['countries'] and not region
    return (not country or country in place['countries']) and (not region or region in place['regions'])


def preferred_matches(query, job):
    code = country_code(query)
    if code: return region_matches(job, country=code)
    region = next((code for code,name in REGIONS.items() if name.casefold()==query.strip().casefold()), None)
    if region: return region_matches(job, region=region)
    from hives.careers.taxonomy import location_matches
    return location_matches(query, [*(job.get('locations') or [job.get('location','')]), *job.get('countries',[])])
