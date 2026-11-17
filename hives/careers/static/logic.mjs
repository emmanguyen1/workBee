export function parseSkills(text) {
  const found = new Map();
  for (const line of text.split(/\r?\n/)) {
    const [head, ...rest] = line.split('|');
    const evidence = rest.join('|').trim();
    for (const item of head.split(/[,;]/)) {
      const skill = item.trim();
      if (!skill) continue;
      const key = skill.toLowerCase();
      if (!found.has(key) || (!found.get(key).evidence && evidence)) found.set(key, {skill, evidence});
    }
  }
  const skills = [...found.values()];
  if (skills.length > 60) throw new Error('Choose up to 60 skills for your profile.');
  if (skills.some(s => s.skill.length > 60)) throw new Error('Keep each skill name under 60 characters. Separate different skills with commas or new lines.');
  if (skills.some(s => s.evidence.length > 1000)) throw new Error('Keep each skill example under 1,000 characters.');
  return skills;
}

export function apiError(data, fallback = 'Something went wrong. Please try again.') {
  if (typeof data.detail === 'string') return data.detail;
  if (Array.isArray(data.detail)) {
    return data.detail.slice(0, 2).map(error => {
      const field = (error.loc || []).filter(k => !['body', 'profile'].includes(k)).join(' · ');
      return (field ? field + ': ' : '') + String(error.msg || 'Check this value').replace(/^Value error, /, '');
    }).join('. ');
  }
  return fallback;
}

export function assessmentLabel(result) {
  if (result.assessment === 'requirements_unavailable') return 'Requirements not supplied';
  if (result.assessment === 'unrecognized_requirements') return 'Manual review needed';
  if (result.assessment === 'needs_profile') return 'Add skills to compare';
  return result.score == null ? 'Not yet compared' : result.score + '%';
}

export function relativeTime(iso, now = Date.now()) {
  const elapsed = now - Date.parse(iso);
  if (!Number.isFinite(elapsed)) return 'Check time unavailable';
  const minutes = Math.max(0, Math.floor(elapsed / 60000));
  if (minutes < 1) return 'Source checked just now';
  if (minutes < 60) return `Source checked ${minutes}m ago`;
  if (minutes < 1440) return `Source checked ${Math.floor(minutes / 60)}h ago`;
  return `Source checked ${Math.floor(minutes / 1440)}d ago`;
}

export function freshnessWindow(job, now = Date.now()) {
  const origin = job?.published_at || job?.first_seen;
  if (!origin) return { tier: 'standard', isGolden: false, isEarly: false, ageHours: Infinity, label: '', timeLabel: '', description: '' };
  const originTs = Date.parse(origin);
  if (!Number.isFinite(originTs)) return { tier: 'standard', isGolden: false, isEarly: false, ageHours: Infinity, label: '', timeLabel: '', description: '' };
  const diffMs = now - originTs;
  const ageHours = Math.max(0, diffMs / 3600000);
  if (ageHours <= 24) {
    const hours = Math.floor(ageHours);
    const timeLabel = hours < 1 ? 'just now' : `${hours}h ago`;
    return {
      tier: 'golden',
      isGolden: true,
      isEarly: false,
      ageHours,
      label: 'Golden window · First 24h',
      timeLabel,
      description: 'First detected within the last 24 hours — high callback window'
    };
  }
  if (ageHours <= 72) {
    const days = Math.floor(ageHours / 24);
    return {
      tier: 'early',
      isGolden: false,
      isEarly: true,
      ageHours,
      label: 'Early drop · Under 3d',
      timeLabel: `${days}d ago`,
      description: 'First detected within the last 3 days'
    };
  }
  return {
    tier: 'standard',
    isGolden: false,
    isEarly: false,
    ageHours,
    label: '',
    timeLabel: '',
    description: ''
  };
}

