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
  const example=text=>/\b(built|developed|designed|created|analy[sz]ed|implemented|managed|automated|project|coursework|capstone|thesis|laboratory)\b/i.test(text||'');
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
