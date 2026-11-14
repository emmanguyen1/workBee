"""Bounded cache of public catalog data only. Personal matches never enter this cache."""
import asyncio
from collections import OrderedDict
from time import monotonic
from starlette.concurrency import run_in_threadpool
from hives.careers import store
from hives.careers.deadlines import deadline_info
from hives.careers.geography import geography
from hives.careers.programs import student_years
from hives.careers.sectors import sector_tags
from hives.careers.simplify import deduplicate
from hives.careers.taxonomy import career_field,role_type,talent_pool


def prepare(data):
    jobs=[]
    for raw in deduplicate(data['jobs']):
        if talent_pool(raw['title']):continue
        if raw.get('summary_version')==1:
            jobs.append(raw);continue
        job={**raw,'deadline_info':deadline_info(raw),'sectors':sector_tags(raw),
          'career_field':raw.get('career_field','other') if raw.get('source') in {'simplify','program'} else career_field(raw['title'],raw.get('department','')),
          'role_type':raw['role_type'] if raw.get('is_program') else 'internship' if raw['role_type']=='internship' else role_type(raw['title']),
          'locations':raw.get('locations') or [raw.get('location','')],
          'workplace':raw.get('workplace','unspecified').lower()}
        job['student_audience']=raw['student_audience'] if raw.get('is_program') else student_years(raw)
        job['geography']=geography(job)
        jobs.append(job)
    return {**data,'jobs':jobs,'prepared':True}


class PublicCatalogCache:
    def __init__(self,ttl=60,max_entries=2,clock=monotonic,max_age=300):
        self.ttl=ttl;self.max_entries=max_entries;self.clock=clock;self.max_age=max_age
        self.entries=OrderedDict();self.loop=None;self.lock=None
    def clear(self):self.entries.clear()
    async def get(self,**options):
        loop=asyncio.get_running_loop()
        if loop is not self.loop:
            self.clear();self.loop=loop;self.lock=asyncio.Lock()
        # Tests/custom loaders get a distinct namespace; store writes increment the epoch.
        key=(id(store.catalog),store.catalog_epoch(),tuple(sorted(options.items())))
        async with self.lock:
            entry=self.entries.get(key)
            if entry and self.clock()-entry[0]<self.ttl:
                self.entries.move_to_end(key);return entry[1],True
            if entry and entry[2] is not None and self.clock()-entry[3]<self.max_age:
                revision=await store.catalog_revision(**options)
                if revision==entry[2]:
                    self.entries[key]=(self.clock(),entry[1],revision,entry[3])
                    self.entries.move_to_end(key);return entry[1],True
            raw=await store.catalog(**options)
            public=await run_in_threadpool(prepare,raw)
            self.entries[key]=(self.clock(),public,raw.get('revision'),self.clock())
            while len(self.entries)>self.max_entries:self.entries.popitem(last=False)
            return public,False

cache=PublicCatalogCache()