export function formatPayPill(payQuote, payStatus) {
  if (payQuote && typeof payQuote === 'string') {
    // Hourly range: $40 to $58/hour or $40 - $58 / hr
    const hourlyRange = payQuote.match(/\$\s*(\d+(?:\.\d+)?)\s*(?:-|–|to|and)\s*\$\s*(\d+(?:\.\d+)?)\s*(?:\/|\s*per\s*)?\s*(?:hr|hour)\b/i);
    if (hourlyRange) {
      const low = parseFloat(hourlyRange[1]), high = parseFloat(hourlyRange[2]);
      return `$${low}–$${high}/hr`;
    }
    // Single hourly: $45/hr or $45.00 per hour
    const singleHourly = payQuote.match(/\$\s*(\d+(?:\.\d+)?)\s*(?:\/|\s*per\s*)?\s*(?:hr|hour)\b/i);
    if (singleHourly) {
      return `$${parseFloat(singleHourly[1])}/hr`;
    }
    // Monthly range or single: $8,000 / month
    const monthly = payQuote.match(/\$\s*(\d[\d,.]*)\s*(?:-|–|to|and)?\s*(?:\$\s*(\d[\d,.]*))?\s*(?:\/|\s*per\s*)?\s*(?:month|mo)\b/i);
    if (monthly) {
      const m1 = parseFloat(monthly[1].replace(/,/g, ''));
      if (monthly[2]) {
        const m2 = parseFloat(monthly[2].replace(/,/g, ''));
        return `$${Math.round(m1 / 1000)}k–$${Math.round(m2 / 1000)}k/mo`;
      }
      return `$${Math.round(m1 / 1000)}k/mo`;
    }
    // Annual salary: $80,000 - $100,000 / year
    const yearly = payQuote.match(/\$\s*(\d[\d,.]*)\s*(?:-|–|to|and)\s*\$\s*(\d[\d,.]*)\s*(?:\/|\s*per\s*)?\s*(?:year|yr|annum|annually)?/i);
    if (yearly && parseFloat(yearly[1].replace(/,/g, '')) >= 10000) {
      const y1 = Math.round(parseFloat(yearly[1].replace(/,/g, '')) / 1000);
      const y2 = Math.round(parseFloat(yearly[2].replace(/,/g, '')) / 1000);
      return `$${y1}k–$${y2}k/yr`;
    }
  }
  if (payStatus === 'paid') return 'Explicitly paid';
  if (payStatus === 'unpaid') return 'Unpaid';
  return null;
}

