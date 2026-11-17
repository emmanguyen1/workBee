import {parseSkills, apiError, assessmentLabel, relativeTime, freshnessWindow, comparisonPreferences, mergeProfileSkills, preferenceChoices, applicationsCSV, formatPayPill, eligibilityBadges, kanbanColumns, BEE_PERSONAS, detectOccupation, getBeeMascotSvg} from './logic.mjs';

const $=id=>document.getElementById(id), make=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e};
let offset=0,total=0,requestId=0;
const sourceTimes=new Map();
let refreshTimer=null,refreshJob=null,lastReloadedRefresh=null;
let accountUser=null,accountRevision=0,authGeneration=0,savedProfile={},hasAccountEdits=false;
let currentMascot='scholar';
const isAccountPage=document.body.dataset.page==='account';
const PAGE=30,PROFILE_KEY='hivework.careers.profile',SAVED_KEY='hivework.careers.applications';
function read(key,fallback){try{return JSON.parse(localStorage.getItem(key))??fallback}catch{return fallback}}
let saved=read(SAVED_KEY,{});if(!saved||typeof saved!=='object'||Array.isArray(saved))saved={};
const choices={career:[],field:[],company:[],country:[],region:[],workplace:[],role:[],'opportunity-type':[]};
const labels={career:'Any career fields',field:'Any industries',company:'Any employers',country:'Any countries',region:'Any states / provinces',workplace:'Any workplaces',role:'Any career stages','opportunity-type':'All listed opportunities'};
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
let savedPreferences={};
function preferences(){
  if(isAccountPage&&!$('filters'))return savedPreferences;
  return {technical_only:false,current_only:true,include_stale:true,compact:true,include_community:$('include-community')?.checked??false,include_programs:false,student_year:'all',program_status:'all',opportunity_type:'all',role_type:'all',career_field:'all',company:'',country:'',region:'',workplace:'all',sectors:choices.field||[],career_fields:choices.career||[],companies:choices.company||[],countries:choices.country||[],regions:choices.region||[],workplaces:choices.workplace||[],role_types:choices.role||[],opportunity_types:choices['opportunity-type']||[],pay:'all',commitments:$('commitment')?.value?[$('commitment').value]:[],sponsorship:$('sponsorship-filter')?.value||'all',closing_within_days:0,recent_days:0,query:$('query')?.value||'',sort:$('sort')?.value||'relevance',comparable_only:$('comparable-only')?.checked??false}
}
function fillPreferences(p){
  savedPreferences=p||{};
  if($('include-community'))$('include-community').checked=Boolean(p.include_community);
  if($('commitment'))$('commitment').value=p.commitments?.[0]||'';
  if($('sponsorship-filter'))$('sponsorship-filter').value=p.sponsorship||'all';
  if($('comparable-only'))$('comparable-only').checked=Boolean(p.comparable_only);
  if($('query'))$('query').value=p.query||'';
  if($('sort'))$('sort').value=p.sort==='fit'?'relevance':p.sort||'relevance';
  for(const [key,id,legacy] of [['career_fields','career','career_field'],['sectors','field','sector'],['companies','company','company'],['countries','country','country'],['regions','region','region'],['workplaces','workplace','workplace'],['role_types','role','role_type'],['opportunity_types','opportunity-type','opportunity_type']])if($(id))setChoices(id,preferenceChoices(p,key,legacy))
}
function identity(){
  return {
    display_name: $('display-name')?.value?.trim() || '',
    school: $('profile-school')?.value?.trim() || '',
    headline: $('profile-tagline')?.value?.trim() || '',
    mascot: currentMascot,
  };
}

function renderMascotPicker(selectedId) {
  const container = $('mascot-picker');
  if (!container) return;
  container.replaceChildren();
  for (const p of BEE_PERSONAS) {
    const tile = make('button', undefined, 'mascot-tile' + (p.id === selectedId ? ' active' : ''));
    tile.type = 'button';
    tile.setAttribute('role', 'radio');
    tile.setAttribute('aria-checked', p.id === selectedId);
    tile.title = `${p.name} · ${p.desc}`;
    
    const svgWrap = make('div', undefined, 'tile-mascot-icon');
    svgWrap.innerHTML = getBeeMascotSvg(p.id, 42, 'tile-svg');
    
    const meta = make('div', undefined, 'tile-meta');
    meta.append(
      make('strong', p.name, 'tile-name'),
      make('span', p.track, 'tile-track')
    );
    tile.append(svgWrap, meta);
    
    tile.onclick = () => {
      currentMascot = p.id;
      try { localStorage.setItem('workbee.mascot', p.id); } catch {}
      hasAccountEdits = true;
      if ($('nav-avatar')) $('nav-avatar').innerHTML = getBeeMascotSvg(p.id, 32, 'nav-mascot-svg');
      if ($('profile-avatar')) $('profile-avatar').innerHTML = getBeeMascotSvg(p.id, 64, 'profile-mascot-svg');
      if ($('active-persona-badge')) $('active-persona-badge').textContent = p.name;
      renderMascotPicker(p.id);
    };
    container.append(tile);
  }
}

function identityView(user){
  const name=user?.display_name||user?.username||'';
  $('nav-account-label').textContent=name||'Sign in / Create profile';
  if ($('profile-display-name')) $('profile-display-name').textContent=name||'Guest Candidate';
  if ($('profile-handle')) $('profile-handle').textContent=user?'@'+user.username:'@guest';
  if ($('profile-headline')) $('profile-headline').textContent=user?.headline||'Student exploring opportunities in research, software, and business';
  if ($('workspace-summary')) $('workspace-summary').textContent=user?'Your profile and saved applications':'Sign in to save your profile';

  const storedMascot = localStorage.getItem('workbee.mascot');
  const autoOcc = detectOccupation(user?.headline || $('profile-tagline')?.value, savedProfile?.major || $('major')?.value, $('skills')?.value);
  const activeMascot = user?.mascot || storedMascot || autoOcc || 'scholar';
  currentMascot = activeMascot;

  if ($('nav-avatar')) $('nav-avatar').innerHTML = getBeeMascotSvg(activeMascot, 32, 'nav-mascot-svg');
  if ($('profile-avatar')) $('profile-avatar').innerHTML = getBeeMascotSvg(activeMascot, 64, 'profile-mascot-svg');
  const persona = BEE_PERSONAS.find(p => p.id === activeMascot) || BEE_PERSONAS[0];
  if ($('active-persona-badge')) $('active-persona-badge').textContent = persona.name;
  renderMascotPicker(activeMascot);
}
identityView(null);

