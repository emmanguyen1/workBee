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
