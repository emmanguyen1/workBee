import test from 'node:test';
import assert from 'node:assert/strict';
import {parseSkills, apiError, assessmentLabel, relativeTime, freshnessWindow, comparisonPreferences} from '../hives/careers/static/logic.mjs';

test('comma-separated skills are individual skills; evidence commas are retained',()=>{
  assert.deepEqual(parseSkills('Python, SQL | Built an API, with charts\nReact'),[
    {skill:'Python',evidence:'Built an API, with charts'},
    {skill:'SQL',evidence:'Built an API, with charts'},
    {skill:'React',evidence:''},
  ]);
});

test('duplicates prefer evidence and excessive skill lists are actionable',()=>{
  assert.deepEqual(parseSkills('Python\npython | Course project'),[{skill:'python',evidence:'Course project'}]);
  assert.throws(()=>parseSkills(Array.from({length:61},(_,i)=>'Skill'+i).join(',')),/up to 60/);
});

test('applying a profile switches newest sorting to fit without clearing area preferences',()=>{
  assert.deepEqual(comparisonPreferences({sort:'newest',location:'Boston',company:'Figma'},true),{sort:'fit',location:'Boston',company:'Figma',comparable_only:true});
  assert.equal(comparisonPreferences({},false).comparable_only,false);
});

test('missing requirements and missing profile have distinct labels, not zero scores',()=>{
  assert.equal(assessmentLabel({assessment:'requirements_unavailable',score:null}),'Requirements not supplied');
  assert.equal(assessmentLabel({assessment:'needs_profile',score:null}),'Add skills to compare');
  assert.equal(assessmentLabel({assessment:'assessed',score:0}),'0%');
});

test('validation errors surface the actual problem without echoing request input',()=>{
  const text=apiError({detail:[{loc:['body','profile'],msg:'Value error, Availability end must be on or after the start date',input:'private resume text'}]});
  assert.match(text,/Availability end/);assert.ok(!text.includes('private resume'));
});

test('source freshness is readable and handles absent times',()=>{
  const now=Date.parse('2026-10-22T18:00:00Z');
  assert.equal(relativeTime('2026-10-22T17:45:00Z',now),'Source checked 15m ago');
  assert.equal(relativeTime('',now),'Check time unavailable');
});

test('freshnessWindow identifies golden window, early drops, and standard listings',()=>{
  const now=Date.parse('2026-10-22T18:00:00Z');
  // 3 hours old -> Golden window
  const golden=freshnessWindow({first_seen:'2026-10-22T15:00:00Z'},now);
  assert.equal(golden.isGolden,true);
  assert.equal(golden.isEarly,false);
  assert.equal(golden.tier,'golden');
  assert.match(golden.label,/Golden window/);
  assert.equal(golden.timeLabel,'3h ago');

  // Published date preferred over first_seen if available
  const pubGolden=freshnessWindow({first_seen:'2026-10-10T12:00:00Z',published_at:'2026-10-22T17:30:00Z'},now);
  assert.equal(pubGolden.isGolden,true);

  // 48 hours old -> Early drop
  const early=freshnessWindow({first_seen:'2026-10-20T18:00:00Z'},now);
  assert.equal(early.isGolden,false);
  assert.equal(early.isEarly,true);
  assert.equal(early.tier,'early');
  assert.match(early.label,/Early drop/);

  // 5 days old -> Standard
  const standard=freshnessWindow({first_seen:'2026-10-17T18:00:00Z'},now);
  assert.equal(standard.isGolden,false);
  assert.equal(standard.isEarly,false);
  assert.equal(standard.tier,'standard');

  // Missing or invalid dates
  assert.equal(freshnessWindow({},now).isGolden,false);
  assert.equal(freshnessWindow({first_seen:'invalid'},now).isGolden,false);
});

test('calendar exports use the published deadline timezone and escape text', async()=>{
  const {deadlineCalendar}=await import('../hives/careers/static/logic.mjs');
  const ics=deadlineCalendar({id:'program:suli',title:'Science, lab; research',deadline:'2027-01-06',deadline_at:'2027-01-06T22:00:00+00:00',source_url:'https://science.osti.gov/wdts/suli'},new Date('2026-11-05T12:00:00Z'));
  assert.match(ics,/DTSTART:20270106T220000Z/);
  assert.match(ics,/Science\\, lab\\; research/);
  assert.match(ics,/END:VCALENDAR\r\n$/);
  const day=deadlineCalendar({id:'program:example',title:'Example',deadline:'2027-01-06',source_url:'https://example.com'});
  assert.match(day,/DTSTART;VALUE=DATE:20270106/);
  assert.match(day,/DTEND;VALUE=DATE:20270107/);
});

test('resume merging retains user skills and upgrades weak evidence',async()=>{
  const {mergeProfileSkills}=await import('../hives/careers/static/logic.mjs');
  const old=[{skill:'Python',evidence:'Listed skill'},{skill:'Excel',evidence:'Managed a budget project'}],incoming=[{skill:'Python',evidence:'Built a data pipeline'},{skill:'SQL',evidence:'Built a reporting project'}];
  const merged=mergeProfileSkills(old,incoming);
  assert.equal(merged.length,3);assert.equal(merged[0].evidence,'Built a data pipeline');assert.equal(merged[1].skill,'Excel');
  assert.equal(mergeProfileSkills(old,incoming,true).length,2);
  assert.throws(()=>mergeProfileSkills(Array.from({length:60},(_,i)=>({skill:'Skill'+i,evidence:''})),incoming),/exceeds 60/);
});

test('multi-choice preferences restore arrays and legacy saved filters',async()=>{
  const {preferenceChoices}=await import('../hives/careers/static/logic.mjs');
  assert.deepEqual(preferenceChoices({career_fields:['healthcare','business','healthcare']},'career_fields','career_field'),['healthcare','business']);
  assert.deepEqual(preferenceChoices({career_fields:[],career_field:'finance'},'career_fields','career_field'),['finance']);
  assert.deepEqual(preferenceChoices({career_fields:[],career_field:'all'},'career_fields','career_field'),[]);
});

test('application CSV preserves multiline notes and neutralizes spreadsheet formulas',async()=>{
  const {applicationsCSV}=await import('../hives/careers/static/logic.mjs');
  const csv=applicationsCSV([{company:'=HYPERLINK("evil")',title:'Policy, research',status:'saved',details:{notes:'First line\n"quoted"',next_action:'@formula',follow_up:'2030-01-10'}}]);
  assert.ok(csv.startsWith('\uFEFF'));assert.ok(csv.includes('"\'=HYPERLINK(""evil"")"'));assert.ok(csv.includes('"Policy, research"'));assert.ok(csv.includes('"First line\n""quoted"""'));assert.ok(csv.includes('"\'@formula"'));
});

test('account profile submit applies reviewed changes instead of silently doing nothing',async()=>{
  const {readFile}=await import('node:fs/promises');
  const source=await readFile(new URL('../hives/careers/static/app.mjs',import.meta.url),'utf8');
  const binding=source.match(/^\$\('profile'\)\.onsubmit=.*$/m)?.[0];assert.ok(binding);
  const form={};let applied=0,prevented=0;
  const bind=new Function('$','applyProfile','isAccountPage','let hasAccountEdits=false;'+binding+';return ()=>hasAccountEdits;');
  const dirty=bind(()=>form,()=>applied++,true);
  form.onsubmit({preventDefault(){prevented++}});
  assert.equal(prevented,1);assert.equal(applied,1);assert.equal(dirty(),true);
});
