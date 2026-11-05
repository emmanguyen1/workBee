"""Availability evidence from complete configured feeds, never HTTP-200 guesses."""
import asyncio
from datetime import datetime, timezone
from time import monotonic

import httpx

from hives.careers.feeds import employers, fetch_board

_CACHE = {}
_LOCK = asyncio.Lock()


def availability(job, board=None, now=None):
    now = now or datetime.now(timezone.utc)
    checked = job.get('last_seen')
    try:
        age = (now - datetime.fromisoformat(checked.replace('Z', '+00:00'))).total_seconds()
        recent = 0 <= age <= 1800
    except (ValueError, TypeError, AttributeError):
        recent = False
    verification = job.get('verification')
    if verification and verification.get('state') in {'listed', 'removed', 'community', 'unavailable'}:
        try:
            verified = datetime.fromisoformat(verification['checked_at'])
            last_seen = datetime.fromisoformat(checked.replace('Z', '+00:00')) if checked else datetime.min.replace(tzinfo=timezone.utc)
            if verified >= last_seen and 0 <= (now - verified).total_seconds() <= 1800:
                return verification
        except (ValueError, TypeError, KeyError, AttributeError):
            pass
    community = job.get('source') == 'simplify' 
    if job.get('open') is False:
        state, label = 'removed', 'Removed from source feed'
    elif community:
        state, label = 'community', 'Community-listed · verify with employer'
    elif board and board.get('error'):
        state, label = 'unavailable', 'Latest source check failed'
    elif recent:
        state, label = 'listed', 'Listed in employer feed'
    else:
        state, label = 'stale', 'Employer status needs refresh'
    return {'state': state, 'label': label, 'checked_at': checked,
            'verification_supported': any(e['source'] == job.get('source') and e['board'] == job.get('board') for e in employers()),
            'note': 'Source presence is not a guarantee that the application form accepts submissions. Community presence does not verify employer availability.'}


async def verify(job):
    employer = next((e for e in employers() if e['source'] == job.get('source') and e['board'] == job.get('board')), None)
    if not employer:
        return {**availability(job), 'state': 'unsupported', 'label': 'No configured source to check'}
    key = (employer['source'], employer['board'])
    async with _LOCK:
        cached = _CACHE.get(key)
        if not cached or monotonic() - cached['time'] >= 60:
            checked = datetime.now(timezone.utc).isoformat()
            try:
                async with httpx.AsyncClient(timeout=20, headers={'User-Agent': 'Hivework-Careers/0.1'}) as client:
                    jobs = await fetch_board(client, employer)
                cached = {'time': monotonic(), 'checked_at': checked, 'ids': {j['id'] for j in jobs}, 'error': False}
            except (httpx.HTTPError, ValueError, KeyError, TypeError):
                cached = {'time': monotonic(), 'checked_at': checked, 'ids': set(), 'error': True}
            # Cache only public feed membership. Never cache profile data or failures as closures.
            _CACHE[key] = cached
    if cached['error']:
        state, label = 'unavailable', 'Source unavailable · status unknown'
    elif job['id'] not in cached['ids']:
        state, label = 'removed', 'No longer listed in source feed'
    elif employer['source'] == 'simplify':
        state, label = 'community', 'Still community-listed · verify with employer'
    else:
        state, label = 'listed', 'Listed in employer feed'
    return {'state': state, 'label': label, 'checked_at': cached['checked_at'],
            'verification_supported': True, 'note': availability(job)['note']}
