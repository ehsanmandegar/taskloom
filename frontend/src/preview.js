export function resolveMarkdownAsset(documentPath,target){
  const clean=target.trim().replace(/\\/g,'/').split(/[?#]/,1)[0];
  if(!clean||/^[a-z][a-z\d+.-]*:/i.test(clean)||clean.startsWith('//'))return null;
  const parts=clean.startsWith('/')?[]:String(documentPath||'').split('/').slice(0,-1);
  for(const part of clean.split('/')){
    if(!part||part==='.')continue;
    if(part==='..'){
      if(!parts.length)return null;
      parts.pop();
    }else parts.push(part);
  }
  return parts.join('/');
}
