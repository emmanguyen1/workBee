import {parseSkills, apiError, assessmentLabel, relativeTime, comparisonPreferences, mergeProfileSkills, preferenceChoices, applicationsCSV} from './logic.mjs';

const $=id=>document.getElementById(id), make=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e};
let offset=0,total=0,requestId=0;
let accountUser=null,accountRevision=0,authGeneration=0,savedProfile={},hasAccountEdits=false;
const isAccountPage=document.body.dataset.page==='account';
const PAGE=30,PROFILE_KEY='hivework.careers.profile',SAVED_KEY='hivework.careers.applications';
function read(key,fallback){try{return JSON.parse(localStorage.getItem(key))??fallback}catch{return fallback}}
let saved=read(SAVED_KEY,{});if(!saved||typeof saved!=='object'||Array.isArray(saved))saved={};
const choices={career:[],field:[],company:[],country:[],region:[],workplace:[],role:[],'opportunity-type':[]};
const labels={career:'Any career fields',field:'Any industries',company:'Any employers',country:'Any countries',region:'Any states / provinces',workplace:'Any workplaces',role:'Any career stages','opportunity-type':'All current postings'};
function setChoices(id,values){choices[id]=[...new Set(values||[])];updateChoiceSummary(id);const box=$(id);if(box)for(const input of box.querySelectorAll('input[type=checkbox]'))input.checked=choices[id].includes(input.value)}
function updateChoiceSummary(id){const node=$(id);if(!node)return;const selected=choices[id],items=node._items||[];const names=selected.map(v=>items.find(item=>item.value===v)?.label||v);node.querySelector('summary span').textContent=names.length?names.length===1?names[0]:names.length+' selected':labels[id];node.querySelector('summary').title=names.join(', ')||labels[id]}
function multiOptions(id,items){
  const node=$(id);node._items=items;let menu=node.querySelector('.multi-menu');
  if(!menu){menu=make('div',undefined,'multi-menu');const search=make('input');search.type='search';search.placeholder='Find an option…';search.setAttribute('aria-label','Find '+labels[id].toLowerCase());search.oninput=()=>{for(const row of menu.querySelectorAll('.multi-option'))row.hidden=!row.textContent.toLowerCase().includes(search.value.toLowerCase())};const list=make('div',undefined,'multi-options'),clear=make('button','Clear selection','text-button');clear.type='button';clear.onclick=()=>{setChoices(id,[]);refreshFilters()};menu.append(search,list,clear);node.append(menu);node.addEventListener('toggle',()=>{if(node.open)for(const other of document.querySelectorAll('.multi-filter[open]'))if(other!==node)other.open=false});node.addEventListener('keydown',event=>{if(event.key==='Escape'){node.open=false;node.querySelector('summary').focus();event.stopPropagation()}})}
  const active=document.activeElement?.closest('.multi-options')===menu.querySelector('.multi-options')?document.activeElement.value:null;
  const all=[...items,...choices[id].filter(value=>!items.some(i=>i.value===value)).map(value=>({value,label:value+' (no current matches)'}))];
  menu.querySelector('.multi-options').replaceChildren(...all.map(item=>{const row=make('label',undefined,'multi-option'),input=make('input');input.type='checkbox';input.value=item.value;input.dataset.facet=id;input.checked=choices[id].includes(item.value);input.onchange=()=>{const values=new Set(choices[id]);if(input.checked)values.add(item.value);else values.delete(item.value);setChoices(id,[...values])};row.append(input,make('span',item.label));return row}));
  menu.querySelector('input[type=search]').dispatchEvent(new Event('input'));updateChoiceSummary(id);
  if(active)for(const input of menu.querySelectorAll('input[type=checkbox]'))if(input.value===active)input.focus();
}
document.addEventListener('click',event=>{for(const node of document.querySelectorAll('.multi-filter[open]'))if(!node.contains(event.target))node.open=false});
const bool=id=>$(id).value===''?null:$(id).value==='true';
function profile(){return {skills:parseSkills($('skills').value),graduation_year:$('graduation').value?Number($('graduation').value):null,gpa:$('gpa').value!==''?Number($('gpa').value):null,enrolled:bool('enrolled'),needs_sponsorship:bool('sponsorship'),location:$('location').value.trim(),degree_level:$('degree').value,degree_status:$('degree-status').value,major:$('major').value.trim(),experience_years:$('experience').value!==''?Number($('experience').value):null,available_from:$('available-from').value||null,available_until:$('available-until').value||null}}
function fill(p){$('skills').value=(p.skills||[]).map(s=>s.skill+(s.evidence?' | '+s.evidence:'')).join('\n');$('graduation').value=p.graduation_year||'';$('gpa').value=p.gpa??'';$('enrolled').value=p.enrolled==null?'':String(p.enrolled);$('sponsorship').value=p.needs_sponsorship==null?'':String(p.needs_sponsorship);$('location').value=p.location||'';$('degree').value=p.degree_level||'';$('degree-status').value=p.degree_status||'';$('major').value=p.major||'';$('experience').value=p.experience_years??'';$('available-from').value=p.available_from||'';$('available-until').value=p.available_until||''}
function preferences(){return {technical_only:false,current_only:true,include_programs:false,student_year:'all',program_status:'all',opportunity_type:'all',role_type:'all',career_field:'all',company:'',country:'',region:'',workplace:'all',sectors:choices.field,career_fields:choices.career,companies:choices.company,countries:choices.country,regions:choices.region,workplaces:choices.workplace,role_types:choices.role,opportunity_types:choices['opportunity-type'],pay:$('pay-filter').value,commitments:$('commitment').value?[$('commitment').value]:[],closing_within_days:Number($('closing-window').value),recent_days:Number($('recent-window').value),query:$('query').value,sort:$('sort').value,comparable_only:$('comparable-only').checked}}
function fillPreferences(p){$('pay-filter').value=p.pay||'all';$('commitment').value=p.commitments?.[0]||'';$('closing-window').value=String(p.closing_within_days||0);$('recent-window').value=String(p.recent_days||0);$('comparable-only').checked=Boolean(p.comparable_only);$('query').value=p.query||'';$('sort').value=p.sort==='fit'?'relevance':p.sort||'relevance';for(const [key,id,legacy] of [['career_fields','career','career_field'],['sectors','field','sector'],['companies','company','company'],['countries','country','country'],['regions','region','region'],['workplaces','workplace','workplace'],['role_types','role','role_type'],['opportunity_types','opportunity-type','opportunity_type']])setChoices(id,preferenceChoices(p,key,legacy))}
function identity(){return {display_name:$('display-name').value.trim(),school:$('profile-school').value.trim(),headline:$('profile-tagline').value.trim()}}
function identityView(user){const name=user?.display_name||user?.username||'',initials=name.split(/\s+/).slice(0,2).map(p=>p[0]).join('').toUpperCase()||'wB';$('nav-avatar').textContent=initials;$('profile-avatar').textContent=initials;$('nav-account-label').textContent=name||'Sign in / Create profile';$('profile-display-name').textContent=name;$('profile-handle').textContent=user?'@'+user.username:'';$('profile-headline').textContent=user?.headline||'';$('workspace-summary').textContent=user?'Your profile and saved preferences':'Sign in to save your profile & preferences'}
async function accountFetch(path,method='GET',body){const response=await fetch('/api/account/'+path,{method,credentials:'same-origin',headers:body?{'Content-Type':'application/json'}:{},...(body?{body:JSON.stringify(body)}:{})});const data=await response.json();if(!response.ok)throw new Error(apiError(data,'Check the account fields and try again.'));return data}
function accountView(data,restore=true){accountUser=data.user;savedProfile=data.profile||{};hasAccountEdits=false;if(isAccountPage){$('account-private').classList.toggle('hidden',!accountUser);$('workspace').open=true;if(accountUser){loadSavedApplications();if(location.hash==='#resume')$('resume').open=true}}accountRevision=data.revision||0;$('account-actions').classList.toggle('hidden',!accountUser);$('auth-details').classList.toggle('hidden',!!accountUser);$('save').disabled=!!accountUser;$('identity-panel').classList.toggle('hidden',!accountUser);identityView(accountUser);for(const [key,id] of [['display_name','display-name'],['school','profile-school'],['headline','profile-tagline']])$(id).value=accountUser?.[key]||'';if(accountUser){$('account-state').textContent='Signed in as '+accountUser.username+'. Save profile and filters explicitly; application status changes sync automatically. Raw resumes are not saved.';saved=data.applications||{};if(restore){fill(data.profile||{});fillPreferences(data.preferences||{})}}else{$('account-state').textContent='Guest mode. Create an account to save your profile, preferences, and application statuses across devices.'}if(isAccountPage&&accountUser){try{const pending=sessionStorage.getItem('workbee.pending.preferences');if(pending){sessionStorage.removeItem('workbee.pending.preferences');fillPreferences(JSON.parse(pending));hasAccountEdits=true;$('account-message').textContent='Search preferences brought from Explore. Save them to your account when ready.'}}catch{}}}
if(!isAccountPage)$('edit-preferences').onclick=()=>{try{sessionStorage.setItem('workbee.pending.preferences',JSON.stringify(preferences()))}catch{}};
$('account-toggle').onclick=event=>{if(!isAccountPage)return;event.preventDefault();$('workspace').open=true;$('workspace').scrollIntoView({behavior:'smooth',block:'start'});if(!accountUser){$('auth-details').open=true;$('account-username').focus()}else $('display-name').focus()};
$('auth-mode').onchange=()=>{$('account-password').autocomplete=$('auth-mode').value==='register'?'new-password':'current-password'};
$('auth-form').onsubmit=async event=>{event.preventDefault();++authGeneration;$('auth-submit').disabled=true;$('account-message').textContent='Connecting…';try{const data=await accountFetch($('auth-mode').value,'POST',{username:$('account-username').value,password:$('account-password').value});accountView(data);$('auth-details').open=false;$('account-message').textContent=data.revision===0?'Account ready. Save your profile and filters to sync your current work.':'Saved account data loaded.';offset=0;await load()}catch(error){$('account-message').textContent=error.message}finally{$('account-password').value='';$('auth-submit').disabled=false}};
async function saveAccount(){const generation=authGeneration,owner=accountUser?.username;if(!owner){$('account-message').textContent='Sign in to save your profile.';return false}$('save-account').disabled=true;try{const data=await accountFetch('state','PUT',{identity:identity(),profile:checkedProfile(),preferences:preferences(),revision:accountRevision});if(generation!==authGeneration||accountUser?.username!==owner)return false;accountRevision=data.revision;accountUser=data.user;savedProfile=data.profile;identityView(accountUser);hasAccountEdits=false;$('account-message').textContent='Your profile and preferences are saved. They will load across sessions and devices.';if('BroadcastChannel' in window){const channel=new BroadcastChannel('workbee-account');channel.postMessage({type:'saved'});channel.close()}return true}catch(error){$('account-message').textContent=error.message;return false}finally{$('save-account').disabled=false}}
$('save-account').onclick=saveAccount;
$('reload-account').onclick=async()=>{try{const data=await accountFetch('session');accountView(data);if(!data.user){fill({});fillPreferences({});saved={}}$('account-message').textContent=data.user?'Saved account profile, filters, and application statuses loaded.':'Session expired. Sign in again.';offset=0;await load()}catch(error){$('account-message').textContent=error.message}};
$('logout-account').onclick=async()=>{try{await accountFetch('logout','POST');++authGeneration;accountView({user:null});fill({});fillPreferences({});clearImport();saved=read(SAVED_KEY,{});$('account-message').textContent='Signed out. Account data remains saved on the server.';offset=0;await load()}catch(error){$('account-message').textContent=error.message}};
$('save').onclick=()=>{try{localStorage.setItem(PROFILE_KEY,JSON.stringify(profile()));$('profile-message').textContent='Profile saved on this browser.'}catch{$('profile-message').textContent='Browser storage unavailable; profile remains in this page only.'}};
$('clear').onclick=()=>{try{localStorage.removeItem(PROFILE_KEY);localStorage.removeItem(SAVED_KEY)}catch{}saved={};fill({});clearImport();$('profile-message').textContent=accountUser?'Device data and current form cleared. Saved account data is unchanged; reload it above.':'Profile, resume draft, and application statuses cleared from this device.';offset=0;load()};
let importVersion=0;
function clearImport(){importVersion++;$('resume-file').value='';$('resume-text').value='';$('resume-review').classList.add('hidden');$('review-confirm').checked=false;$('apply-resume').disabled=true;$('resume-warnings').replaceChildren();$('resume-sources').replaceChildren();for(const id of ['draft-skills','draft-degree','draft-degree-status','draft-major','draft-graduation','draft-gpa'])$(id).value='';$('resume-message').textContent='';$('extract-resume').disabled=false}
$('discard-resume').onclick=clearImport;
$('review-confirm').onchange=()=>{$('apply-resume').disabled=!$('review-confirm').checked};
$('extract-resume').onclick=async()=>{
 const version=++importVersion,file=$('resume-file').files[0],text=$('resume-text').value.trim();$('resume-review').classList.add('hidden');$('review-confirm').checked=false;$('apply-resume').disabled=true;$('extract-resume').disabled=true;$('resume-message').className='notice';$('resume-message').textContent='Extracting a review draft…';
 try{if(file&&text)throw new Error('Choose a file or paste text, then clear the other input.');if(!file&&!text)throw new Error('Choose a resume file or paste your resume text first.');const format=file?file.name.split('.').pop().toLowerCase():'txt';if(!['pdf','docx','txt'].includes(format))throw new Error('Use a PDF, DOCX, or UTF-8 text file.');if(file&&file.size>4*1024*1024)throw new Error('Resume must be 4 MB or smaller.');const res=await fetch('/api/careers/resume?format='+format,{method:'POST',headers:{'Content-Type':'application/octet-stream'},body:file||new Blob([text],{type:'text/plain'})});const data=await res.json();if(!res.ok)throw new Error(apiError(data,'Could not extract this resume. Try pasting the text instead.'));if(version!==importVersion)return;const draft=data.draft;$('resume-quality').textContent=data.summary?data.summary.with_examples+' skills with project/work/course examples · '+data.summary.listed_only+' listed-only skills. Review the evidence before matching.':'';$('draft-skills').value=draft.skills.map(s=>s.skill+' | '+s.evidence.replaceAll('\n',' ')).join('\n');$('draft-degree').value=draft.degree_level||'';$('draft-degree-status').value=draft.degree_status||'';$('draft-major').value=draft.major||'';$('draft-graduation').value=draft.graduation_year||'';$('draft-gpa').value=draft.gpa??'';$('resume-warnings').replaceChildren(...data.warnings.map(w=>make('li',w)));$('resume-sources').replaceChildren(...data.fields.map(f=>make('p',f.field+': '+f.quote)));$('resume-review').classList.remove('hidden');$('resume-message').textContent='Draft ready: '+draft.skills.length+' suggested skills. Your matching profile has not changed.';$('review-title').focus();
 }catch(error){if(version===importVersion){$('resume-message').textContent=error.message;$('resume-message').className='notice error'}}finally{if(version===importVersion)$('extract-resume').disabled=false}
};
$('apply-resume').onclick=()=>{if(!$('review-confirm').checked)return;for(const id of ['draft-skills','draft-major','draft-graduation','draft-gpa'])if(!$(id).reportValidity())return;try{const merged=mergeProfileSkills(parseSkills($('skills').value),parseSkills($('draft-skills').value),$('resume-apply-mode').value==='replace');$('skills').value=merged.map(s=>s.skill+(s.evidence?' | '+s.evidence:'')).join('\n')}catch(error){$('resume-message').textContent=error.message;return};for(const [from,to] of [['draft-degree','degree'],['draft-degree-status','degree-status'],['draft-major','major'],['draft-graduation','graduation'],['draft-gpa','gpa']])if($(from).value!=='')$(to).value=$(from).value;clearImport();$('profile-message').textContent=accountUser?'Reviewed draft applied. Save profile & filters to your account to keep it.':'Reviewed draft applied. Save on device if you want to keep it.';hasAccountEdits=true;if(!isAccountPage)applyProfile()};
function section(title){const d=make('details');d.append(make('summary',title));return d}
let fieldLabels={},sectorLabels={};
let visibleJobs = [];
let searchController = null;
const dialog = $('opportunity-dialog');
if (!isAccountPage&&window.matchMedia('(max-width:860px)').matches) $('profile-drawer').open = false;