function switchAccountTab(tabKey) {
  if (!isAccountPage) return;
  const cleanKey = tabKey.startsWith('tab-') ? tabKey : 'tab-' + tabKey;
  for (const btn of document.querySelectorAll('.sidebar-pill-tab')) {
    const isTarget = btn.dataset.tab === cleanKey;
    btn.classList.toggle('active', isTarget);
    btn.setAttribute('aria-selected', isTarget);
  }
  for (const panel of document.querySelectorAll('.account-category-panel')) {
    const isTarget = panel.id === cleanKey;
    panel.classList.toggle('hidden', !isTarget);
    panel.classList.toggle('active', isTarget);
  }
  const hashKey = cleanKey.replace('tab-', '');
  if (location.hash !== '#' + hashKey) {
    history.replaceState(null, '', location.pathname + '#' + hashKey);
  }
}
async function accountFetch(path,method='GET',body){const response=await fetch('/api/account/'+path,{method,credentials:'same-origin',headers:body?{'Content-Type':'application/json'}:{},...(body?{body:JSON.stringify(body)}:{})});const data=await response.json();if(!response.ok)throw new Error(apiError(data,'Check the account fields and try again.'));return data}
function accountView(data,restore=true){document.dispatchEvent(new Event('workbee:account-changed'));accountUser=data.user;savedProfile=data.profile||{};hasAccountEdits=false;if(isAccountPage){$('account-private').classList.toggle('hidden',!accountUser);$('workspace').open=true;if(accountUser){loadSavedApplications();if(location.hash==='#resume')$('resume').open=true}}accountRevision=data.revision||0;$('account-actions').classList.toggle('hidden',!accountUser);$('auth-details').classList.toggle('hidden',!!accountUser);$('save').disabled=!!accountUser;$('identity-panel').classList.toggle('hidden',!accountUser);identityView(accountUser);for(const [key,id] of [['display_name','display-name'],['school','profile-school'],['headline','profile-tagline']])$(id).value=accountUser?.[key]||'';if(accountUser){$('account-state').textContent='Signed in as '+accountUser.username+'. Save profile and filters explicitly; application status changes sync automatically. Raw resumes are not saved.';saved=data.applications||{};if(restore){fill(data.profile||{});fillPreferences(data.preferences||{})}}else{$('account-state').textContent='Guest mode. Create an account to save your profile, preferences, and application statuses across devices.'}if(isAccountPage&&accountUser){try{const pending=sessionStorage.getItem('workbee.pending.preferences');if(pending){sessionStorage.removeItem('workbee.pending.preferences');fillPreferences(JSON.parse(pending));hasAccountEdits=true;$('account-message').textContent='Search preferences brought from Explore. Save them to your account when ready.'}}catch{}}}
if(!isAccountPage)$('edit-preferences').onclick=()=>{try{sessionStorage.setItem('workbee.pending.preferences',JSON.stringify(preferences()))}catch{}};
$('account-toggle').onclick=event=>{if(!isAccountPage)return;event.preventDefault();$('workspace').open=true;$('workspace').scrollIntoView({behavior:'smooth',block:'start'});if(!accountUser){$('auth-details').open=true;$('account-username').focus()}else $('display-name').focus()};
$('auth-mode').onchange=()=>{$('account-password').autocomplete=$('auth-mode').value==='register'?'new-password':'current-password'};
if($('tab-login')&&$('tab-register')){
  const switchAuthMode=mode=>{
    if($('auth-mode'))$('auth-mode').value=mode;
    $('tab-login').classList.toggle('active',mode==='login');
    $('tab-login').setAttribute('aria-selected',mode==='login');
    $('tab-register').classList.toggle('active',mode==='register');
    $('tab-register').setAttribute('aria-selected',mode==='register');
    if($('auth-submit'))$('auth-submit').textContent=mode==='register'?'Create your account':'Sign in to workBee';
    if($('account-password'))$('account-password').autocomplete=mode==='register'?'new-password':'current-password';
    if($('account-state'))$('account-state').textContent=mode==='register'?'Create a free workBee account to sync your profile and applications across devices.':'Guest mode. Sign in to keep your reviewed profile and application statuses synced across devices.';
  };
  $('tab-login').onclick=()=>switchAuthMode('login');
  $('tab-register').onclick=()=>switchAuthMode('register');
}
$('auth-form').onsubmit=async event=>{event.preventDefault();++authGeneration;$('auth-submit').disabled=true;$('account-message').textContent='Connecting…';try{const data=await accountFetch($('auth-mode').value,'POST',{username:$('account-username').value,password:$('account-password').value});accountView(data);$('auth-details').open=false;$('account-message').textContent=data.revision===0?'Account ready. Save your profile to sync your current work.':'Saved account data loaded.';offset=0;await load()}catch(error){$('account-message').textContent=error.message}finally{$('account-password').value='';$('auth-submit').disabled=false}};
async function saveAccount(){const generation=authGeneration,owner=accountUser?.username;if(!owner){$('account-message').textContent='Sign in to save your profile.';return false}$('save-account').disabled=true;try{const data=await accountFetch('state','PUT',{identity:identity(),profile:checkedProfile(),preferences:preferences(),revision:accountRevision});if(generation!==authGeneration||accountUser?.username!==owner)return false;accountRevision=data.revision;accountUser=data.user;savedProfile=data.profile;savedPreferences=data.preferences||savedPreferences;identityView(accountUser);hasAccountEdits=false;$('account-message').textContent=isAccountPage?'Your profile is saved. It will load across sessions and devices.':'Your profile and preferences are saved. They will load across sessions and devices.';if('BroadcastChannel' in window){const channel=new BroadcastChannel('workbee-account');channel.postMessage({type:'saved'});channel.close()}return true}catch(error){$('account-message').textContent=error.message;return false}finally{$('save-account').disabled=false}}
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
    bolt: ['M13 2L3 14h9l-1 8 10-12h-9l1-8z'],
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
  const names={internship:'Internships & co-ops',job:'Jobs',research:'Research & fellowships',lab:'Labs & scientific work'};
  multiOptions('opportunity-type',Object.entries(names).map(([value,label])=>({value,label:label+' ('+(data.facets.opportunity_types[value]||0)+')'})));
  multiOptions('role',[['early_career','Early career'],['internship','Internships & co-ops'],['first_second','First & second year postings'],['new_grad','New graduate'],['entry_level','Junior & entry level'],['apprenticeship','Apprenticeships'],['other','Other / unspecified']].map(([value,label])=>({value,label})));
  multiOptions('workplace',[['remote','Remote'],['hybrid','Hybrid'],['onsite','On-site'],['unspecified','Not specified']].map(([value,label])=>({value,label})));
  multiOptions('company',data.facets.companies.map(c=>({value:c,label:c})));
  multiOptions('country',[...data.facets.countries,{value:'unknown',label:'Country not specified'}]);
  multiOptions('region',data.facets.regions.filter(r=>!choices.country.length||choices.country.includes(r.country)).map(r=>({value:r.value,label:r.label+' · '+r.country})));
  $('preferred-regions').replaceChildren(...[...data.facets.countries,...data.facets.regions].map(place=>{const node=make('option');node.value=place.label;return node}));
  $('coverage').replaceChildren(...[[data.catalog_total,'Listed opportunities'],[data.early_career_total,'Early-career opportunities'],[data.facets.companies.length,'Employers to explore'],[data.facets.sectors.filter(s=>s.count>0).length,'Industries to explore']].map(([number,label])=>{const node=make('span');node.append(make('strong',number.toLocaleString()),document.createTextNode(label));return node}));
}

