"""One-time, resumable public search-index upgrade; never change source freshness."""
import asyncio,json
from hives.careers import store
from hives.careers.feeds import employers
from hives.careers.search_index import build,VERSION,REQUIREMENTS_VERSION,QUALIFICATION_VERSION
from core import db

async def main():
    await store.initialize();conn=await db.connect();cursor='';total=0
    keys=[f"{e['source']}:{e['board']}" for e in employers()]
    try:
        while True:
            rows=await conn.fetch("SELECT id,data,changed_at,md5(data::text) AS fingerprint FROM career_jobs WHERE open AND board_key=ANY($1::text[]) AND id>$2 AND (summary IS NULL OR summary_changed_at IS NULL OR summary_changed_at<changed_at OR summary->>'summary_version' IS DISTINCT FROM $3 OR summary->>'requirements_version' IS DISTINCT FROM $4 OR summary->>'qualification_version' IS DISTINCT FROM $5) ORDER BY id LIMIT 200",keys,cursor,str(VERSION),str(REQUIREMENTS_VERSION),str(QUALIFICATION_VERSION))
            if not rows:break
            def indexed():
                updates=[]
                for row in rows:
                    raw=json.loads(row['data']) if isinstance(row['data'],str) else row['data']
                    summary,document=build(raw)
                    updates.append((row['id'],json.dumps(summary),document,row['fingerprint'],row['changed_at']))
                return updates
            updates=await asyncio.to_thread(indexed)
            async with conn.transaction():
                await conn.executemany('UPDATE career_jobs SET summary=$2::jsonb,search_document=$3,summary_changed_at=changed_at WHERE id=$1 AND md5(data::text)=$4 AND changed_at=$5',updates)
            total+=len(updates);cursor=rows[-1]['id'];print(f'Public search records indexed: {total}',flush=True)
        store.invalidate_catalog();print('Public search index ready.',flush=True)
    finally:await conn.close()

if __name__=='__main__':asyncio.run(main())