function icon(name, size = 14) {
  const paths = {
    pin: ['M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 1 1 16 0Z', 'M15 10a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z'],
    clock: ['M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0Z', 'M12 6v6l4 2'],
  };
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  for (const [key, value] of Object.entries({width:size, height:size, viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', 'stroke-width':'1.7', 'stroke-linecap':'round', 'stroke-linejoin':'round', 'aria-hidden':'true'})) svg.setAttribute(key, value);
  for (const d of paths[name] || []) {const path = document.createElementNS(svg.namespaceURI, 'path'); path.setAttribute('d', d); svg.append(path);}
  return svg;
}

function logo(job) {
  const box = make('div', undefined, 'company-logo');
  const initials = make('span', job.company_initials || job.company.split(' ').slice(0,2).map(s=>s[0]).join('').toUpperCase());
  initials.setAttribute('aria-hidden','true'); box.append(initials);
  if (job.company_logo_url) {
    try {
      const url = new URL(job.company_logo_url,location.origin);
      if ((url.protocol === 'https:' && url.hostname === 'www.google.com') || (url.origin === location.origin && url.pathname.startsWith('/careers/logos/'))) {
        const img = make('img'); img.alt = job.company + ' logo'; img.loading='lazy'; img.decoding='async'; img.referrerPolicy='no-referrer'; img.src=url.href; img.onerror=()=>{if(!img.dataset.retry&&job.company_domain){img.dataset.retry='1';img.src='https://www.google.com/s2/favicons?domain='+encodeURIComponent(job.company_domain)+'&sz=128'}else img.hidden=true}; box.append(img);
      }
    } catch {}
  }
  return box;
}

function facets(data) {
  sectorLabels=Object.fromEntries(data.facets.sectors.map(s=>[s.value,s.label]));
  fieldLabels=Object.fromEntries(data.facets.fields.map(f=>[f.value,f.label]));
  multiOptions('career',[...data.facets.fields].sort((a,b)=>a.label.localeCompare(b.label)).map(f=>({value:f.value,label:f.label+' ('+f.count+')'})));
  multiOptions('field',[...data.facets.sectors].sort((a,b)=>a.label.localeCompare(b.label)).map(f=>({value:f.value,label:f.label+' ('+f.count+')'})));
  const names={internship:'Internships & co-ops',job:'Jobs',research:'Research & fellowships',lab:'Labs & scientific work',program:'First & second year postings'};
  multiOptions('opportunity-type',Object.entries(names).map(([value,label])=>({value,label:label+' ('+(data.facets.opportunity_types[value]||0)+')'})));
  multiOptions('role',[['early_career','Early career'],['internship','Internships & co-ops'],['new_grad','New graduate'],['entry_level','Junior & entry level'],['apprenticeship','Apprenticeships'],['other','Other / unspecified']].map(([value,label])=>({value,label})));
  multiOptions('workplace',[['remote','Remote'],['hybrid','Hybrid'],['onsite','On-site'],['unspecified','Not specified']].map(([value,label])=>({value,label})));
  multiOptions('company',data.facets.companies.map(c=>({value:c,label:c})));
  multiOptions('country',[...data.facets.countries,{value:'unknown',label:'Country not specified'}]);
  multiOptions('region',data.facets.regions.filter(r=>!choices.country.length||choices.country.includes(r.country)).map(r=>({value:r.value,label:r.label+' · '+r.country})));
  $('preferred-regions').replaceChildren(...[...data.facets.countries,...data.facets.regions].map(place=>{const node=make('option');node.value=place.label;return node}));
  $('coverage').replaceChildren(...[[data.catalog_total,'Current employer postings'],[data.early_career_total,'Early-career opportunities'],[data.facets.companies.length,'Employers to explore'],[data.facets.sectors.filter(s=>s.count>0).length,'Industries to explore']].map(([number,label])=>{const node=make('span');node.append(make('strong',number.toLocaleString()),document.createTextNode(label));return node}));
}

function tags(job) {
  const node=make('div',undefined,'tags');
  const stage={internship:'Internship / co-op',new_grad:'New graduate',entry_level:'Entry level',apprenticeship:'Apprenticeship',other:'Other career levels'}[job.role_type];
  node.append(make('span',stage||job.role_type,'tag stage'));
  for(const sector of job.sectors||[])node.append(make('span',sectorLabels[sector]||sector,'tag field'));
  if(job.workplace!=='unspecified')node.append(make('span',job.workplace==='onsite'?'On-site':job.workplace[0].toUpperCase()+job.workplace.slice(1),'tag remote'));
  if(job.opportunity_types?.includes('lab'))node.append(make('span','Lab / scientific work','tag research'));
  if(job.deadline_info?.date)node.append(make('span','Apply by '+job.deadline_info.date,'tag deadline'));
  if(job.opportunity_types?.includes('research'))node.append(make('span','Research / fellowship','tag research'));
  if(job.facts?.pay_status&&job.facts.pay_status!=='unknown')node.append(make('span',job.facts.pay_status==='paid'?'Explicitly paid':'Unpaid','tag pay'));
  for(const year of job.student_audience?.years||[])node.append(make('span',year===1?'Mentions first-year':'Mentions second-year','tag'));
  if(job.terms?.length)node.append(make('span',job.terms.join(' · '),'tag'));
  return node;
}

function matchBox(result, expanded=false) {
  const assessed=result.score!=null;
  const box=make('div',undefined,'match-box'+(!assessed?' unavailable':result.score<40?' low':''));
  const head=make('div',undefined,'match-head'); head.append(make('span',assessed?'Skill coverage':assessmentLabel(result)));
  if(assessed){head.append(make('strong',result.score+'%','match-score'));box.append(head);const progress=make('progress');progress.max=100;progress.value=result.score;progress.setAttribute('aria-label',result.score+' percent skill coverage');box.append(progress)} else box.append(head);
  const supported=result.checks.filter(c=>c.status==='supported'&&c.kind!=='mentioned');
  const missing=result.checks.filter(c=>c.status==='no_evidence'&&c.kind==='required');
  let caption;
  if(result.assessment==='requirements_unavailable') caption='Open the posting, then paste its requirements to compare your profile.';
  else if(result.assessment==='needs_profile')caption='Add your skills on your account page to unlock a comparison.';
  else if(result.assessment==='unrecognized_requirements')caption='No supported skill requirements recognized. Review the full description.';
  else caption=supported.length+' skill group'+(supported.length===1?'':'s')+' supported'+(missing.length?' · '+missing.length+' required group'+(missing.length===1?'':'s')+' to review':'');
  box.append(make('p',caption,'match-caption'));
  if(supported.length){const chips=make('div',undefined,'skill-tags');for(const c of supported.slice(0,expanded?12:3))chips.append(make('span','✓ '+c.evidence.map(e=>e.skill).join(' / '),'skill-tag'));box.append(chips)}
  else if(assessed&&missing.length){const chips=make('div',undefined,'skill-tags');for(const c of missing.slice(0,3))chips.append(make('span',c.skills.join(' or '),'skill-tag missing'));box.append(chips)}
  return box;
}

function applicationLink(job,label='Apply ↗') {
  if(job.availability?.state==='removed')return null;
  try{const url=new URL(job.apply_url);if(url.protocol==='https:'){const node=make('a',label,'button-link');node.href=url.href;node.target='_blank';node.rel='noopener noreferrer';return node}}catch{}
  return null;
}

function tracking(job) {
  const row=make('div',undefined,'card-tracking'),select=make('select');
  const label=make('label','Application status'); label.htmlFor='status-'+job.id;
  select.id='status-'+job.id; select.setAttribute('aria-label','Application status for '+job.title+' at '+job.company);
  for(const [value,text] of [['','Not saved'],['saved','Saved'],['preparing','Preparing'],['applied','Applied'],['interview','Interview'],['offer','Offer'],['rejected','Rejected'],['dismissed','Dismissed']]){const option=make('option',text);option.value=value;select.append(option)}
  select.value=saved[job.id]||(job.alternate_ids||[]).map(id=>saved[id]).find(Boolean)||'';
  select.onchange=async()=>{
    const before=saved[job.id]||'',value=select.value,owner=accountUser?.username,generation=authGeneration;select.disabled=true;
    try{if(owner)await accountFetch('applications/'+encodeURIComponent(job.id),'PUT',{status:value});if(generation!==authGeneration)return;if(value)saved[job.id]=value;else delete saved[job.id];if(!owner)localStorage.setItem(SAVED_KEY,JSON.stringify(saved));if(isAccountPage)await loadSavedApplications()}
    catch(error){if(generation!==authGeneration)return;if(before)saved[job.id]=before;else delete saved[job.id];select.value=before;$('account-message').textContent=error.message||'Could not save this application status.'}
    finally{select.disabled=false}
  };
  row.append(label,select);return row;
}

function card(job) {

  const article=make('article',undefined,'job'),company=make('div',undefined,'company-row'),identity=make('div',undefined,'company-identity');
  identity.append(make('div',job.company,'company-name'));
  const source=make('div',undefined,'source-tag'+(job.listing_status==='community_listed'?' community':''));source.append(make('span'),document.createTextNode(job.listing_status==='community_listed'?'Community discovery':'Employer feed'));identity.append(source);company.append(logo(job),identity);article.append(company);
  const heading=make('h3'),title=make('button',job.title,'job-title');title.type='button';title.onclick=()=>showDetails(job);heading.append(title);article.append(heading);
  const location=make('div',undefined,'job-location');location.append(icon('pin'),make('span',(job.locations||[]).join(' · ')||job.location||'Location not specified'));article.append(location,tags(job),matchBox(job.match));
  if(job.match.has_conflict)article.append(make('p','Possible qualification conflict · review before applying','notice conflict'));
  const actions=make('div',undefined,'card-actions'),details=make('button','View match & details','secondary');details.type='button';details.onclick=()=>showDetails(job);actions.append(details);const apply=applicationLink(job);if(apply)actions.append(apply);const compare=make('button',compared.has(job.id)?'In shortlist ✓':'Compare','secondary compare-toggle');compare.type='button';compare.setAttribute('aria-pressed',String(compared.has(job.id)));compare.onclick=()=>toggleCompare(job);actions.append(compare);article.append(actions,tracking(job));
  if(job.facts?.pay_quote)article.append(make('p',job.facts.pay_quote.slice(0,200)+(job.facts.pay_quote.length>200?'…':''),'decision-facts'));
  if(job.availability)article.append(availabilityBox(job));
  const stale=Date.now()-Date.parse(job.last_seen)>30*60000;
  const fresh=make('div',undefined,'job-freshness'+(stale?' stale':''));fresh.append(icon('clock',11),document.createTextNode(relativeTime(job.last_seen).replace('Source checked','Last seen in source')));article.append(fresh);return article;
}

function availabilityBox(job, interactive=false) {
  const status=job.availability||{state:'stale',label:'Availability not checked'},box=make('div',undefined,'availability '+status.state);
  box.append(make('strong',status.label));
  if(status.checked_at){const time=make('time',relativeTime(status.checked_at));time.dateTime=status.checked_at;time.title=new Date(status.checked_at).toLocaleString();box.append(time)}
  if(interactive){
    box.append(make('p',status.note||'Confirm application availability on the employer website.','notice'));
    if(status.verification_supported){
      const button=make('button','Check source now','secondary');button.type='button';const message=make('p','','notice');message.setAttribute('role','status');
      button.onclick=async()=>{button.disabled=true;message.textContent='Checking the configured source feed…';try{
        const response=await fetch('/api/careers/verify',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({job_id:job.id})});const result=await response.json();if(!response.ok)throw new Error(apiError(result));job.availability=result;
        $('jobs').replaceChildren(...visibleJobs.map(card));
        const updated=availabilityBox(job,true);box.replaceWith(updated);
        const actions=document.querySelector('#dialog-content [data-application-actions]');if(actions){const link=applicationLink(job,'Open employer application ↗');actions.replaceChildren(...(link?[link]:[]));}
      }catch(error){message.textContent=error.message}finally{button.disabled=false}};
      box.append(button,message);
    }
  }
  return box;
}

function renderMatchDetails(node,result) {
  node.replaceChildren(make('h3','How your profile compares'),matchBox(result,true));
  const breakdown=result.breakdown;
  if(breakdown){
    const explanation=make('div',undefined,'score-explanation');explanation.append(make('h3','Why this score?'));
    for(const [key,label] of [['required','Required skill groups'],['preferred','Preferred skill groups']]){const value=breakdown[key];explanation.append(make('p',label+': '+value.matched+' / '+value.total+' supported'));}
    explanation.append(make('p','Required groups count twice; preferred groups count once. Contextual mentions do not affect the score.','notice'));
    if(result.score!=null)explanation.append(make('p',breakdown.earned_weight+' of '+breakdown.total_weight+' weighted points = '+result.score+'% skill coverage.','score-formula'));
    if(breakdown.self_reported)explanation.append(make('p',breakdown.self_reported+' supported group(s) rely on skills listed without a project, coursework, or work example. These are self-reported, not verified.','notice unknown'));
    if(breakdown.missing_required.length)explanation.append(make('p','Required skills to review: '+breakdown.missing_required.join(' · '),'notice'));
    explanation.append(make('p','Eligibility checks are separate from the skill score. Missing profile information remains unknown; the parser may miss requirements.','notice'));
    node.append(explanation);
  }
  const summary=result.qualification_summary,stats=make('div',undefined,'qualification-stats');
  for(const [count,label] of [[summary.matched,'Matched checks'],[summary.conflicts,'Possible conflicts'],[summary.unclear,'Need clarification']]){const item=make('div');item.append(make('strong',count),document.createTextNode(label));stats.append(item)}node.append(stats);
  const skills=section('Skills & supporting evidence ('+result.checks.length+')');
  if(!result.checks.length)skills.append(make('p','No supported skill requirements recognized. Check the employer description.','notice muted'));
  for(const check of result.checks){const row=make('div',undefined,'check');row.append(make('strong',check.skills.join(' or ')+' · '+check.kind),make('div',check.status==='supported'?'Supported by your profile':'No profile evidence found',check.status==='supported'?'badge':'unknown'),make('p','Employer: '+check.quote,'quote'));for(const evidence of check.evidence)row.append(make('p','Your profile · '+evidence.skill+': '+evidence.text));skills.append(row)}
  skills.open=true;
  const qualifications=section('Education, eligibility & availability');qualifications.open=true;
  for(const check of result.eligibility){const row=make('div',undefined,'check'),label={matches:'Matched',conflict:'Possible conflict',unknown:'Needs clarification'}[check.status]||check.status;row.append(make('strong',check.criterion+' · '+label,check.status==='conflict'?'conflict':check.status==='unknown'?'unknown':''),make('p',(check.kind==='unspecified'?'Check: ':'Employer: ')+check.quote,'quote'));if(check.evidence)row.append(make('p','Your profile: '+check.evidence));row.append(make('p',check.explanation,'meta'));qualifications.append(row)}
  const next=section('Your next steps'),list=make('ul',undefined,'next-steps');for(const text of result.next_steps)list.append(make('li',text));next.append(list);
  node.append(skills,qualifications,next,make('p','Skill coverage measures supported skill groups, not your eligibility or likelihood of being hired.','summary-note'));
}

function showDetails(job) {

  const container=$('dialog-content'),header=make('div',undefined,'dialog-header'),heading=make('div',undefined,'dialog-heading');
  heading.append(make('div',job.company,'company-name'));const title=make('h2',job.title);title.id='opportunity-title';heading.append(title);
  const close=make('button','×','close-dialog');close.type='button';close.setAttribute('aria-label','Close opportunity details');close.onclick=()=>dialog.close();header.append(logo(job),heading,close);
  const body=make('div',undefined,'dialog-body');body.append(availabilityBox(job,true));body.append(tags(job),make('p',(job.locations||[]).join(' · ')||job.location||'Location not specified','muted'));
  const actions=make('div',undefined,'actions'),apply=applicationLink(job,'Open employer application ↗');actions.setAttribute('data-application-actions','');if(apply)actions.append(apply);body.append(actions);
  if(job.listing_status==='community_listed')body.append(make('p','Community-listed opportunity. Confirm that applications are open on the employer website.','notice unknown'));
  const references=[...(job.source_references||[]),...(job.source_url?[{url:job.source_url,label:job.attribution||'Source list'}]:[])];for(const reference of references){try{if(new URL(reference.url).protocol==='https:'){const link=make('a',reference.label,'notice');link.href=reference.url;link.target='_blank';link.rel='noopener noreferrer';body.append(link)}}catch{}}
  if(job.student_audience?.evidence?.length){const audience=section('Class-year wording in the posting');audience.open=true;for(const quote of job.student_audience.evidence)audience.append(make('p',quote,'quote'));audience.append(make('p','A class-year mention is not a complete eligibility decision. Review the full requirements.','notice'));body.append(audience)}
  if(job.facts?.pay_quote)body.append(make('p','Pay wording: '+job.facts.pay_quote,'quote'));
  if(job.facts?.commitments?.length)body.append(make('p','Commitment wording: '+job.facts.commitments.map(v=>v.replaceAll('_',' ')).join(' / '),'notice'));
  const deadline=job.deadline_info;if(deadline){body.append(make('p',deadline.date?'Application deadline: '+deadline.date+' · '+deadline.timezone_note:'Application deadline not provided; check the employer posting.','notice'));if(deadline.quote)body.append(make('p',deadline.quote,'quote'))}
  const comparison=make('div');renderMatchDetails(comparison,job.match);body.append(comparison);
  const manual=make('div',undefined,'manual-comparison');manual.append(make('h3',job.description?'Compare an updated employer description':'Compare the employer’s requirements'),make('p','Paste the requirements from the employer posting. We’ll compare them with your current profile. This text is used for this comparison only.'));
  const input=make('textarea');input.maxLength=100000;input.minLength=20;input.placeholder='Paste the actual qualifications, skills, and eligibility requirements…';input.setAttribute('aria-label','Employer requirements for comparison');
  const compare=make('button','Compare with my profile');compare.type='button';const message=make('p','','notice');message.setAttribute('role','status');
  compare.onclick=async()=>{
    compare.disabled=true;message.className='notice';message.textContent='Comparing requirements…';
    try{const current=checkedProfile();if(!current.skills.length&&!current.major&&!current.degree_level)throw new Error('Add skills or education to your profile first.');if(input.value.trim().length<20)throw new Error('Paste at least 20 characters of actual employer requirements.');const response=await fetch('/api/careers/match',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({profile:current,description:input.value.trim(),location:job.location||''})});const result=await response.json();if(!response.ok)throw new Error(apiError(result));renderMatchDetails(comparison,result);message.textContent='Compared with the requirements you supplied and your current profile. The original source listing is unchanged.';comparison.scrollIntoView({behavior:'smooth',block:'start'})}
    catch(error){message.textContent=error.message;message.className='notice error'}finally{compare.disabled=false}
  };
  manual.append(input,compare,message);body.append(manual);
  const description=section('Full employer description');description.append(make('p',job.description||'The source does not supply a full description. Open the employer posting and paste its requirements above for a comparison.','description'));body.append(description);
  container.replaceChildren(header,body);dialog.showModal();
}

dialog.addEventListener('click',event=>{if(event.target===dialog){const rect=dialog.getBoundingClientRect();if(event.clientX<rect.left||event.clientX>rect.right||event.clientY<rect.top||event.clientY>rect.bottom)dialog.close()}});

function checkedProfile() {
  const value=profile();
  if(value.available_from&&value.available_until&&value.available_until<value.available_from)throw new Error('Availability end must be on or after the start date.');
  const invalid=$('profile').querySelector(':invalid');
  if(invalid){const details=invalid.closest('details');if(details)details.open=true;$('profile-drawer').open=true;invalid.reportValidity();throw new Error('Check '+(invalid.labels?.[0]?.textContent||'the highlighted profile field')+'.');}
  return value;
}

async function applyProfile() {
  try{
    const value=checkedProfile();
    if(!value.skills.length&&!value.major&&!value.degree_level&&!value.graduation_year&&value.enrolled===null)throw new Error('Add at least one skill or your education details to compare opportunities.');
    const focus=comparisonPreferences(preferences(),value.skills.length>0);fillPreferences(focus);offset=0;if(isAccountPage){if(await saveAccount())location.href='/';return;}
    $('profile-message').className='notice';$('profile-message').textContent='Applying your profile and ranking opportunities…';
    if(await load()){$('profile-message').textContent='Profile applied. Results are sorted by fit.';$('results').scrollIntoView({behavior:'smooth',block:'start'});}
  }catch(error){$('profile-message').textContent=error.message;$('profile-message').className='notice error';$('profile-drawer').open=true}
}

function renderJobs(data) {
  visibleJobs=data.jobs;$('jobs').replaceChildren(...visibleJobs.map(card));
  if(!visibleJobs.length){const empty=make('div',undefined,'empty');empty.append(make('h3','No opportunities match this view'),make('p',$('comparable-only').checked?'Try another field or location, or turn off “With comparable skill requirements” to include other current employer postings.':'Try a broader search or clear your filters.'));const reset=make('button','Clear filters','secondary');reset.type='button';reset.onclick=resetFilters;empty.append(reset);$('jobs').append(empty)}
}

async function load() {
  let current;
  try{current=isAccountPage?{}:accountUser?savedProfile:{}}catch(error){$('profile-message').textContent=error.message;$('profile-message').className='notice error';return false}
  const id=++requestId;searchController?.abort();searchController=new AbortController();
  $('search').disabled=true;$('match-profile').disabled=true;$('match-profile').textContent='Comparing…';$('status').className='';$('status').textContent='Finding opportunities…';$('jobs').setAttribute('aria-busy','true');
  if(!$('jobs').children.length)for(let index=0;index<4;index++)$('jobs').append(make('div',undefined,'skeleton'));
  try{
    const response=await fetch('/api/careers/search',{method:'POST',headers:{'Content-Type':'application/json'},signal:searchController.signal,body:JSON.stringify({profile:current,...preferences(),offset,limit:PAGE})});
    const data=await response.json();if(!response.ok)throw new Error(apiError(data));if(id!==requestId)return false;
    total=data.total;facets(data);if(!isAccountPage)renderJobs(data);else $('account-preferences-status').textContent=total.toLocaleString()+' current postings match these preferences.';
    $('results-count').textContent=total.toLocaleString()+' current postings';
    const normalized=data.profile_skills||[];
    $('match-notice').classList.toggle('active',normalized.length>0);
    $('match-notice').textContent=normalized.length?`Comparing ${normalized.length} skills: ${normalized.slice(0,5).join(', ')}${normalized.length>5?'…':''}. ${$('comparable-only').checked?'Showing current postings with comparable requirements.':'Listings without requirements remain unscored.'}`:'Add your skills to see how you fit each opportunity. Unscored listings are not zero-percent matches.';
    $('sort-note').textContent=({newest:'Most recent employer publication where available; otherwise first seen in this catalog.',deadline:'Published closing dates first; missing deadlines are last. Confirm the cutoff on the employer page.',company:'Employers ordered alphabetically.',relevance:'Sorted by saved-profile coverage, qualifications, and supporting examples; possible conflicts last.'})[data.effective_sort];
    $('status').textContent=total.toLocaleString()+' current employer postings in this view';
    $('sources').replaceChildren();const sources=section('Source checks · '+data.boards.length+' feeds'),grid=make('div',undefined,'source-grid');for(const board of data.boards){const stale=!board.checked_at||Date.now()-Date.parse(board.checked_at)>30*60000;grid.append(make('div',board.company+': '+(board.error||(!board.checked_at?'Waiting for first check':relativeTime(board.checked_at))),'source'+(board.error||stale?' unknown':'')))}sources.append(grid);$('sources').append(sources);
    $('previous').disabled=offset===0;$('next').disabled=offset+PAGE>=total;$('page').textContent=total?`${offset+1}–${Math.min(offset+PAGE,total)} of ${total.toLocaleString()}`:'0 roles';
    return true;
  }catch(error){if(id!==requestId||error.name==='AbortError')return false;$('status').textContent=error.message;$('status').className='error';if(!visibleJobs.length)$('jobs').replaceChildren(make('p','Unable to load opportunities. Check the message above and retry.','empty'));return false}
  finally{if(id===requestId){$('search').disabled=false;$('match-profile').disabled=false;$('match-profile').textContent=isAccountPage?'Save profile & find matches →':'Match my profile →';$('jobs').setAttribute('aria-busy','false')}}
}

function resetFilters(){fillPreferences({});offset=0;load()}
$('profile').onsubmit=event=>{event.preventDefault();hasAccountEdits=true;if(!isAccountPage)applyProfile()};
$('identity-panel').addEventListener('input',()=>{hasAccountEdits=true;$('account-message').textContent='Unsaved profile changes. Choose Save profile & filters to account.'});
$('filters').addEventListener('change',()=>{hasAccountEdits=true;if(accountUser)$('account-message').textContent='Preferences changed. Save profile & filters to keep them across devices.'});
$('profile').addEventListener('input',()=>{hasAccountEdits=true;$('profile-message').className='notice';$('profile-message').textContent='Profile changed. Apply it to update your matches.'});
$('filters').onsubmit=event=>{event.preventDefault();refreshFilters()};
$('keyword-search').onsubmit=event=>{event.preventDefault();refreshFilters()};
let filterTimer;
function refreshFilters(){clearTimeout(filterTimer);offset=0;load()}
$('filters').addEventListener('change',event=>{if(event.target.dataset.facet==='country'&&choices.country.length)setChoices('region',choices.region.filter(r=>choices.country.includes(r.split('-')[0])));if(event.target.tagName==='SELECT'||event.target.type==='checkbox')refreshFilters()});
for(const id of ['query'])$(id).addEventListener('input',()=>{clearTimeout(filterTimer);filterTimer=setTimeout(refreshFilters,400);hasAccountEdits=true});
$('reset-filters').onclick=resetFilters;
$('previous').onclick=()=>{offset=Math.max(0,offset-PAGE);load()};
$('next').onclick=()=>{offset+=PAGE;load()};
let savedApplications=[],savedApplicationOwner=null;const compared=new Map();
function download(text,name,type){const url=URL.createObjectURL(new Blob([text],{type})),a=make('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
function toggleCompare(job){if(compared.has(job.id))compared.delete(job.id);else if(compared.size<3)compared.set(job.id,job);else{$('compare-message').textContent='Your shortlist has three opportunities. Remove one to compare another.';return}$('compare-message').textContent='';renderComparison();$('jobs').replaceChildren(...visibleJobs.map(card))}
function renderComparison(){if(isAccountPage)return;$('compare-tray').classList.toggle('hidden',!compared.size);$('compare-items').replaceChildren(...[...compared.values()].map(job=>{const item=make('article',undefined,'compare-item');item.append(make('strong',job.company),make('h4',job.title));const dl=make('dl');for(const [label,value] of [['Location',(job.locations||[]).join(' · ')||'Not specified'],['Workplace',job.workplace==='unspecified'?'Not specified':job.workplace],['Pay',job.facts?.pay_quote||'Not provided'],['Commitment',job.facts?.commitments?.map(v=>v.replaceAll('_',' ')).join(' / ')||'Not specified'],['Deadline',job.deadline_info?.date||'Not provided'],['Skill coverage',job.match.score==null?'Not assessed':job.match.score+'%']])dl.append(make('dt',label),make('dd',value));const remove=make('button','Remove','text-button');remove.onclick=()=>toggleCompare(job);item.append(dl,remove);return item}))}
if(!isAccountPage){$('clear-compare').onclick=()=>{compared.clear();renderComparison();$('jobs').replaceChildren(...visibleJobs.map(card))};for(const button of document.querySelectorAll('[data-path]'))button.onclick=()=>{fillPreferences({});const key=button.dataset.path;if(key==='internship')setChoices('opportunity-type',['internship']);if(key==='research')setChoices('opportunity-type',['research','lab']);if(key==='impact')setChoices('field',['nonprofit']);if(key==='part_time')$('commitment').value='part_time';refreshFilters();$('results').scrollIntoView({behavior:'smooth'})}}
function renderNextSteps(){const now=new Date(),today=[now.getFullYear(),String(now.getMonth()+1).padStart(2,'0'),String(now.getDate()).padStart(2,'0')].join('-'),upcoming=savedApplications.filter(j=>j.details?.follow_up&&!['rejected','dismissed','offer'].includes(j.status)).sort((a,b)=>a.details.follow_up.localeCompare(b.details.follow_up));$('next-steps').replaceChildren();if(upcoming.length){$('next-steps').append(make('h3','Your next small steps'));for(const job of upcoming.slice(0,8))$('next-steps').append(make('p',(job.details.follow_up<today?'Overdue · ':'')+job.details.follow_up+' · '+job.company+' — '+(job.details.next_action||job.title)));$('next-steps').append(make('p','Personal follow-up dates appear here when you visit. No email or background notifications are sent.','notice muted'))}}
function noteEditor(job){const editor=make('details',undefined,'note-editor');editor.append(make('summary','Notes & next step'));const values=job._draft||job.details||{},fields={};for(const [key,label,type] of [['notes','Private notes','textarea'],['next_action','Next action','input'],['follow_up','Follow-up date','date']]){const row=make('label',label),input=make(type==='textarea'?'textarea':'input');if(type==='date')input.type='date';else input.maxLength=key==='notes'?3000:200;input.value=values[key]||'';fields[key]=input;row.append(input);editor.append(row);input.oninput=()=>{job._draft={notes:fields.notes.value,next_action:fields.next_action.value,follow_up:fields.follow_up.value||null,revision:job._draft?.revision??job.details?.revision??0}}}const save=make('button','Save next step','secondary'),message=make('p',undefined,'notice');message.setAttribute('role','status');save.type='button';save.onclick=async()=>{const generation=authGeneration;save.disabled=true;try{const data=await accountFetch('application-details/'+encodeURIComponent(job.id),'PUT',{notes:fields.notes.value,next_action:fields.next_action.value,follow_up:fields.follow_up.value||null,revision:job._draft?.revision??job.details?.revision??0});if(generation!==authGeneration)return;job.details=data;delete job._draft;message.textContent='Notes and next step saved.';renderNextSteps()}catch(error){message.textContent=error.message}finally{save.disabled=false}};const discard=make('button','Discard unsaved notes','text-button');discard.type='button';discard.onclick=()=>{delete job._draft;for(const key of ['notes','next_action','follow_up'])fields[key].value=job.details?.[key]||'';message.textContent='Unsaved notes discarded. Reload applications to fetch changes from other devices.'};editor.append(save,discard,message);return editor}
function renderSavedApplications(){if(!isAccountPage)return;const stage=$('saved-stage').value,rows=savedApplications.filter(j=>stage==='all'||j.status===stage);$('saved-application-count').textContent=savedApplications.length+' tracked';renderNextSteps();$('saved-applications').replaceChildren(...rows.map(job=>{const card=make('article',undefined,'saved-application');card.append(make('strong',job.title),make('p',job.company,'muted'),make('p',job.open?'Saved posting · confirm current availability':'Archived or no longer in the source feed','notice'));const link=applicationLink(job,'View employer posting ↗');if(job.open&&link)card.append(link);card.append(tracking(job),noteEditor(job));return card}));if(!rows.length)$('saved-applications').append(make('p','No tracked applications in this stage. Save roles from the opportunities page to start.','notice muted'))}
async function loadSavedApplications(){if(!isAccountPage||!accountUser)return;const generation=authGeneration,owner=accountUser.username;try{const data=await accountFetch('applications');if(generation!==authGeneration)return;const drafts=new Map(savedApplicationOwner===owner?savedApplications.filter(j=>j._draft).map(j=>[j.id,j._draft]):[]);savedApplications=data.applications.map(j=>({...j,...(drafts.has(j.id)?{_draft:drafts.get(j.id)}:{})}));savedApplicationOwner=owner;renderSavedApplications();$('saved-message').textContent='Application stages save automatically. Save notes and next steps explicitly.'}catch(error){$('saved-message').textContent=error.message}}
if(isAccountPage){$('saved-stage').onchange=renderSavedApplications;$('reload-applications').onclick=loadSavedApplications;$('export-applications').onclick=()=>download(applicationsCSV(savedApplications),'workbee-applications.csv','text/csv;charset=utf-8')}
async function refreshAccount(){const generation=authGeneration;try{const data=await accountFetch('session');if(generation!==authGeneration)return;const changed=data.user?.username!==accountUser?.username||data.revision!==accountRevision;if(changed){if(isAccountPage&&hasAccountEdits&&data.user?.username===accountUser?.username){$('account-message').textContent='Your saved profile changed elsewhere. Reload saved account data when ready.';return}if(data.user?.username!==accountUser?.username)++authGeneration;if(!isAccountPage){compared.clear();renderComparison()}accountView(data);if(!data.user){fill({});savedProfile={};saved={}}if(!isAccountPage||accountUser)await load()}else if(data.user){saved=data.applications||{};if(isAccountPage)await loadSavedApplications();else if(visibleJobs.length)$('jobs').replaceChildren(...visibleJobs.map(card))}}catch{}}
window.addEventListener('focus',refreshAccount);
if('BroadcastChannel' in window){const channel=new BroadcastChannel('workbee-account');channel.onmessage=event=>{if(event.data?.type==='saved')refreshAccount()}}
async function start(){const generation=authGeneration;try{const data=await accountFetch('session');if(generation===authGeneration)accountView(data)}catch(error){if(generation===authGeneration)$('account-message').textContent='Account storage is unavailable. You can continue in guest mode.'}if(generation===authGeneration&&(!isAccountPage||accountUser))await load()}start();