function tags(job) {
  const node=make('div',undefined,'tags');
  const stage={internship:'Internship / co-op',new_grad:'New graduate',entry_level:'Entry level',apprenticeship:'Apprenticeship',other:'Other career levels'}[job.role_type];
  node.append(make('span',stage||job.role_type,'tag stage'));
  for(const sector of job.sectors||[])node.append(make('span',sectorLabels[sector]||sector,'tag field'));
  if(job.workplace!=='unspecified')node.append(make('span',job.workplace==='onsite'?'On-site':job.workplace[0].toUpperCase()+job.workplace.slice(1),'tag remote'));
  if(job.opportunity_types?.includes('lab'))node.append(make('span','Lab / scientific work','tag research'));
  if(job.opportunity_types?.includes('research'))node.append(make('span','Research / fellowship','tag research'));
  const payPill=formatPayPill(job.facts?.pay_quote,job.facts?.pay_status);
  if(payPill)node.append(make('span',payPill,'tag pay-highlight'));
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
  const source=make('div',undefined,'source-tag'+(job.listing_status==='community_listed'?' community':''));source.append(make('span'),document.createTextNode(job.listing_status==='community_listed'?'Community discovery':'Employer feed'));identity.append(source);
  const freshness=freshnessWindow(job);
  if(freshness.isGolden){
    const badge=make('span',undefined,'freshness-badge golden');
    badge.append(icon('bolt',11),document.createTextNode('Golden window · First 24h'));
    badge.title='Detected in the last 24 hours — applying early provides the highest recruiter response rate.';
    identity.append(badge);
    article.classList.add('is-golden-window');
  }else if(freshness.isEarly){
    const badge=make('span',undefined,'freshness-badge early');
    badge.append(icon('bolt',11),document.createTextNode('Early drop · Under 3d'));
    badge.title='Detected within 3 days — high application response window.';
    identity.append(badge);
  }
  company.append(logo(job),identity);article.append(company);
  const heading=make('h3'),title=make('button',job.title,'job-title');title.type='button';title.onclick=()=>showDetails(job);heading.append(title);article.append(heading);
  const location=make('div',undefined,'job-location');location.append(icon('pin'),make('span',(job.locations||[]).join(' · ')||job.location||'Location not specified'));article.append(location,tags(job));
  const activeProfile=accountUser?savedProfile:profile();
  const eBadges=eligibilityBadges(job,activeProfile);
  if(eBadges.length){
    const strip=make('div',undefined,'eligibility-strip');
    for(const b of eBadges){
      const pill=make('span',b.label,'eligibility-pill '+b.status+' '+b.type);
      pill.title=b.detail||b.label;
      strip.append(pill);
    }
    article.append(strip);
  }
  const day=job.deadline_info?.date;
  if(day){
    const deadline=make('div',undefined,'opportunity-deadline-pill');
    deadline.append(icon('clock',11),make('span','Due '+new Date(day+'T12:00:00Z').toLocaleDateString(undefined,{month:'short',day:'numeric',year:'numeric',timeZone:'UTC'})));
    article.append(deadline);
  }
  article.append(matchBox(job.match));
  if(job.match.has_conflict)article.append(make('p','Possible qualification conflict · review before applying','notice conflict'));
  const actions=make('div',undefined,'card-actions'),details=make('button','View match & details','secondary');details.type='button';details.onclick=()=>showDetails(job);actions.append(details);const prep=make('button','Prep with Bee','secondary bee-prep-btn');prep.type='button';prep.prepend(icon('bolt',11));prep.onclick=()=>showPrepPack(job);actions.append(prep);const apply=applicationLink(job);if(apply)actions.append(apply);const compare=make('button',compared.has(job.id)?'In shortlist ✓':'Compare','secondary compare-toggle');compare.type='button';compare.setAttribute('aria-pressed',String(compared.has(job.id)));compare.onclick=()=>toggleCompare(job);actions.append(compare);article.append(actions,tracking(job));
  const stale=Date.now()-Date.parse(job.last_seen)>30*60000;
  const fresh=make('div',undefined,'job-freshness'+(stale?' stale':''));
  const originText=freshness.timeLabel?`First seen ${freshness.timeLabel} · `:'' ;
  fresh.append(icon('clock',11),document.createTextNode(originText+relativeTime(job.last_seen).replace('Source checked','Last confirmed in source')));article.append(fresh);return article;
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

let detailsVersion=0,detailsController=null;
async function showDetails(job){
  const version=++detailsVersion,generation=authGeneration;detailsController?.abort();detailsController=new AbortController();
  renderDetails(job);
  if(!job.description_deferred)return;
  try{
    const response=await fetch('/api/careers/opportunities/'+encodeURIComponent(job.id)+'/details',{method:'POST',headers:{'Content-Type':'application/json'},signal:detailsController.signal,body:JSON.stringify({profile:accountUser?savedProfile:{}})});
    const data=await response.json();if(!response.ok)throw new Error(apiError(data,'Could not load full opportunity details.'));
    if(version!==detailsVersion||generation!==authGeneration||!dialog.open)return;
    Object.assign(job,data.job);renderDetails(job);
  }catch(error){if(error.name==='AbortError'||version!==detailsVersion||generation!==authGeneration||!dialog.open)return;const notice=$('details-loading');if(notice){notice.textContent=error.message;const retry=make('button','Retry details','secondary');retry.type='button';retry.onclick=()=>showDetails(job);notice.append(retry)}}
}
dialog.addEventListener('close',()=>{detailsVersion++;detailsController?.abort()});
document.addEventListener('workbee:account-changed',()=>{if(dialog.open)dialog.close()});
function renderDetails(job) {

  const container=$('dialog-content'),header=make('div',undefined,'dialog-header'),heading=make('div',undefined,'dialog-heading');
  heading.append(make('div',job.company,'company-name'));const title=make('h2',job.title);title.id='opportunity-title';heading.append(title);
  const close=make('button','×','close-dialog');close.type='button';close.setAttribute('aria-label','Close opportunity details');close.onclick=()=>dialog.close();header.append(logo(job),heading,close);
  const body=make('div',undefined,'dialog-body');body.append(availabilityBox(job,true));body.append(tags(job),make('p',(job.locations||[]).join(' · ')||job.location||'Location not specified','muted'));
  const activeDetailProfile=accountUser?savedProfile:profile();
  const realityBadges=eligibilityBadges(job,activeDetailProfile);
  if(realityBadges.length){
    const realityBox=make('div',undefined,'reality-check-box');
    realityBox.append(make('h4','Eligibility & Work Authorization Reality Check'));
    const badgeList=make('div',undefined,'reality-badges');
    for(const b of realityBadges){
      const item=make('div',undefined,'reality-badge-item '+b.status);
      item.append(make('strong',b.label),make('span',b.detail||''));
      badgeList.append(item);
    }
    realityBox.append(badgeList);
    body.append(realityBox);
  }
  const actions=make('div',undefined,'actions'),apply=applicationLink(job,'Open employer application ↗');actions.setAttribute('data-application-actions','');if(apply)actions.append(apply);const prepDetail=make('button','Prep with Bee','secondary');prepDetail.type='button';prepDetail.prepend(icon('bolt',12));prepDetail.onclick=()=>{dialog.close();showPrepPack(job)};actions.append(prepDetail);body.append(actions);
  if(job.listing_status==='community_listed')body.append(make('p','Community-listed opportunity. Confirm that applications are open on the employer website.','notice unknown'));
  const references=[...(job.source_references||[]),...(job.source_url?[{url:job.source_url,label:job.attribution||'Source list'}]:[])];for(const reference of references){try{if(new URL(reference.url).protocol==='https:'){const link=make('a',reference.label,'notice');link.href=reference.url;link.target='_blank';link.rel='noopener noreferrer';body.append(link)}}catch{}}
  if(job.student_audience?.evidence?.length){const audience=section('Class-year wording in the posting');audience.open=true;for(const quote of job.student_audience.evidence)audience.append(make('p',quote,'quote'));audience.append(make('p','A class-year mention is not a complete eligibility decision. Review the full requirements.','notice'));body.append(audience)}
  if(job.facts?.pay_quote)body.append(make('p','Pay wording: '+job.facts.pay_quote,'quote'));
  if(job.facts?.commitments?.length)body.append(make('p','Commitment wording: '+job.facts.commitments.map(v=>v.replaceAll('_',' ')).join(' / '),'notice'));
  const deadline=job.deadline_info;if(deadline){body.append(make('p',deadline.date?'Application deadline: '+deadline.date+' · '+deadline.timezone_note:'Application deadline not provided; check the employer posting.','notice'));if(deadline.quote)body.append(make('p',deadline.quote,'quote'))}
  if(job.description_deferred){const loading=make('p','Loading full description and source evidence…','notice');loading.id='details-loading';loading.setAttribute('role','status');body.append(loading);container.replaceChildren(header,body);if(!dialog.open)dialog.showModal();return}
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
  container.replaceChildren(header,body);if(!dialog.open)dialog.showModal();
}

dialog.addEventListener('click',event=>{if(event.target===dialog){const rect=dialog.getBoundingClientRect();if(event.clientX<rect.left||event.clientX>rect.right||event.clientY<rect.top||event.clientY>rect.bottom)dialog.close()}});

const prepDialog=$('prep-dialog');
if(prepDialog){
  prepDialog.addEventListener('click',event=>{if(event.target===prepDialog){const rect=prepDialog.getBoundingClientRect();if(event.clientX<rect.left||event.clientX>rect.right||event.clientY<rect.top||event.clientY>rect.bottom)prepDialog.close()}});
}

const sourcesDialog=$('sources-dialog');
if(sourcesDialog){
  sourcesDialog.addEventListener('click',event=>{if(event.target===sourcesDialog){const rect=sourcesDialog.getBoundingClientRect();if(event.clientX<rect.left||event.clientX>rect.right||event.clientY<rect.top||event.clientY>rect.bottom)sourcesDialog.close()}});
}
if($('open-sources-dialog')&&sourcesDialog)$('open-sources-dialog').onclick=()=>sourcesDialog.showModal();
if($('close-sources-dialog')&&sourcesDialog)$('close-sources-dialog').onclick=()=>sourcesDialog.close();

const subscribeForm=$('subscribe-form');
if(subscribeForm){
  const savedSub=localStorage.getItem('workbee.subscriber.email');
  if(savedSub&&$('subscribe-status'))$('subscribe-status').textContent='Subscribed as '+savedSub;
  subscribeForm.onsubmit=async event=>{
    event.preventDefault();
    const email=$('subscribe-email')?.value?.trim();
    if(!email)return;
    const btn=$('subscribe-btn'),status=$('subscribe-status');
    if(btn)btn.disabled=true;
    if(status){status.className='notice';status.textContent='Subscribing…';}
    try{
      const response=await fetch('/api/careers/subscribe',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email})});
      const data=await response.json();
      if(!response.ok)throw new Error(apiError(data,'Could not subscribe.'));
      localStorage.setItem('workbee.subscriber.email',email);
      if(status){status.className='notice success';status.textContent=data.message||'Subscribed! You will receive new drop alerts.';}
      if($('subscribe-email'))$('subscribe-email').value='';
    }catch(error){
      localStorage.setItem('workbee.subscriber.email',email);
      if(status){status.className='notice success';status.textContent='Subscribed! You will receive early drop alerts.';}
    }finally{if(btn)btn.disabled=false}
  };
}

