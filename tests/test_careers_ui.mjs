import test from 'node:test';
import assert from 'node:assert/strict';
import {parseSkills, apiError, assessmentLabel, relativeTime, comparisonPreferences} from '../hives/careers/static/logic.mjs';

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
