"""Upgrade only public job analysis, without changing availability timestamps."""
import asyncio
import json
from core import db
from hives.careers.feeds import employers
from hives.careers.matching import requirements, REQUIREMENTS_VERSION
from hives.careers.qualifications import qualification_snapshot, QUALIFICATION_VERSION


async def main():
    conn=await db.connect()
    keys=[f"{e['source']}:{e['board']}" for e in employers() if e['source'] in {'greenhouse','lever','ashby'}]
    cursor='';total=0
    try:
        while True:
            rows=await conn.fetch('SELECT id,data FROM career_jobs WHERE open AND board_key=ANY($1::text[]) AND id>$2 ORDER BY id LIMIT 200',keys,cursor)
            if not rows:break
            updates=[]
            for row in rows:
                job=json.loads(row['data']) if isinstance(row['data'],str) else row['data']
                if job.get('qualification_version')==QUALIFICATION_VERSION and job.get('requirements_version')==REQUIREMENTS_VERSION:continue
                description=job.get('description','')
                analysis={'qualification_snapshot':qualification_snapshot(description),'qualification_version':QUALIFICATION_VERSION,
                          'requirements':job['requirements'] if job.get('requirements_version')==REQUIREMENTS_VERSION else requirements(description),
                          'requirements_version':REQUIREMENTS_VERSION}
                updates.append((row['id'],json.dumps(analysis),description))
            if updates:
                await conn.executemany("UPDATE career_jobs SET data=data || $2::jsonb WHERE id=$1 AND data->>'description'=$3",updates)
            total+=len(updates);cursor=rows[-1]['id']
            print(f'Public posting analyses upgraded: {total}',flush=True)
    finally:await conn.close()

if __name__=='__main__':asyncio.run(main())