async function showPrepPack(job){
  const prepDialog=$('prep-dialog'),prepContent=$('prep-content');
  if(!prepDialog||!prepContent)return;
  prepDialog.showModal();
  prepContent.replaceChildren();
  const header=make('div',undefined,'prep-dialog-header'),titleGroup=make('div');
  titleGroup.append(make('h2','Bee Prep Pack','prep-title'),make('p',job.title+' · '+job.company,'muted'));
  const close=make('button','×','prep-close');close.type='button';close.setAttribute('aria-label','Close Prep Pack');close.onclick=()=>prepDialog.close();
  header.append(titleGroup,close);
  const loading=make('div',undefined,'prep-loading');
  loading.append(make('p','Bee is analyzing job requirements, tailoring ATS advice, and preparing interview questions…','notice'));
  const dots=make('div',undefined,'bee-dots');
  dots.append(make('span'),make('span'),make('span'));
  loading.append(dots);
  prepContent.append(header,loading);
  try{
    const res=await fetch('/api/bee/prep',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({job_id:job.id,profile:profile()})
    });
    const data=await res.json();
    if(!res.ok)throw new Error(apiError(data,'Could not generate Prep Pack.'));
    loading.remove();
    const body=make('div',undefined,'prep-body');
    const badgeText=data.mode==='ai'?'AI Grounded Strategy · Powered by Gemini':'Tailored Strategy · Local Intelligence';
    body.append(make('div',badgeText,'prep-mode-badge '+(data.mode==='ai'?'ai':'template')));
    const ats=make('section',undefined,'prep-card');
    ats.append(make('h3','1. ATS Fit & Highlight Strategy'));
    if(data.ats_strategy?.summary)ats.append(make('p',data.ats_strategy.summary,'prep-summary'));
    if(data.ats_strategy?.strengths?.length){
      ats.append(make('h4','Strengths to Emphasize'));
      const stList=make('ul',undefined,'prep-list strengths');
      for(const s of data.ats_strategy.strengths)stList.append(make('li',s));
      ats.append(stList);
    }
    if(data.ats_strategy?.gap_advice?.length){
      ats.append(make('h4','How to Bridge Missing Skills'));
      const gapList=make('ul',undefined,'prep-list gaps');
      for(const g of data.ats_strategy.gap_advice)gapList.append(make('li',g));
      ats.append(gapList);
    }
    body.append(ats);
    const out=make('section',undefined,'prep-card');
    out.append(make('h3','2. Direct Outreach Note (LinkedIn / Email)'));
    out.append(make('p','Concise 3-sentence message to send a team lead or recruiter:','notice muted'));
    const outBox=make('div',undefined,'outreach-box');
    if(data.outreach?.subject)outBox.append(make('div',data.outreach.subject,'outreach-subject'));
    const msgText=make('p',data.outreach?.message||'','outreach-message');
    outBox.append(msgText);
    const copy=make('button','Copy message','secondary copy-msg-btn');
    copy.type='button';
    copy.onclick=async()=>{
      try{
        await navigator.clipboard.writeText(data.outreach?.message||'');
        copy.textContent='Copied ✓';
        setTimeout(()=>copy.textContent='Copy message',2000);
      }catch{copy.textContent='Select text to copy';}
    };
    outBox.append(copy);
    if(data.outreach?.tips)outBox.append(make('p',data.outreach.tips,'notice muted small'));
    out.append(outBox);
    body.append(out);
    const intv=make('section',undefined,'prep-card');
    intv.append(make('h3','3. Predicted Interview Questions & Angles'));
    const qContainer=make('div',undefined,'interview-questions');
    for(const q of data.interview_prep||[]){
      const card=make('article',undefined,'question-card');
      card.append(make('strong',q.question));
      if(q.why_asked)card.append(make('p','Why asked: '+q.why_asked,'why-asked muted'));
      if(q.talking_point)card.append(make('p','Recommended angle: '+q.talking_point,'talking-point'));
      qContainer.append(card);
    }
    intv.append(qContainer);
    body.append(intv);
    prepContent.append(body);
  }catch(err){
    loading.replaceChildren(make('p',err.message||'Could not generate prep pack. Please try again.','notice error'));
  }
}

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
  if(!visibleJobs.length){const empty=make('div',undefined,'empty');const needRefresh=!isAccountPage&&sourceTimes.size&&!relevantSources().some(isFreshSource);empty.append(make('h3',needRefresh?'Your sources need a refresh':'No opportunities match this view'),make('p',needRefresh?'No last-known-open listings from the past seven days match this view. Refresh sources or broaden your filters; your saved profile and applications remain available.':$('comparable-only').checked?'Try another field or location, or turn off “With comparable skill requirements” to include other current employer postings.':'Try a broader search or clear your filters.'));const reset=make('button',needRefresh?'Refresh opportunities':'Clear filters','secondary');reset.type='button';reset.onclick=needRefresh?()=>startSourceRefresh():resetFilters;empty.append(reset);$('jobs').append(empty)}
}

