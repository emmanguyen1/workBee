import test from 'node:test';
import assert from 'node:assert/strict';
import {parseSkills, apiError, assessmentLabel, relativeTime, freshnessWindow, comparisonPreferences, formatPayPill, eligibilityBadges, kanbanColumns} from '../hives/careers/static/logic.mjs';

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

test('googleCalendarUrl and pipelineCalendarIcs generate correct sync links and multi-event feeds', async()=>{
  const {googleCalendarUrl, pipelineCalendarIcs}=await import('../hives/careers/static/logic.mjs');
  
  // Test Google Calendar link
  const gUrl = googleCalendarUrl({
    company: 'Stripe',
    title: 'Software Engineer Intern',
    deadline: '2027-02-15',
    apply_url: 'https://stripe.com/jobs/123'
  });
  assert.match(gUrl, /https:\/\/calendar\.google\.com\/calendar\/render/);
  assert.match(gUrl, /Stripe/);
  assert.match(gUrl, /20270215/);

  // Test multi-event ICS feed
  const apps = [
    {
      id: 'app-1',
      company: 'Microsoft',
      title: 'Explore Intern',
      deadline_date: '2027-03-01',
      status: 'applied',
      apply_url: 'https://careers.microsoft.com/456'
    },
    {
      id: 'app-2',
      company: 'Apple',
      title: 'Hardware Co-op',
      deadline_date: '2027-04-10',
      status: 'preparing'
    }
  ];
  const multiIcs = pipelineCalendarIcs(apps, new Date('2026-11-01T00:00:00Z'));
  assert.match(multiIcs, /BEGIN:VCALENDAR/);
  assert.match(multiIcs, /X-WR-CALNAME:workBee Application Deadlines/);
  assert.match(multiIcs, /\[Deadline\] Microsoft - Explore Intern/);
  assert.match(multiIcs, /\[Prep Milestone\] 3 days until Microsoft/);
  assert.match(multiIcs, /\[Deadline\] Apple - Hardware Co-op/);
  assert.match(multiIcs, /END:VCALENDAR\r\n$/);
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

test('formatPayPill extracts concise hourly, monthly, and yearly salary pills', () => {
  // Hourly range
  assert.equal(formatPayPill('The expected pay is between $40 and $58/hour for MA roles.', 'paid'), '$40–$58/hr');
  assert.equal(formatPayPill('$45.00 - $55.00 / hr', 'paid'), '$45–$55/hr');
  // Single hourly
  assert.equal(formatPayPill('$35/hour base compensation', 'paid'), '$35/hr');
  // Monthly
  assert.equal(formatPayPill('$8,000/month stipend provided', 'paid'), '$8k/mo');
  // Yearly
  assert.equal(formatPayPill('Annual salary $85,000 - $110,000 / year', 'paid'), '$85k–$110k/yr');
  // Status fallback
  assert.equal(formatPayPill('', 'paid'), 'Explicitly paid');
  assert.equal(formatPayPill('', 'unpaid'), 'Unpaid');
  assert.equal(formatPayPill('', 'unknown'), null);
});

test('eligibilityBadges detects visa sponsorship, citizenship, grad years, and gpa fit', () => {
  // 1. Visa sponsorship conflict when user needs sponsorship
  const noSponsorJob = {
    description: 'We cannot provide visa sponsorship for this role.',
    match: {
      eligibility: [{criterion: 'Sponsorship', status: 'conflict', explanation: 'Only compares sponsorship needs'}]
    }
  };
  const badSponsor = eligibilityBadges(noSponsorJob, {needs_sponsorship: true});
  assert.ok(badSponsor.some(b => b.type === 'visa' && b.status === 'conflict'));

  // 2. Visa sponsorship match
  const sponsorJob = {
    match: {
      eligibility: [{criterion: 'Sponsorship', status: 'matches', quote: 'Visa sponsorship is available for qualified applicants'}]
    }
  };
  const goodSponsor = eligibilityBadges(sponsorJob, {needs_sponsorship: true});
  assert.ok(goodSponsor.some(b => b.type === 'visa' && b.status === 'match'));

  // 3. Citizenship requirement
  const defenseJob = {
    description: 'Must be a U.S. Citizen due to government contract specifications.'
  };
  const citizenBadges = eligibilityBadges(defenseJob, {});
  assert.ok(citizenBadges.some(b => b.type === 'citizenship' && b.status === 'warning'));

  // 4. Grad year match / conflict
  const gradJob = {
    match: {
      eligibility: [{criterion: 'Graduation window', status: 'conflict', explanation: 'Requires graduation between 2026 and 2027'}]
    }
  };
  const gradBadges = eligibilityBadges(gradJob, {graduation_year: 2029});
  assert.ok(gradBadges.some(b => b.type === 'grad' && b.status === 'conflict'));
});

test('kanbanColumns groups applications into pipeline stages and closed', () => {
  const apps = [
    { id: '1', title: 'Job 1', company: 'A', status: 'saved' },
    { id: '2', title: 'Job 2', company: 'B', status: 'preparing' },
    { id: '3', title: 'Job 3', company: 'C', status: 'applied' },
    { id: '4', title: 'Job 4', company: 'D', status: 'interview' },
    { id: '5', title: 'Job 5', company: 'E', status: 'offer' },
    { id: '6', title: 'Job 6', company: 'F', status: 'rejected' },
    { id: '7', title: 'Job 7', company: 'G', status: 'dismissed' },
  ];
  const cols = kanbanColumns(apps);
  assert.equal(cols.saved.jobs.length, 2); // 'saved' and 'preparing'
  assert.equal(cols.applied.jobs.length, 1);
  assert.equal(cols.interview.jobs.length, 1);
  assert.equal(cols.offer.jobs.length, 1);
  assert.equal(cols.closed.jobs.length, 2); // 'rejected' and 'dismissed'
});

test('detectOccupation identifies occupation and getBeeMascotSvg generates distinctive SVG', async () => {
  const { detectOccupation, getBeeMascotSvg, BEE_PERSONAS } = await import('../hives/careers/static/logic.mjs');
  assert.equal(detectOccupation('Software Engineer Intern', 'Computer Science', 'Python, React'), 'code');
  assert.equal(detectOccupation('Machine Learning Researcher', 'Data Science', 'PyTorch, SQL'), 'data');
  assert.equal(detectOccupation('Lab Assistant', 'Biochemistry', 'PCR, Gel electrophoresis'), 'research');
  assert.equal(detectOccupation('Product Designer', 'Interaction Design', 'Figma, Prototyping'), 'design');
  assert.equal(detectOccupation('Investment Banking Analyst', 'Finance', 'Excel, Financial Modeling'), 'business');
  assert.equal(detectOccupation('Clinical Research Intern', 'Nursing / Pre-Med', 'Patient Care'), 'health');
  assert.equal(detectOccupation('Explorer', 'General Studies', ''), 'scholar');

  // Verify mascot SVGs
  assert.equal(BEE_PERSONAS.length, 7);
  for (const p of BEE_PERSONAS) {
    const svg = getBeeMascotSvg(p.id, 48);
    assert.ok(svg.startsWith('<svg'));
    assert.ok(svg.includes(p.name));
    assert.ok(svg.endsWith('</svg>'));
  }
});

import { readFile as fsReadFile } from 'node:fs/promises';
const fs = { readFile: fsReadFile };

test('interview dialog element exists in page.html', async () => {
  const html = await fs.readFile(new URL('../hives/careers/page.html', import.meta.url), 'utf8');
  assert.ok(html.includes('id="interview-dialog"'), 'interview-dialog must exist in page.html');
});

test('interview dialog element exists in account.html', async () => {
  const html = await fs.readFile(new URL('../hives/careers/account.html', import.meta.url), 'utf8');
  assert.ok(html.includes('id="interview-dialog"'), 'interview-dialog must exist in account.html');
});

test('interview-dialog id is unique in page.html', async () => {
  const html = await fs.readFile(new URL('../hives/careers/page.html', import.meta.url), 'utf8');
  const matches = [...html.matchAll(/id="interview-dialog"/g)];
  assert.strictEqual(matches.length, 1, 'interview-dialog id must appear exactly once in page.html');
});

test('instant apply dialog element exists in page.html and account.html', async () => {
  const pageHtml = await fs.readFile(new URL('../hives/careers/page.html', import.meta.url), 'utf8');
  const accHtml = await fs.readFile(new URL('../hives/careers/account.html', import.meta.url), 'utf8');
  assert.ok(pageHtml.includes('id="instant-apply-dialog"'), 'instant-apply-dialog must exist in page.html');
  assert.ok(accHtml.includes('id="instant-apply-dialog"'), 'instant-apply-dialog must exist in account.html');
});

test('global practice button exists outside application cards in page.html', async () => {
  const pageHtml = await fs.readFile(new URL('../hives/careers/page.html', import.meta.url), 'utf8');
  assert.ok(pageHtml.includes('id="global-practice-btn"'), 'global-practice-btn must exist in page.html');
});

test('header navigation tabs and practice dropdown exist in page.html and account.html', async () => {
  const pageHtml = await fs.readFile(new URL('../hives/careers/page.html', import.meta.url), 'utf8');
  const accHtml = await fs.readFile(new URL('../hives/careers/account.html', import.meta.url), 'utf8');
  assert.ok(pageHtml.includes('id="practice-dropdown-btn"'), 'practice-dropdown-btn in page.html');
  assert.ok(pageHtml.includes('id="practice-menu-sandbox"'), 'practice-menu-sandbox in page.html');
  assert.ok(pageHtml.includes('id="nav-pipeline-tab"'), 'nav-pipeline-tab in page.html');
  assert.ok(accHtml.includes('id="practice-dropdown-btn"'), 'practice-dropdown-btn in account.html');
  assert.ok(accHtml.includes('id="practice-menu-sandbox"'), 'practice-menu-sandbox in account.html');
});

test('sandbox dialog element exists in page.html and account.html', async () => {
  const pageHtml = await fs.readFile(new URL('../hives/careers/page.html', import.meta.url), 'utf8');
  const accHtml = await fs.readFile(new URL('../hives/careers/account.html', import.meta.url), 'utf8');
  assert.ok(pageHtml.includes('id="sandbox-dialog"'), 'sandbox-dialog in page.html');
  assert.ok(accHtml.includes('id="sandbox-dialog"'), 'sandbox-dialog in account.html');
});