export function eligibilityBadges(job, profile = {}) {
  const badges = [];
  const checks = job?.match?.eligibility || [];
  const description = job?.description || '';

  // 1. Visa Sponsorship
  const sponsorCheck = checks.find(c => c.criterion === 'Sponsorship');
  if (sponsorCheck && sponsorCheck.status === 'conflict') {
    badges.push({
      type: 'visa',
      status: 'conflict',
      label: 'Sponsorship conflict',
      detail: sponsorCheck.explanation || 'Employer does not offer visa sponsorship.'
    });
  } else if (sponsorCheck && sponsorCheck.status === 'matches' && profile.needs_sponsorship === false) {
    // profile doesn't need it, matches
  } else if (sponsorCheck && sponsorCheck.quote && !sponsorCheck.quote.includes('No explicit rule')) {
    if (/no (?:visa )?sponsorship|cannot.*sponsor|will not.*sponsor|not eligible for.*sponsor/i.test(sponsorCheck.quote)) {
      badges.push({
        type: 'visa',
        status: profile?.needs_sponsorship ? 'conflict' : 'warning',
        label: 'No visa sponsorship',
        detail: sponsorCheck.quote
      });
    } else if (/sponsorship (?:is )?(?:available|provided|offered)|open to (?:f-?1|opt|cpt)/i.test(sponsorCheck.quote)) {
      badges.push({
        type: 'visa',
        status: 'match',
        label: 'Sponsors visas',
        detail: sponsorCheck.quote
      });
    }
  } else if (/no (?:visa )?sponsorship|cannot (?:provide |offer )?(?:visa )?sponsor|will not (?:provide |offer )?(?:visa )?sponsor/i.test(description)) {
    badges.push({
      type: 'visa',
      status: profile?.needs_sponsorship ? 'conflict' : 'warning',
      label: 'No visa sponsorship',
      detail: 'Employer stated no visa sponsorship is available.'
    });
  }

  // 2. US Citizenship / Permanent Residency / Clearance
  const citizenCheck = checks.find(c => c.criterion === 'Citizenship / Clearance');
  if (citizenCheck && citizenCheck.quote) {
    badges.push({
      type: 'citizenship',
      status: 'warning',
      label: 'U.S. Citizen / PR required',
      detail: citizenCheck.quote
    });
  } else if (/\b(?:u\.?s\.?\s+citizenship\s+(?:is\s+)?required|must be a\s+u\.?s\.?\s+citizen|u\.?s\.?\s+citizens?\s+(?:only|or\s+permanent\s+resident)|security\s+clearance\s+(?:required|active)|green\s+card\s+holder)\b/i.test(description)) {
    badges.push({
      type: 'citizenship',
      status: 'warning',
      label: 'U.S. Citizen / PR required',
      detail: 'Requires U.S. Citizenship, Permanent Residency, or Security Clearance.'
    });
  }

  // 3. Graduation Window & Student Stage
  const gradCheck = checks.find(c => c.criterion === 'Graduation window');
  if (gradCheck && gradCheck.status === 'conflict') {
    badges.push({
      type: 'grad',
      status: 'conflict',
      label: 'Grad year conflict',
      detail: gradCheck.explanation || gradCheck.quote
    });
  } else if (gradCheck && gradCheck.status === 'matches') {
    badges.push({
      type: 'grad',
      status: 'match',
      label: 'Grad year matches',
      detail: gradCheck.evidence
    });
  } else if (gradCheck && gradCheck.quote && !gradCheck.quote.includes('No explicit rule')) {
    const m = gradCheck.quote.match(/(20\d{2})\s*(?:-|–|to|and)\s*(20\d{2})/);
    if (m) {
      badges.push({
        type: 'grad',
        status: 'info',
        label: `Class of ${m[1]}–${m[2]}`,
        detail: gradCheck.quote
      });
    }
  } else if (job?.student_audience?.years?.length) {
    const yrs = job.student_audience.years;
    const yrLabel = yrs.includes(1) && yrs.includes(2) ? 'Freshmen & Sophomores' : yrs.includes(1) ? 'Freshmen preferred' : 'Sophomores preferred';
    badges.push({
      type: 'grad',
      status: 'info',
      label: yrLabel,
      detail: job.student_audience.evidence?.[0] || 'Targeted toward early-year students'
    });
  }

  // 4. Minimum GPA
  const gpaCheck = checks.find(c => c.criterion === 'Minimum GPA (4.0 scale)');
  if (gpaCheck && gpaCheck.status === 'conflict') {
    badges.push({
      type: 'gpa',
      status: 'conflict',
      label: 'Min GPA conflict',
      detail: gpaCheck.evidence || gpaCheck.quote
    });
  } else if (gpaCheck && gpaCheck.status === 'matches') {
    badges.push({
      type: 'gpa',
      status: 'match',
      label: 'GPA matches',
      detail: gpaCheck.evidence
    });
  } else if (gpaCheck && gpaCheck.quote && !gpaCheck.quote.includes('No explicit rule')) {
    const m = gpaCheck.quote.match(/GPA\s*(?:of|:)?\s*(\d(?:\.\d+)?)/i);
    if (m) {
      badges.push({
        type: 'gpa',
        status: 'info',
        label: `Min ${m[1]} GPA`,
        detail: gpaCheck.quote
      });
    }
  }

  return badges;
}

export function kanbanColumns(applications = []) {
  const cols = {
    saved: { id: 'saved', label: 'Wishlist & Prep', jobs: [] },
    applied: { id: 'applied', label: 'Applied', jobs: [] },
    interview: { id: 'interview', label: 'Interviewing', jobs: [] },
    offer: { id: 'offer', label: 'Offers', jobs: [] },
    closed: { id: 'closed', label: 'Closed / Inactive', jobs: [] },
  };

  for (const job of applications) {
    const s = job.status || 'saved';
    if (s === 'saved' || s === 'preparing') {
      cols.saved.jobs.push(job);
    } else if (s === 'applied') {
      cols.applied.jobs.push(job);
    } else if (s === 'interview') {
      cols.interview.jobs.push(job);
    } else if (s === 'offer') {
      cols.offer.jobs.push(job);
    } else if (s === 'rejected' || s === 'dismissed') {
      cols.closed.jobs.push(job);
    } else {
      cols.saved.jobs.push(job);
    }
  }

  return cols;
}