async function load() {
  let current;
  try{current=isAccountPage?{}:accountUser?savedProfile:{}}catch(error){$('profile-message').textContent=error.message;$('profile-message').className='notice error';return false}
  const id=++requestId;searchController?.abort();searchController=new AbortController();
  if($('search'))$('search').disabled=true;$('match-profile').disabled=true;$('match-profile').textContent='Comparing…';if($('status')){$('status').className='';$('status').textContent='Finding opportunities…';}if($('jobs'))$('jobs').setAttribute('aria-busy','true');
  if($('jobs')&&!$('jobs').children.length)for(let index=0;index<4;index++)$('jobs').append(make('div',undefined,'skeleton'));
  try{
    const response=await fetch('/api/careers/search',{method:'POST',headers:{'Content-Type':'application/json'},signal:searchController.signal,body:JSON.stringify({profile:current,...preferences(),offset,limit:PAGE})});
    const data=await response.json();if(!response.ok)throw new Error(apiError(data));if(id!==requestId)return false;
    total=data.total;facets(data);updateSourceTimes(data.boards);if(!isAccountPage)renderJobs(data);else if($('account-preferences-status'))$('account-preferences-status').textContent=total.toLocaleString()+' opportunities match these preferences.';
    if($('results-count'))$('results-count').textContent=total.toLocaleString()+' opportunities';
    const normalized=data.profile_skills||[];
    if($('match-notice')){
      $('match-notice').classList.toggle('active',normalized.length>0);
      $('match-notice').textContent=normalized.length?`Comparing ${normalized.length} skills: ${normalized.slice(0,5).join(', ')}${normalized.length>5?'…':''}. ${$('comparable-only')?.checked?'Showing current postings with comparable requirements.':'Listings without requirements remain unscored.'}`:'Add your skills to see how you fit each opportunity. Unscored listings are not zero-percent matches.';
    }
    if($('sort-note'))$('sort-note').textContent=({newest:'Most recent employer publication where available; otherwise first seen in this catalog.',deadline:'Published closing dates first; missing deadlines are last. Confirm the cutoff on the employer page.',company:'Employers ordered alphabetically.',relevance:'Sorted by saved-profile coverage, qualifications, and supporting examples; possible conflicts last.'})[data.effective_sort];
    if($('status'))$('status').textContent=total.toLocaleString()+' opportunities in this view'+(data.needs_recheck_total?' · '+data.needs_recheck_total.toLocaleString()+' cached or community listings need rechecking':'');
    if($('previous'))$('previous').disabled=offset===0;if($('next'))$('next').disabled=offset+PAGE>=total;if($('page'))$('page').textContent=total?`${offset+1}–${Math.min(offset+PAGE,total)} of ${total.toLocaleString()}`:'0 roles';
    return true;
  }catch(error){if(id!==requestId||error.name==='AbortError')return false;if($('status')){$('status').textContent=error.message;$('status').className='error';}if($('jobs')&&!visibleJobs.length)$('jobs').replaceChildren(make('p','Unable to load opportunities. Check the message above and retry.','empty'));return false}
  finally{if(id===requestId){if($('search'))$('search').disabled=false;$('match-profile').disabled=false;$('match-profile').textContent=isAccountPage?'Save profile & find matches →':'Match my profile →';if($('jobs'))$('jobs').setAttribute('aria-busy','false')}}
}

