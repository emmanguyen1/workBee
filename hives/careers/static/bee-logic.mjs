export function resourceURL(value){
  try{const url=new URL(value);return url.protocol==='https:'&&!url.username&&!url.password?url.href:null}catch{return null}
}

// Provider offsets count Unicode characters; use code points rather than UTF-16 units.
export function citationParts(text,citations=[]){
  const chars=Array.from(text),parts=[];let cursor=0,number=0;
  for(const c of [...citations].sort((a,b)=>a.start-b.start)){
    const url=resourceURL(c.url);
    if(!url||!Number.isInteger(c.start)||!Number.isInteger(c.end)||c.start<cursor||c.end<=c.start||c.end>chars.length)continue;
    if(c.start>cursor)parts.push({text:chars.slice(cursor,c.start).join('')});
    parts.push({text:' ['+(++number)+'] ',url,title:c.title||url});cursor=c.end;
  }
  if(cursor<chars.length)parts.push({text:chars.slice(cursor).join('')});
  return parts;
}