export function comparisonPreferences(current, hasSkills) {
  return {...current, sort: 'fit', comparable_only: Boolean(hasSkills)};
}

export function deadlineCalendar(program, now = new Date()) {
  if (!program.deadline) throw new Error('This program has no confirmed deadline.');
  const escape = text => String(text).replaceAll('\\','\\\\').replaceAll('\n','\\n').replaceAll(',','\\,').replaceAll(';','\\;');
  const utc = date => new Date(date).toISOString().replace(/[-:]/g,'').replace(/\.\d{3}Z$/,'Z');
  const lines=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//workBee//Program deadlines//EN','BEGIN:VEVENT','UID:'+escape(program.id+'-'+program.deadline+'@workbee.local'),'DTSTAMP:'+utc(now)];
  if(program.deadline_at)lines.push('DTSTART:'+utc(program.deadline_at));
  else {const next=new Date(program.deadline+'T00:00:00Z');next.setUTCDate(next.getUTCDate()+1);lines.push('DTSTART;VALUE=DATE:'+program.deadline.replaceAll('-',''),'DTEND;VALUE=DATE:'+next.toISOString().slice(0,10).replaceAll('-',''));}
  lines.push('SUMMARY:'+escape(program.title+' application deadline'),'DESCRIPTION:'+escape((program.deadline_note||'Deadline date; cutoff time not published.')+'\nConfirm current requirements on the official page.\n'+program.source_url),'END:VEVENT','END:VCALENDAR');
  return lines.join('\r\n')+'\r\n';
}

export function mergeProfileSkills(existing, imported, replace=false) {
  const merged=new Map();
  const example=text=>/\b(built|developed|designed|created|analy[sz]ed|implemented|managed|automated|conducted|taught|wrote|coordinated|interviewed|collected|project|coursework|capstone|thesis|laboratory)\b/i.test(text||'');
  for(const skill of [...(replace?[]:existing),...imported]){
    const key=skill.skill.toLowerCase();
    const previous=merged.get(key);
    if(!previous||(!previous.evidence&&skill.evidence)||(!example(previous.evidence)&&example(skill.evidence)))merged.set(key,skill);
  }
  const values=[...merged.values()];
  if(values.length>60)throw new Error('The merged profile exceeds 60 skills. Remove a few skills or choose Replace before applying.');
  return values;
}

export function preferenceChoices(preferences,key,legacy){
  if(Array.isArray(preferences[key])&&preferences[key].length)return [...new Set(preferences[key])];
  return preferences[legacy]&&preferences[legacy]!=='all'?[preferences[legacy]]:[];
}

export function applicationsCSV(jobs){
  // Spreadsheet formula prefixes are neutralized even inside CSV quoting.
  const cell=value=>{let s=String(value??'');if(/^[\s]*[=+@-]/.test(s))s="'"+s;return '"'+s.replaceAll('"','""')+'"'};
  return '\uFEFF'+[['Company','Opportunity','Stage','Next action','Follow-up date','Notes','Employer link'],...jobs.map(j=>[j.company,j.title,j.status,j.details?.next_action,j.details?.follow_up,j.details?.notes,j.apply_url])].map(row=>row.map(cell).join(',')).join('\r\n');
}

export const BEE_PERSONAS = [
  { id: 'scholar', name: 'Scholar Bee', track: 'General & Academics', desc: 'Curious student exploring internships & programs' },
  { id: 'code', name: 'Code Bee', track: 'Software & Computing', desc: 'Developer building apps, systems & algorithms' },
  { id: 'data', name: 'Data Bee', track: 'AI & Data Science', desc: 'Model trainer, data analyst & quantitative thinker' },
  { id: 'research', name: 'Research Bee', track: 'Lab & Sciences', desc: 'Scientist discovering breakthroughs in labs & R&D' },
  { id: 'design', name: 'Design Bee', track: 'Product & Creative', desc: 'Creator designing intuitive interfaces & visuals' },
  { id: 'business', name: 'Business Bee', track: 'Finance & Strategy', desc: 'Strategist analyzing markets, finance & growth' },
  { id: 'health', name: 'Health Bee', track: 'Bio & Healthcare', desc: 'Care practitioner, clinical & biotech innovator' },
];

