"""Poll the read-only deployed demo portfolio until a fixed deadline."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
import ssl
import certifi
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / 'logs' / 'kalshi-demo-test-2026-10-15.jsonl'
MARKER = '# hivework-demo-test-2026-10-15'
DEADLINE = datetime(2026, 10, 16, 10, 0, tzinfo=ZoneInfo('America/New_York'))
URL = 'https://gdg-mentor.vercel.app/api/kalshi/portfolio'


def current_cron():
    result = subprocess.run(['/usr/bin/crontab', '-l'], capture_output=True, text=True)
    if result.returncode and 'no crontab' not in result.stderr.lower():
        raise RuntimeError('Could not read crontab: ' + result.stderr.strip())
    return result.stdout


def update_cron(install=False):
    previous = current_cron()
    lines = [line for line in previous.splitlines() if MARKER not in line]
    if install:
        import shlex
        command = shlex.join([sys.executable, str(Path(__file__).resolve())])
        lines.append(f'* * * * * {command} >> {shlex.quote(str(ROOT / "logs" / "kalshi-demo-cron.log"))} 2>&1 {MARKER}')
    updated = '\n'.join(lines) + ('\n' if lines else '')
    if updated != previous:
        subprocess.run(['/usr/bin/crontab', '-'], input=updated, text=True, check=True)


def record(data):
    LOG.parent.mkdir(exist_ok=True)
    with LOG.open('a') as output:
        output.write(json.dumps(data) + '\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--install', action='store_true')
    args = parser.parse_args()
    now = datetime.now(ZoneInfo('America/New_York'))
    if now >= DEADLINE:
        update_cron()
        record({'checked_at': now.isoformat(), 'status': 'stopped', 'reason': 'Deadline reached', 'deadline': DEADLINE.isoformat()})
        return
    if args.install:
        LOG.parent.mkdir(exist_ok=True)
        update_cron(install=True)
        print('Installed: every minute until ' + DEADLINE.isoformat())
    record_data = {'checked_at': now.isoformat(), 'deadline': DEADLINE.isoformat()}
    try:
        request = Request(URL, headers={'Cache-Control': 'no-cache', 'User-Agent': 'Hivework-demo-test/1.0'})
        with urlopen(request, timeout=30, context=ssl.create_default_context(cafile=certifi.where())) as response:
            data = json.load(response)
        if data.get('environment') != 'demo' or data.get('read_only') is not True:
            raise ValueError('Expected a read-only demo response')
        for field in ('updated_at', 'cash_cents', 'positions_value_cents', 'unrealized_pnl_cents', 'unrealized_return_percent', 'open_market_fees_cents'):
            record_data[field] = data[field]
        record_data.update(status='ok', positions=len(data['positions']), orders=len(data['orders']))
    except Exception as exc:
        record_data.update(status='error', error=str(exc))
    record(record_data)
    print(json.dumps(record_data))


if __name__ == '__main__':
    main()
