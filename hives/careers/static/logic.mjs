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

export function googleCalendarUrl({ title = '', company = '', deadline = '', deadline_at = '', apply_url = '', notes = '' }) {
  if (!deadline && !deadline_at) return '';
  const dateStr = deadline_at
    ? new Date(deadline_at).toISOString().replace(/[-:]/g, '').replace(/\.\d{3}Z$/, 'Z')
    : deadline.replace(/-/g, '');
  const dates = deadline_at ? `${dateStr}/${dateStr}` : `${dateStr}/${dateStr}`;
  const eventTitle = `[Apply] ${company ? company + ' - ' : ''}${title || 'Application Deadline'}`;
  const details = [
    company ? `Company: ${company}` : '',
    title ? `Role: ${title}` : '',
    apply_url ? `Job Link: ${apply_url}` : '',
    notes ? `Notes: ${notes}` : '',
    'Tracked with workBee'
  ].filter(Boolean).join('\n\n');
  const params = new URLSearchParams({
    action: 'TEMPLATE',
    text: eventTitle,
    dates,
    details
  });
  return `https://calendar.google.com/calendar/render?${params.toString()}`;
}

export function pipelineCalendarIcs(applications = [], now = new Date()) {
  const escape = text => String(text || '').replaceAll('\\', '\\\\').replaceAll('\n', '\\n').replaceAll(',', '\\,').replaceAll(';', '\\;');
  const utc = date => new Date(date).toISOString().replace(/[-:]/g, '').replace(/\.\d{3}Z$/, 'Z');

  const events = [];
  for (const job of applications) {
    const deadline = job.deadline_date || job.deadline || job.details?.deadline || job.details?.follow_up;
    if (!deadline) continue;

    const company = job.company || 'Employer';
    const title = job.title || 'Role';
    const url = job.apply_url || job.source_url || '';
    const notes = job.details?.notes || '';
    const jobId = job.id || `${company}-${title}`.toLowerCase().replace(/[^a-z0-9]/g, '-');

    // 1. Due Date Event
    const eventLines = [
      'BEGIN:VEVENT',
      `UID:${escape(jobId)}-deadline@workbee.local`,
      `DTSTAMP:${utc(now)}`
    ];

    if (job.deadline_at) {
      eventLines.push(`DTSTART:${utc(job.deadline_at)}`);
    } else {
      const nextDay = new Date(deadline + 'T00:00:00Z');
      nextDay.setUTCDate(nextDay.getUTCDate() + 1);
      eventLines.push(`DTSTART;VALUE=DATE:${deadline.replaceAll('-', '')}`);
      eventLines.push(`DTEND;VALUE=DATE:${nextDay.toISOString().slice(0, 10).replaceAll('-', '')}`);
    }

    eventLines.push(
      `SUMMARY:${escape(`[Deadline] ${company} - ${title}`)}`,
      `DESCRIPTION:${escape(`Application deadline for ${title} at ${company}.\nStatus: ${job.status || 'Applied'}\n${url ? 'Link: ' + url + '\n' : ''}${notes ? 'Notes: ' + notes + '\n' : ''}Tracked on workBee.`)}`,
      'END:VEVENT'
    );
    events.push(eventLines.join('\r\n'));

    // 2. Prep Milestone Reminder (3 days prior if deadline is a standard YYYY-MM-DD date)
    try {
      const dDate = new Date(job.deadline_at || deadline + 'T00:00:00Z');
      if (!isNaN(dDate.getTime())) {
        const reminderDate = new Date(dDate.getTime() - 3 * 24 * 60 * 60 * 1000);
        const reminderDay = reminderDate.toISOString().slice(0, 10);
        const reminderNext = new Date(reminderDay + 'T00:00:00Z');
        reminderNext.setUTCDate(reminderNext.getUTCDate() + 1);

        const reminderLines = [
          'BEGIN:VEVENT',
          `UID:${escape(jobId)}-prep3d@workbee.local`,
          `DTSTAMP:${utc(now)}`,
          `DTSTART;VALUE=DATE:${reminderDay.replaceAll('-', '')}`,
          `DTEND;VALUE=DATE:${reminderNext.toISOString().slice(0, 10).replaceAll('-', '')}`,
          `SUMMARY:${escape(`[Prep Milestone] 3 days until ${company} (${title}) deadline`)}`,
          `DESCRIPTION:${escape(`Reminder: 3 days remaining before ${company} application closes (${deadline}).\nReview your materials and submit on ${url || 'the official portal'}.`)}`,
          'END:VEVENT'
        ];
        events.push(reminderLines.join('\r\n'));
      }
    } catch {}
  }

  const calendarLines = [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//workBee//Pipeline Deadlines//EN',
    'CALSCALE:GREGORIAN',
    'X-WR-CALNAME:workBee Application Deadlines',
    ...events,
    'END:VCALENDAR'
  ];

  return calendarLines.join('\r\n') + '\r\n';
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
    // Graduation cap matching the authentic character
    accessory = `
      <polygon points="32,6 12,14 32,20 52,14" fill="#1E293B" stroke="#0E1D35" stroke-width="1.2"/>
      <polygon points="23,16 23,21 41,21 41,16" fill="#0F172A"/>
      <circle cx="32" cy="13.5" r="1.6" fill="#F59E0B"/>
      <path d="M32 13.5 C38 14.5, 43 17, 44 23" stroke="#F59E0B" stroke-width="1.6" fill="none"/>
      <circle cx="44" cy="24" r="1.4" fill="#F59E0B"/>
    `;
  } else if (persona.id === 'code') {
    // Developer glasses + code badge
    accessory = `
      <rect x="21" y="21" width="10" height="8.5" rx="3" fill="rgba(59, 130, 246, 0.25)" stroke="#2563EB" stroke-width="1.8"/>
      <rect x="33" y="21" width="10" height="8.5" rx="3" fill="rgba(59, 130, 246, 0.25)" stroke="#2563EB" stroke-width="1.8"/>
      <line x1="31" y1="25" x2="33" y2="25" stroke="#2563EB" stroke-width="1.8"/>
      <rect x="25" y="47" width="14" height="7.5" rx="2" fill="#0E1D35"/>
      <text x="32" y="53" font-size="5" font-weight="bold" fill="#38BDF8" text-anchor="middle" font-family="monospace">&lt;/&gt;</text>
    `;
  } else if (persona.id === 'data') {
    // AR visor + data nodes
    accessory = `
      <path d="M20 22 Q32 19 44 22 L43 28 Q32 25 21 28 Z" fill="rgba(6, 182, 212, 0.35)" stroke="#06B6D4" stroke-width="1.8"/>
      <circle cx="27" cy="25" r="1.2" fill="#22D3EE"/>
      <circle cx="37" cy="25" r="1.2" fill="#22D3EE"/>
      <rect x="26" y="48" width="3" height="5" rx="1" fill="#06B6D4"/>
      <rect x="30.5" y="46" width="3" height="7" rx="1" fill="#38BDF8"/>
      <rect x="35" y="44" width="3" height="9" rx="1" fill="#818CF8"/>
    `;
  } else if (persona.id === 'research') {
    // Lab goggles + flask
    accessory = `
      <circle cx="26" cy="25" r="5" fill="rgba(168, 85, 247, 0.25)" stroke="#9333EA" stroke-width="1.8"/>
      <circle cx="38" cy="25" r="5" fill="rgba(168, 85, 247, 0.25)" stroke="#9333EA" stroke-width="1.8"/>
      <line x1="31" y1="25" x2="33" y2="25" stroke="#9333EA" stroke-width="1.8"/>
      <path d="M46 36 L48 40 L44 47 L52 47 L48 40 L46 36 Z" fill="#A855F7" stroke="#0E1D35" stroke-width="1.2"/>
      <circle cx="48" cy="44" r="1" fill="#ffffff"/>
    `;
  } else if (persona.id === 'design') {
    // Artist French beret + palette
    accessory = `
      <ellipse cx="28" cy="14" rx="13" ry="5.5" transform="rotate(-15 28 14)" fill="#EC4899"/>
      <circle cx="23" cy="9.5" r="1.5" fill="#BE185D"/>
      <ellipse cx="25" cy="47" rx="6" ry="4.5" fill="#ffffff" stroke="#0E1D35" stroke-width="1"/>
      <circle cx="22.5" cy="46" r="1" fill="#EF4444"/>
      <circle cx="25" cy="45" r="1" fill="#3B82F6"/>
      <circle cx="27.5" cy="46" r="1" fill="#10B981"/>
    `;
  } else if (persona.id === 'business') {
    // Executive necktie & briefcase
    accessory = `
      <polygon points="31,39 33,39 34,47 32,50 30,47" fill="#DC2626"/>
      <rect x="44" y="37" width="9" height="7.5" rx="1.5" fill="#78350F" stroke="#0E1D35" stroke-width="1"/>
      <path d="M46.5 37 V35.5 H50.5 V37" stroke="#0E1D35" stroke-width="1" fill="none"/>
    `;
  } else if (persona.id === 'health') {
    // Head mirror & stethoscope
    accessory = `
      <rect x="18" y="15" width="28" height="2" rx="1" fill="#0E1D35"/>
      <circle cx="32" cy="16" r="4.2" fill="#E2E8F0" stroke="#0E1D35" stroke-width="1.4"/>
      <circle cx="32" cy="16" r="1.3" fill="#0E1D35"/>
      <path d="M21 33 Q32 44 43 33" stroke="#0D9488" stroke-width="1.8" fill="none"/>
      <circle cx="32" cy="43" r="2.2" fill="#14B8A6" stroke="#0E1D35" stroke-width="1"/>
    `;
  }

  return `
    <svg width="${size}" height="${size}" viewBox="0 0 64 64" fill="none" class="${className}" aria-label="${persona.name}">
      <circle cx="32" cy="32" r="30" fill="${bg}"/>
      <!-- Antennas with round tips -->
      <path d="M26 15 C24 9, 18 7, 16 9" stroke="#0E1D35" stroke-width="2.5" stroke-linecap="round" fill="none"/>
      <circle cx="16" cy="9" r="2.8" fill="#F59E0B" stroke="#0E1D35" stroke-width="0.8"/>
      <path d="M38 15 C40 9, 46 7, 48 9" stroke="#0E1D35" stroke-width="2.5" stroke-linecap="round" fill="none"/>
      <circle cx="48" cy="9" r="2.8" fill="#F59E0B" stroke="#0E1D35" stroke-width="0.8"/>
      <!-- Translucent Wings -->
      <ellipse cx="17" cy="28" rx="10" ry="6" transform="rotate(-28 17 28)" fill="rgba(186, 230, 253, 0.85)" stroke="#38BDF8" stroke-width="1.5"/>
      <ellipse cx="47" cy="28" rx="10" ry="6" transform="rotate(28 47 28)" fill="rgba(186, 230, 253, 0.85)" stroke="#38BDF8" stroke-width="1.5"/>
      <!-- Striped Bee Abdomen below blazer -->
      <ellipse cx="32" cy="46" rx="14" ry="12" fill="#FBBF24"/>
      <path d="M21 44 Q32 47 43 44 M22 50 Q32 53 42 50" stroke="#0E1D35" stroke-width="3" stroke-linecap="round" fill="none"/>
      <polygon points="32,58 29.5,54 34.5,54" fill="#0E1D35"/>
      <!-- Head -->
      <circle cx="32" cy="27" r="14" fill="#FBBF24"/>
      <!-- Big expressive anime eyes with double glossy sparkles -->
      <ellipse cx="26.5" cy="25" rx="3.8" ry="4.5" fill="#0E1D35"/>
      <circle cx="25.2" cy="23.2" r="1.6" fill="#ffffff"/>
      <circle cx="28" cy="26.8" r="0.8" fill="#ffffff"/>
      <ellipse cx="37.5" cy="25" rx="3.8" ry="4.5" fill="#0E1D35"/>
      <circle cx="36.2" cy="23.2" r="1.6" fill="#ffffff"/>
      <circle cx="39" cy="26.8" r="0.8" fill="#ffffff"/>
      <!-- Rosy Cheeks -->
      <ellipse cx="20.5" cy="29" rx="2.5" ry="1.5" fill="#F472B6" opacity="0.6"/>
      <ellipse cx="43.5" cy="29" rx="2.5" ry="1.5" fill="#F472B6" opacity="0.6"/>
      <!-- Happy Open Smile with Rosy Tongue -->
      <path d="M28 29.5 Q32 35 36 29.5 Z" fill="#991B1B"/>
      <path d="M29.5 32 Q32 34.5 34.5 32" stroke="#F472B6" stroke-width="1.8" stroke-linecap="round" fill="none"/>
      <path d="M27 29.5 Q32 35 37 29.5" stroke="#0E1D35" stroke-width="1.8" stroke-linecap="round" fill="none"/>
      <!-- Navy Suit Blazer & White Shirt -->
      <polygon points="27,37 37,37 32,45" fill="#ffffff"/>
      <path d="M19 39 Q25 38 28 44 L25 52 L17 48 Z" fill="#0E1D35"/>
      <path d="M45 39 Q39 38 36 44 L39 52 L47 48 Z" fill="#0E1D35"/>
      <!-- Silver Tablet / Slate in hand -->
      <rect x="34" y="42" width="10" height="13" rx="1.5" transform="rotate(-15 34 42)" fill="#CBD5E1" stroke="#475569" stroke-width="1"/>
      <circle cx="39" cy="48" r="1.4" fill="#94A3B8"/>
      <!-- Paws / Hands -->
      <circle cx="24" cy="45" r="2.5" fill="#0E1D35"/>
      <circle cx="34" cy="46" r="2.5" fill="#0E1D35"/>
      <!-- Role Accessory Overlay -->
      ${accessory}
    </svg>
  `.trim();
}