export function detectOccupation(headline = '', major = '', skillsText = '') {
  const combined = `${headline} ${major} ${skillsText}`.toLowerCase();
  if (/(health|med\b|medicine|nursing|doctor|clinical|pharma|biomed|hospital)/.test(combined)) {
    return 'health';
  }
  if (/(code|software|developer|computer|cs\b|web|frontend|backend|fullstack|programming|devops|cloud|react|python|java\b|c\+\+|golang)/.test(combined)) {
    return 'code';
  }
  if (/(data science|machine learning|ai\b|artificial intelligence|deep learning|nlp|analytics|statistic|big data|tableau)/.test(combined)) {
    return 'data';
  }
  if (/(research|lab\b|physics|chemistry|neuro|genetics|biotech|scientific|r&d)/.test(combined)) {
    return 'research';
  }
  if (/(design|ui\b|ux\b|graphic|creative|product design|figma|visual|artist|animation)/.test(combined)) {
    return 'design';
  }
  if (/(business|finance|consulting|accounting|marketing|economics|management|product manager|banking|equity)/.test(combined)) {
    return 'business';
  }
  return 'scholar';
}

export function getBeeMascotSvg(occupation = 'scholar', size = 48, className = 'bee-mascot-avatar') {
  const persona = BEE_PERSONAS.find(p => p.id === occupation) || BEE_PERSONAS[0];
  const bgColors = {
    scholar: '#FEF3C7',
    code: '#E0E7FF',
    data: '#CFFAFE',
    research: '#EDE9FE',
    design: '#FCE7F3',
    business: '#E2E8F0',
    health: '#D1FAE5',
  };
  const bg = bgColors[persona.id] || '#FEF3C7';

  let accessory = '';
  if (persona.id === 'scholar') {
    accessory = `<polygon points="32,7 13,15 32,21 51,15" fill="#1E293B" stroke="#0E1D35" stroke-width="1.2"/><polygon points="23,17 23,22 41,22 41,17" fill="#0F172A"/><circle cx="32" cy="14" r="1.6" fill="#F59E0B"/><path d="M32 14 C38 15, 43 18, 44 24" stroke="#F59E0B" stroke-width="1.6" fill="none"/><circle cx="44" cy="25" r="1.4" fill="#F59E0B"/>`;
  } else if (persona.id === 'code') {
    accessory = `<rect x="20" y="24" width="10" height="9" rx="3" fill="rgba(59, 130, 246, 0.2)" stroke="#2563EB" stroke-width="1.8"/><rect x="34" y="24" width="10" height="9" rx="3" fill="rgba(59, 130, 246, 0.2)" stroke="#2563EB" stroke-width="1.8"/><line x1="30" y1="28.5" x2="34" y2="28.5" stroke="#2563EB" stroke-width="1.8"/><rect x="25" y="44" width="14" height="8" rx="2" fill="#0E1D35"/><text x="32" y="50" font-size="5.5" font-weight="bold" fill="#38BDF8" text-anchor="middle" font-family="monospace">&lt;/&gt;</text>`;
  } else if (persona.id === 'data') {
    accessory = `<path d="M19 25 Q32 22 45 25 L44 32 Q32 29 20 32 Z" fill="rgba(6, 182, 212, 0.3)" stroke="#06B6D4" stroke-width="1.8"/><circle cx="28" cy="28.5" r="1.2" fill="#22D3EE"/><circle cx="36" cy="28.5" r="1.2" fill="#22D3EE"/><rect x="25" y="45" width="3" height="6" rx="1" fill="#06B6D4"/><rect x="30" y="43" width="3" height="8" rx="1" fill="#38BDF8"/><rect x="35" y="41" width="3" height="10" rx="1" fill="#818CF8"/>`;
  } else if (persona.id === 'research') {
    accessory = `<circle cx="25" cy="28.5" r="5" fill="rgba(168, 85, 247, 0.2)" stroke="#9333EA" stroke-width="1.8"/><circle cx="39" cy="28.5" r="5" fill="rgba(168, 85, 247, 0.2)" stroke="#9333EA" stroke-width="1.8"/><line x1="30" y1="28.5" x2="34" y2="28.5" stroke="#9333EA" stroke-width="1.8"/><path d="M46 38 L48 42 L44 49 L52 49 L48 42 L46 38 Z" fill="#A855F7" stroke="#0E1D35" stroke-width="1.2"/><circle cx="48" cy="46" r="1" fill="#ffffff"/>`;
  } else if (persona.id === 'design') {
    accessory = `<ellipse cx="28" cy="14" rx="13" ry="5.5" transform="rotate(-15 28 14)" fill="#EC4899"/><circle cx="23" cy="9.5" r="1.5" fill="#BE185D"/><ellipse cx="32" cy="47" rx="7" ry="5" fill="#ffffff" stroke="#0E1D35" stroke-width="1"/><circle cx="29" cy="46" r="1.1" fill="#EF4444"/><circle cx="32" cy="45" r="1.1" fill="#3B82F6"/><circle cx="35" cy="46" r="1.1" fill="#10B981"/>`;
  } else if (persona.id === 'business') {
    accessory = `<polygon points="26,37 32,40 29,45 25,39" fill="#ffffff" stroke="#0E1D35" stroke-width="1"/><polygon points="38,37 32,40 35,45 39,39" fill="#ffffff" stroke="#0E1D35" stroke-width="1"/><polygon points="31,40 33,40 34,48 32,51 30,48" fill="#DC2626"/><rect x="44" y="38" width="9" height="7.5" rx="1.5" fill="#78350F" stroke="#0E1D35" stroke-width="1"/><path d="M46.5 38 V36.5 H50.5 V38" stroke="#0E1D35" stroke-width="1" fill="none"/>`;
  } else if (persona.id === 'health') {
    accessory = `<rect x="18" y="17" width="28" height="2.2" rx="1" fill="#0E1D35"/><circle cx="32" cy="18" r="4.2" fill="#E2E8F0" stroke="#0E1D35" stroke-width="1.4"/><circle cx="32" cy="18" r="1.3" fill="#0E1D35"/><path d="M21 34 Q32 45 43 34" stroke="#0D9488" stroke-width="1.8" fill="none"/><circle cx="32" cy="44" r="2.2" fill="#14B8A6" stroke="#0E1D35" stroke-width="1"/>`;
  }

  return `<svg width="${size}" height="${size}" viewBox="0 0 64 64" fill="none" class="${className}" aria-label="${persona.name}"><circle cx="32" cy="32" r="30" fill="${bg}"/><path d="M26 18 C24 12, 18 10, 16 12" stroke="#0E1D35" stroke-width="2.5" stroke-linecap="round" fill="none"/><circle cx="16" cy="12" r="2.5" fill="#F59E0B"/><path d="M38 18 C40 12, 46 10, 48 12" stroke="#0E1D35" stroke-width="2.5" stroke-linecap="round" fill="none"/><circle cx="48" cy="12" r="2.5" fill="#F59E0B"/><ellipse cx="19" cy="27" rx="10" ry="6" transform="rotate(-25 19 27)" fill="rgba(186, 230, 253, 0.85)" stroke="#38BDF8" stroke-width="1.5"/><ellipse cx="45" cy="27" rx="10" ry="6" transform="rotate(25 45 27)" fill="rgba(186, 230, 253, 0.85)" stroke="#38BDF8" stroke-width="1.5"/><ellipse cx="32" cy="35" rx="17" ry="19" fill="#FBBF24"/><path d="M16 32 Q32 37 48 32" stroke="#0E1D35" stroke-width="4.5" stroke-linecap="round" fill="none"/><path d="M17 40 Q32 45 47 40" stroke="#0E1D35" stroke-width="4.5" stroke-linecap="round" fill="none"/><circle cx="26" cy="28.5" r="2.5" fill="#0E1D35"/><circle cx="27" cy="27.5" r="0.9" fill="#ffffff"/><circle cx="38" cy="28.5" r="2.5" fill="#0E1D35"/><circle cx="39" cy="27.5" r="0.9" fill="#ffffff"/><circle cx="22" cy="33.5" r="2.2" fill="#F472B6" opacity="0.6"/><circle cx="42" cy="33.5" r="2.2" fill="#F472B6" opacity="0.6"/><path d="M29 33 Q32 36 35 33" stroke="#0E1D35" stroke-width="1.8" stroke-linecap="round" fill="none"/><polygon points="32,54 29.5,49 34.5,49" fill="#0E1D35"/>${accessory}</svg>`.trim();
}