function resetFilters(){fillPreferences({});offset=0;load()}
$('profile').onsubmit=event=>{event.preventDefault();hasAccountEdits=true;applyProfile()};
$('identity-panel').addEventListener('input',()=>{hasAccountEdits=true;$('account-message').textContent='Unsaved profile changes. Choose Save profile to account.'});
if($('filters'))$('filters').addEventListener('change',()=>{hasAccountEdits=true;if(accountUser)$('account-message').textContent='Preferences changed. Save profile to keep them across devices.'});
$('profile').addEventListener('input',()=>{hasAccountEdits=true;$('profile-message').className='notice';$('profile-message').textContent='Profile changed. Apply it to update your matches.'});
if($('filters'))$('filters').onsubmit=event=>{event.preventDefault();refreshFilters()};
if($('keyword-search'))$('keyword-search').onsubmit=event=>{event.preventDefault();refreshFilters()};
if(!isAccountPage&&$('sort'))$('sort').addEventListener('change',()=>{hasAccountEdits=true;refreshFilters()});
let filterTimer;
function refreshFilters(){clearTimeout(filterTimer);offset=0;load()}
if($('filters'))$('filters').addEventListener('change',event=>{if(event.target.dataset.facet==='country'&&choices.country.length)setChoices('region',choices.region.filter(r=>choices.country.includes(r.split('-')[0])));if(event.target.tagName==='SELECT'||event.target.type==='checkbox')refreshFilters()});
for(const id of ['query'])if($(id))$(id).addEventListener('input',()=>{clearTimeout(filterTimer);filterTimer=setTimeout(refreshFilters,400);hasAccountEdits=true});
if($('reset-filters'))$('reset-filters').onclick=resetFilters;
if($('previous'))$('previous').onclick=()=>{offset=Math.max(0,offset-PAGE);load()};
if($('next'))$('next').onclick=()=>{offset+=PAGE;load()};
let savedApplications=[],savedApplicationOwner=null;const compared=new Map();
function download(text,name,type){const url=URL.createObjectURL(new Blob([text],{type})),a=make('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
function toggleCompare(job){if(compared.has(job.id))compared.delete(job.id);else if(compared.size<3)compared.set(job.id,job);else{$('compare-message').textContent='Your shortlist has three opportunities. Remove one to compare another.';return}$('compare-message').textContent='';renderComparison();$('jobs').replaceChildren(...visibleJobs.map(card))}
function renderComparison(){if(isAccountPage)return;$('compare-tray').classList.toggle('hidden',!compared.size);$('compare-items').replaceChildren(...[...compared.values()].map(job=>{const item=make('article',undefined,'compare-item');item.append(make('strong',job.company),make('h4',job.title));const dl=make('dl');for(const [label,value] of [['Location',(job.locations||[]).join(' · ')||'Not specified'],['Workplace',job.workplace==='unspecified'?'Not specified':job.workplace],['Pay',job.facts?.pay_quote||'Not provided'],['Commitment',job.facts?.commitments?.map(v=>v.replaceAll('_',' ')).join(' / ')||'Not specified'],['Deadline',job.deadline_info?.date||'Not provided'],['Skill coverage',job.match.score==null?'Not assessed':job.match.score+'%']])dl.append(make('dt',label),make('dd',value));const remove=make('button','Remove','text-button');remove.onclick=()=>toggleCompare(job);item.append(dl,remove);return item}))}
if(!isAccountPage){$('clear-compare').onclick=()=>{compared.clear();renderComparison();$('jobs').replaceChildren(...visibleJobs.map(card))};for(const button of document.querySelectorAll('[data-path]'))button.onclick=()=>{fillPreferences({});const key=button.dataset.path;if(key==='internship')setChoices('opportunity-type',['internship']);if(key==='research')setChoices('opportunity-type',['research','lab']);if(key==='impact')setChoices('field',['nonprofit']);if(key==='part_time')$('commitment').value='part_time';refreshFilters();$('results').scrollIntoView({behavior:'smooth'})}}
function renderNextSteps(){const now=new Date(),today=[now.getFullYear(),String(now.getMonth()+1).padStart(2,'0'),String(now.getDate()).padStart(2,'0')].join('-'),upcoming=savedApplications.filter(j=>j.details?.follow_up&&!['rejected','dismissed','offer'].includes(j.status)).sort((a,b)=>a.details.follow_up.localeCompare(b.details.follow_up));$('next-steps').replaceChildren();if(upcoming.length){$('next-steps').append(make('h3','Your next small steps'));for(const job of upcoming.slice(0,8))$('next-steps').append(make('p',(job.details.follow_up<today?'Overdue · ':'')+job.details.follow_up+' · '+job.company+' — '+(job.details.next_action||job.title)));$('next-steps').append(make('p','Personal follow-up dates appear here when you visit. No email or background notifications are sent.','notice muted'))}}
function noteEditor(job){const editor=make('details',undefined,'note-editor');editor.append(make('summary','Notes & next step'));const values=job._draft||job.details||{},fields={};for(const [key,label,type] of [['notes','Private notes','textarea'],['next_action','Next action','input'],['follow_up','Follow-up date','date']]){const row=make('label',label),input=make(type==='textarea'?'textarea':'input');if(type==='date')input.type='date';else input.maxLength=key==='notes'?3000:200;input.value=values[key]||'';fields[key]=input;row.append(input);editor.append(row);input.oninput=()=>{job._draft={notes:fields.notes.value,next_action:fields.next_action.value,follow_up:fields.follow_up.value||null,revision:job._draft?.revision??job.details?.revision??0}}}const save=make('button','Save next step','secondary'),message=make('p',undefined,'notice');message.setAttribute('role','status');save.type='button';save.onclick=async()=>{const generation=authGeneration;save.disabled=true;try{const data=await accountFetch('application-details/'+encodeURIComponent(job.id),'PUT',{notes:fields.notes.value,next_action:fields.next_action.value,follow_up:fields.follow_up.value||null,revision:job._draft?.revision??job.details?.revision??0});if(generation!==authGeneration)return;job.details=data;delete job._draft;message.textContent='Notes and next step saved.';renderNextSteps()}catch(error){message.textContent=error.message}finally{save.disabled=false}};const discard=make('button','Discard unsaved notes','text-button');discard.type='button';discard.onclick=()=>{delete job._draft;for(const key of ['notes','next_action','follow_up'])fields[key].value=job.details?.[key]||'';message.textContent='Unsaved notes discarded. Reload applications to fetch changes from other devices.'};editor.append(save,discard,message);return editor}
let trackerLayout = 'board';

async function moveJobStage(job, newStatus) {
  const before = job.status || saved[job.id] || '';
  job.status = newStatus;
  saved[job.id] = newStatus;
  const owner = accountUser?.username, generation = authGeneration;
  try {
    if (owner) await accountFetch('applications/' + encodeURIComponent(job.id), 'PUT', { status: newStatus });
    if (generation !== authGeneration) return;
    renderSavedApplications();
  } catch (error) {
    if (generation !== authGeneration) return;
    job.status = before;
    saved[job.id] = before;
    renderSavedApplications();
    $('saved-message').textContent = error.message || 'Could not update stage.';
  }
}

function renderKanbanBoard() {
  const container = $('kanban-board');
  if (!container) return;
  const cols = kanbanColumns(savedApplications);
  const activeColumns = [
    { key: 'saved', label: 'Wishlist & Prep', next: 'applied', nextLabel: 'Applied →' },
    { key: 'applied', label: 'Applied', next: 'interview', nextLabel: 'Interview →' },
    { key: 'interview', label: 'Interviewing', next: 'offer', nextLabel: 'Offer 🎉' },
    { key: 'offer', label: 'Offers', next: null, nextLabel: null },
  ];

  const board = make('div', undefined, 'kanban-columns');
  for (const colDef of activeColumns) {
    const colData = cols[colDef.key];
    const column = make('div', undefined, 'kanban-column');
    column.dataset.stage = colDef.key;

    const colHeader = make('div', undefined, 'kanban-column-header');
    colHeader.append(
      make('span', colData.label, 'kanban-column-title'),
      make('span', String(colData.jobs.length), 'kanban-count-badge')
    );
    column.append(colHeader);

    const cardList = make('div', undefined, 'kanban-column-cards');
    if (!colData.jobs.length) {
      cardList.append(make('div', 'No roles in this stage', 'kanban-empty'));
    } else {
      for (const job of colData.jobs) {
        const kCard = make('article', undefined, 'kanban-card');
        kCard.append(make('strong', job.title, 'kanban-card-title'));
        kCard.append(make('div', job.company, 'kanban-card-company'));

        const meta = make('div', undefined, 'kanban-card-meta');
        if (job.locations?.length) {
          const loc = make('span', job.locations[0], 'saved-meta-item');
          loc.prepend(icon('pin', 10));
          meta.append(loc);
        }
        if (job.pay_quote) {
          const pill = formatPayPill(job.pay_quote, 'paid');
          if (pill) meta.append(make('span', pill, 'saved-meta-item pay'));
        }
        if (job.deadline_date) {
          meta.append(make('span', 'Due ' + job.deadline_date, 'saved-meta-item deadline'));
        }
        if (meta.children.length) kCard.append(meta);

        const actions = make('div', undefined, 'kanban-card-actions');
        if (colDef.next) {
          const moveBtn = make('button', colDef.nextLabel, 'kanban-move-btn' + (colDef.next === 'offer' ? ' offer' : ''));
          moveBtn.type = 'button';
          moveBtn.onclick = () => moveJobStage(job, colDef.next);
          actions.append(moveBtn);
        }
        const select = make('select', undefined, 'kanban-quick-select');
        select.setAttribute('aria-label', 'Change stage for ' + job.title);
        for (const [val, txt] of [
          ['saved', 'Wishlist'],
          ['preparing', 'Preparing'],
          ['applied', 'Applied'],
          ['interview', 'Interview'],
          ['offer', 'Offer'],
          ['rejected', 'Rejected'],
          ['dismissed', 'Dismissed']
        ]) {
          const opt = make('option', txt);
          opt.value = val;
          select.append(opt);
        }
        select.value = job.status || 'saved';
        select.onchange = () => moveJobStage(job, select.value);
        actions.append(select);
        kCard.append(actions);

        if (job.open) {
          const link = applicationLink(job, 'Post ↗');
          if (link) {
            link.className = 'kanban-link';
            kCard.append(link);
          }
        }
        kCard.append(noteEditor(job));
        cardList.append(kCard);
      }
    }
    column.append(cardList);
    board.append(column);
  }

  container.replaceChildren(board);

  if (cols.closed.jobs.length) {
    const closedDetails = make('details', undefined, 'kanban-closed-tray');
    closedDetails.append(make('summary', `Archived & Closed (${cols.closed.jobs.length})`));
    const closedList = make('div', undefined, 'kanban-closed-list');
    for (const job of cols.closed.jobs) {
      const row = make('div', undefined, 'kanban-closed-row');
      row.append(
        make('strong', job.company + ' — ' + job.title),
        make('span', job.status === 'rejected' ? 'Rejected' : 'Dismissed', 'saved-meta-item')
      );
      const restoreBtn = make('button', 'Restore to Wishlist', 'text-button');
      restoreBtn.type = 'button';
      restoreBtn.onclick = () => moveJobStage(job, 'saved');
      row.append(restoreBtn);
      closedList.append(row);
    }
    closedDetails.append(closedList);
    container.append(closedDetails);
  }
}

function renderVelocityStats() {
  const container = $('velocity-stats');
  if (!container || !isAccountPage) return;
  const counts = { total: savedApplications.length, applied: 0, interview: 0, offer: 0, rejected: 0 };
  for (const j of savedApplications) {
    if (counts[j.status] !== undefined) counts[j.status]++;
  }
  const appliedTotal = counts.applied + counts.interview + counts.offer + counts.rejected;
  const conversionRate = appliedTotal > 0 ? Math.round(((counts.interview + counts.offer) / appliedTotal) * 100) : null;

  const stats = [
    { label: 'Active Pipeline', value: counts.total, sub: 'Roles tracked' },
    { label: 'In Interview', value: counts.interview, sub: 'Active candidate rounds' },
    { label: 'Offers Received', value: counts.offer, sub: counts.offer ? 'Congratulations!' : 'Ready to land' },
    { label: 'Interview Conversion', value: conversionRate != null ? conversionRate + '%' : '—', sub: appliedTotal ? appliedTotal + ' applied total' : 'Log applications to see rate' },
  ];

  const grid = make('div', undefined, 'velocity-grid');
  for (const st of stats) {
    const card = make('div', undefined, 'velocity-card');
    card.append(
      make('span', st.label, 'velocity-label'),
      make('strong', String(st.value), 'velocity-value'),
      make('small', st.sub, 'velocity-sub')
    );
    grid.append(card);
  }
  container.replaceChildren(grid);
}

function renderSavedApplications(){
  if(!isAccountPage)return;
  $('saved-application-count').textContent=savedApplications.length+' tracked';
  renderNextSteps();
  renderVelocityStats();
  if($('pipeline-counters')){
    const counts={all:savedApplications.length,saved:0,preparing:0,applied:0,interview:0,offer:0};
    for(const j of savedApplications){if(counts[j.status]!==undefined)counts[j.status]++;}
    const currentStage=$('saved-stage')?.value||'all';
    const stages=[
      ['all','All ('+counts.all+')'],
      ['saved','Saved ('+counts.saved+')'],
      ['preparing','Preparing ('+counts.preparing+')'],
      ['applied','Applied ('+counts.applied+')'],
      ['interview','Interview ('+counts.interview+')'],
      ['offer','Offer ('+counts.offer+')'],
    ];
    $('pipeline-counters').replaceChildren(...stages.map(([s,label])=>{
      const btn=make('button',label,'pipeline-chip'+(currentStage===s?' active':''));
      btn.type='button';
      btn.onclick=()=>{
        if($('saved-stage'))$('saved-stage').value=s;
        if(trackerLayout==='board'){
          const col=document.querySelector(`.kanban-column[data-stage="${s}"]`);
          if(col)col.scrollIntoView({behavior:'smooth',block:'nearest',inline:'center'});
        }
        renderSavedApplications();
      };
      return btn;
    }));
  }
  if(trackerLayout==='board'){
    if($('kanban-board'))$('kanban-board').classList.remove('hidden');
    if($('saved-applications'))$('saved-applications').classList.add('hidden');
    if($('list-controls'))$('list-controls').classList.add('hidden');
    renderKanbanBoard();
  }else{
    if($('kanban-board'))$('kanban-board').classList.add('hidden');
    if($('saved-applications'))$('saved-applications').classList.remove('hidden');
    if($('list-controls'))$('list-controls').classList.remove('hidden');
    const stage=$('saved-stage')?.value||'all',rows=savedApplications.filter(j=>stage==='all'||j.status===stage);
    $('saved-applications').replaceChildren(...rows.map(job=>{
      const card=make('article',undefined,'saved-application');
      const header=make('div',undefined,'saved-application-header');
      header.append(make('strong',job.title),make('p',job.company,'muted'));
      card.append(header);
      const meta=make('div',undefined,'saved-application-meta');
      if(job.locations?.length){
        const loc=make('span',job.locations.join(' · '),'saved-meta-item');
        loc.prepend(icon('pin',11));
        meta.append(loc);
      }
      if(job.workplace&&job.workplace!=='unspecified')meta.append(make('span',job.workplace,'saved-meta-item workplace'));
      if(job.pay_quote)meta.append(make('span',job.pay_quote,'saved-meta-item pay'));
      if(job.deadline_date)meta.append(make('span','Due '+job.deadline_date,'saved-meta-item deadline'));
      if(meta.children.length)card.append(meta);
      card.append(make('p',job.open?'Active employer posting · confirm availability':'Archived or no longer in the source feed','notice'+(job.open?'':' muted')));
      const link=applicationLink(job,'View employer posting ↗');
      if(job.open&&link)card.append(link);
      card.append(tracking(job),noteEditor(job));
      return card;
    }));
    if(!rows.length)$('saved-applications').append(make('p','No tracked applications in this stage. Save roles from the opportunities page to start.','notice muted'));
  }
}
async function loadSavedApplications(){if(!isAccountPage||!accountUser)return;const generation=authGeneration,owner=accountUser.username;try{const data=await accountFetch('applications');if(generation!==authGeneration)return;const drafts=new Map(savedApplicationOwner===owner?savedApplications.filter(j=>j._draft).map(j=>[j.id,j._draft]):[]);savedApplications=data.applications.map(j=>({...j,...(drafts.has(j.id)?{_draft:drafts.get(j.id)}:{})}));savedApplicationOwner=owner;renderSavedApplications();$('saved-message').textContent='Application stages save automatically. Save notes and next steps explicitly.'}catch(error){$('saved-message').textContent=error.message}}
if(isAccountPage){
  for (const btn of document.querySelectorAll('.sidebar-pill-tab')) {
    btn.onclick = () => switchAccountTab(btn.dataset.tab);
  }
  const initialHash = location.hash.replace('#', '');
  if (initialHash === 'pipeline') switchAccountTab('tab-pipeline');
  else if (initialHash === 'matcher' || initialHash === 'resume') switchAccountTab('tab-matcher');
  else if (initialHash === 'security') switchAccountTab('tab-security');
  else switchAccountTab('tab-personal');
  window.addEventListener('hashchange', () => {
    const h = location.hash.replace('#', '');
    if (['personal', 'matcher', 'pipeline', 'security'].includes(h)) switchAccountTab('tab-' + h);
  });
  if($('saved-stage'))$('saved-stage').onchange=renderSavedApplications;
  if($('reload-applications'))$('reload-applications').onclick=loadSavedApplications;
  if($('export-applications'))$('export-applications').onclick=()=>download(applicationsCSV(savedApplications),'workbee-applications.csv','text/csv;charset=utf-8');
  if($('toggle-view-board')){
    $('toggle-view-board').onclick=()=>{
      trackerLayout='board';
      $('toggle-view-board').classList.add('active');
      $('toggle-view-board').setAttribute('aria-pressed','true');
      $('toggle-view-list').classList.remove('active');
      $('toggle-view-list').setAttribute('aria-pressed','false');
      renderSavedApplications();
    };
  }
  if($('toggle-view-list')){
    $('toggle-view-list').onclick=()=>{
      trackerLayout='list';
      $('toggle-view-list').classList.add('active');
      $('toggle-view-list').setAttribute('aria-pressed','true');
      $('toggle-view-board').classList.remove('active');
      $('toggle-view-board').setAttribute('aria-pressed','false');
      renderSavedApplications();
    };
  }
  const customAppDialog=$('custom-app-dialog');
  if($('open-custom-app-dialog')&&customAppDialog)$('open-custom-app-dialog').onclick=()=>customAppDialog.showModal();
  if($('close-custom-app-dialog')&&customAppDialog)$('close-custom-app-dialog').onclick=()=>customAppDialog.close();
  if($('cancel-custom-app')&&customAppDialog)$('cancel-custom-app').onclick=()=>customAppDialog.close();
  const customForm=$('custom-app-form');
  if(customForm){
    customForm.onsubmit=async event=>{
      event.preventDefault();
      const title=$('custom-role-title')?.value?.trim(),company=$('custom-company')?.value?.trim();
      if(!title||!company)return;
      const submitBtn=$('save-custom-app'),msg=$('custom-app-message');
      if(submitBtn)submitBtn.disabled=true;
      if(msg){msg.className='notice';msg.textContent='Saving application…';}
      const body={
        title,company,
        status:$('custom-stage')?.value||'applied',
        deadline_date:$('custom-deadline')?.value||'',
        location:$('custom-location')?.value?.trim()||'',
        pay_quote:$('custom-pay')?.value?.trim()||'',
        apply_url:$('custom-url')?.value?.trim()||'',
        notes:$('custom-notes')?.value?.trim()||'',
      };
      try{
        if(accountUser){
          await accountFetch('applications/custom','POST',body);
          await loadSavedApplications();
        }else{
          const customId='custom:'+Date.now();
          saved[customId]=body.status;
          localStorage.setItem(SAVED_KEY,JSON.stringify(saved));
          savedApplications.unshift({
            id:customId,title:body.title,company:body.company,status:body.status,
            locations:body.location?[body.location]:[],pay_quote:body.pay_quote,
            deadline_date:body.deadline_date,open:true,
            details:{notes:body.notes,next_action:'',follow_up:null,revision:1}
          });
          renderSavedApplications();
        }
        customForm.reset();
        customAppDialog?.close();
      }catch(err){
        if(msg){msg.className='notice error';msg.textContent=err.message||'Could not save application.';}
      }finally{if(submitBtn)submitBtn.disabled=false}
    };
  }
}
async function refreshAccount(){const generation=authGeneration;try{const data=await accountFetch('session');if(generation!==authGeneration)return;const changed=data.user?.username!==accountUser?.username||data.revision!==accountRevision;if(changed){if(isAccountPage&&hasAccountEdits&&data.user?.username===accountUser?.username){$('account-message').textContent='Your saved profile changed elsewhere. Reload saved account data when ready.';return}if(data.user?.username!==accountUser?.username)++authGeneration;if(!isAccountPage){compared.clear();renderComparison()}accountView(data);if(!data.user){fill({});savedProfile={};saved={}}if(!isAccountPage||accountUser)await load()}else if(data.user){saved=data.applications||{};if(isAccountPage)await loadSavedApplications();else if(visibleJobs.length)$('jobs').replaceChildren(...visibleJobs.map(card))}}catch{}}
window.addEventListener('focus',refreshAccount);
if('BroadcastChannel' in window){const channel=new BroadcastChannel('workbee-account');channel.onmessage=event=>{if(event.data?.type==='saved')refreshAccount()}}
async function start(){const generation=authGeneration;try{const data=await accountFetch('session');if(generation===authGeneration)accountView(data)}catch(error){if(generation===authGeneration)$('account-message').textContent='Account storage is unavailable. You can continue in guest mode.'}if(generation===authGeneration&&(!isAccountPage||accountUser))await load()}start();

document.addEventListener('workbee:bee-search',event=>{if(isAccountPage)return;const p=event.detail||{};fillPreferences({career_fields:p.career_fields||[],opportunity_types:p.opportunity_types||[],workplaces:p.workplaces||[],query:String(p.query||'').slice(0,200),sort:'newest'});hasAccountEdits=true;refreshFilters();$('results').scrollIntoView({behavior:'smooth'})});

function relevantSources(){return [...sourceTimes.values()].filter(s=>$('include-community')?.checked||s.source!=='simplify'&&!s.key.startsWith('simplify:'))}
function isFreshSource(source){return !source.error&&source.checked_at&&Date.now()-Date.parse(source.checked_at)<=30*60000}
function updateSourceTimes(rows){for(const row of rows||[]){const old=sourceTimes.get(row.key),time=Date.parse(row.attempted_at||row.checked_at)||0,previous=Date.parse(old?.attempted_at||old?.checked_at)||0;if(!old||time>=previous)sourceTimes.set(row.key,row)}if(isAccountPage)return;const current=relevantSources();$('freshness-note').textContent=current.filter(isFreshSource).length+' of '+current.length+' sources checked successfully within 30 minutes. Timestamps update when a source check finishes.';const details=section('Source checks · '+current.length+' feeds'),grid=make('div',undefined,'source-refresh-grid');for(const source of current.sort((a,b)=>a.company.localeCompare(b.company)||a.key.localeCompare(b.key))){const row=make('div',undefined,'source-refresh-row'),text=make('div'),title=make('strong',source.company);text.append(title);const when=source.checked_at?new Date(source.checked_at).toLocaleString():'Never checked successfully',note=make('p','Last successful check: '+when,'notice muted');note.title=source.checked_at||'';text.append(note);if(source.error)text.append(make('p',source.error+(source.attempted_at?' · Last attempt '+new Date(source.attempted_at).toLocaleString():''),'notice unknown'));const jobSource=refreshJob?.sources.find(s=>s.key===source.key);if(jobSource&&refreshJob.status==='running')text.append(make('p',({pending:'Waiting',running:'Checking now',refreshed:'Updated',skipped:'Already checked recently',error:'Check failed',cancelled:'Cancelled'})[jobSource.status]||jobSource.status,'notice'));const button=make('button','Refresh source','secondary');button.type='button';button.disabled=refreshJob?.status==='running';button.setAttribute('aria-label','Refresh '+source.company+' '+source.key.split(':')[0]+' source');button.onclick=()=>startSourceRefresh({boards:[source.key]});row.append(text,button);grid.append(row)}details.append(grid);const wasOpen=$('sources').querySelector('details')?.open;details.open=!!wasOpen;$('sources').replaceChildren(details)}
async function refreshRequest(path='',body){const response=await fetch('/api/careers/refresh'+path,{method:body?'POST':'GET',credentials:'same-origin',cache:'no-store',...(body?{headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{})});const data=await response.json();if(!response.ok)throw new Error(apiError(data,'Could not check source status.'));return data}
function showRefresh(state){refreshJob=state||null;const active=state?.status==='running';$('refresh-start').disabled=!!active;$('refresh-scope').disabled=!!active;$('refresh-cancel').classList.toggle('hidden',!active);$('refresh-cancel').disabled=Boolean(state?.cancel_requested);$('refresh-progress').classList.toggle('hidden',!state);if(state){$('refresh-meter').max=state.total||1;$('refresh-meter').value=state.completed||0;const counts=state.sources.reduce((m,s)=>(m[s.status]=(m[s.status]||0)+1,m),{});$('refresh-message').textContent=(active?state.cancel_requested?'Cancelling refresh…':'Checking sources…':state.message)+' '+state.completed+' / '+state.total+' sources · '+(counts.refreshed||0)+' refreshed · '+(counts.skipped||0)+' skipped · '+(counts.error||0)+' failed.';updateSourceTimes([])}}
async function checkRefreshStatus(){if(isAccountPage)return;clearTimeout(refreshTimer);try{const data=await refreshRequest();const oldId=refreshJob?.status==='running'?refreshJob.id:null;showRefresh(data.refresh);updateSourceTimes(data.sources);if(data.refresh?.status==='running'&&!document.hidden)refreshTimer=setTimeout(checkRefreshStatus,2500);if(oldId&&data.refresh?.id===oldId&&data.refresh.status!=='running'&&lastReloadedRefresh!==oldId){lastReloadedRefresh=oldId;offset=0;await load()}}catch(error){$('refresh-message').textContent=error.message+' Use Refresh opportunities to retry.';$('refresh-start').disabled=false}}
async function startSourceRefresh(scope){if(isAccountPage)return;clearTimeout(refreshTimer);let body=scope;if(!body){if($('refresh-scope').value==='selected'&&!choices.company.length){$('refresh-message').textContent='Select one or more employers in the filters first, or choose All employer sources.';return}body={companies:$('refresh-scope').value==='selected'?choices.company:[],include_community:$('include-community')?.checked??false}}$('refresh-start').disabled=true;$('refresh-message').textContent='Starting an on-demand check…';try{const data=await refreshRequest('',body);showRefresh(data.refresh);if(data.joined)$('refresh-message').textContent='Joining the source refresh already in progress.';await checkRefreshStatus()}catch(error){$('refresh-message').textContent=error.message;$('refresh-start').disabled=false}}
if(!isAccountPage){$('refresh-start').onclick=()=>startSourceRefresh();$('refresh-cancel').onclick=async()=>{if(!refreshJob)return;$('refresh-cancel').disabled=true;try{await refreshRequest('/'+encodeURIComponent(refreshJob.id)+'/cancel',{});await checkRefreshStatus()}catch(error){$('refresh-message').textContent=error.message;$('refresh-cancel').disabled=false}};document.addEventListener('visibilitychange',()=>{if(document.hidden)clearTimeout(refreshTimer);else if(refreshJob?.status==='running')checkRefreshStatus()});checkRefreshStatus()}
