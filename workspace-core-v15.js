/* Pure data rules shared by the workspace and regression tests. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.PTO_WORKSPACE_CORE=api;})(typeof globalThis!=='undefined'?globalThis:this,function(){
  'use strict';
  const text=v=>String(v??'').trim();
  const norm=v=>text(v).toLowerCase().replace(/[\s·•（）()—_-]/g,'');
  const aliases={shopee深圳虾皮信息科技有限公司:'shopee',小鹏汽车:'小鹏集团',kimi:'月之暗面',moonshot:'月之暗面',千寻智能spiritai:'千寻智能',英伟达:'nvidia',新浪微博:'新浪',智谱:'智谱ai'};
  const company=j=>aliases[norm(j.c??j.company)]||norm(j.c??j.company);
  const role=j=>norm(j.r??j.role);
  const location=j=>norm(j.l??j.location);
  function canonicalUrl(value){try{const u=new URL(text(value),'https://placeholder.invalid');if(!/^https?:$/.test(u.protocol))return '';for(const k of [...u.searchParams.keys()])if(/^utm_|^(spread|recomId|sourceJobId)$/i.test(k))u.searchParams.delete(k);u.searchParams.sort();return u.origin+u.pathname.replace(/\/$/,'')+u.search+u.hash;}catch(_){return '';}}
  function positionId(j){const explicit=text(j.z??j.position_id??j.positionId);if(explicit)return explicit;const u=text(j.u??j.apply_url??j.applyUrl??j.url);const m=u.match(/[?&](?:positionId|jobAdId|jobId|postId|jobUnionId)=([^&#]+)/i)||u.match(/(?:job-info\/|\/job\/|\/position\/(?:detail\/)?)([a-z\d-]{7,})(?:\/detail)?(?:[/?#]|$)/i);return m?m[1]:'';}
  function isLead(j){return /curated-target|target.lead|待官网.*复核|目标岗位清单/.test([j.s,j.source,j.x,j.sourceLabel,j.b,j.batch,j.verification].join(' '));}
  function official(j){return !isLead(j)&&/direct-official|企业官网|招聘官网|官方.*ATS|official-public|employer-public/.test([j.s,j.source,j.x,j.sourceLabel,j.observed_via,j.observedVia].join(' '));}
  function identity(j){const c=company(j),id=positionId(j);if(id)return `pid:${c}:${id}`;const u=canonicalUrl(j.u??j.apply_url??j.applyUrl??j.url);return `role:${c}:${role(j)}:${location(j)}:${u}`;}
  function quality(j){return (isLead(j)?-1000:0)+(official(j)?100:0)+Number(j.q??j.sourceTier??0)*2+(positionId(j)?15:0)+(text(j.d??j.jd).length>100?3:0);}
  function mergeJobs(...groups){const map=new Map();for(const j of groups.flat()){if(!j||typeof j!=='object'||!role(j)||!company(j))continue;const k=identity(j);if(!map.has(k)||quality(j)>quality(map.get(k)))map.set(k,j);}const all=[...map.values()],concrete=all.filter(j=>!isLead(j)),keys=new Set(concrete.map(j=>company(j)+'|'+role(j)+'|'+location(j)));return all.filter(j=>!isLead(j)||!keys.has(company(j)+'|'+role(j)+'|'+location(j)));}
  function localDate(d=new Date()){return [d.getFullYear(),String(d.getMonth()+1).padStart(2,'0'),String(d.getDate()).padStart(2,'0')].join('-');}
  const closed=j=>['rejected','signed'].includes(j.status);
  function summary(jobs,date=localDate()){return {total:jobs.length,active:jobs.filter(j=>!closed(j)).length,interview:jobs.filter(j=>/^interview|^hr$/.test(j.status)).length,due:jobs.filter(j=>!closed(j)&&j.followUpAt&&j.followUpAt<=date).length,offer:jobs.filter(j=>['offer','signed'].includes(j.status)).length};}
  function updateStatus(job,status,date,note='',followUpAt=''){if(!job||!/^\d{4}-\d\d-\d\d$/.test(date))throw Error('请选择状态日期');const out=JSON.parse(JSON.stringify(job));out.timeline=Array.isArray(out.timeline)?out.timeline:[];if(status!==out.status||date!==out.statusDate||note)out.timeline.push({status,date,...(note?{note}: {})});return {...out,status,statusDate:date,followUpAt,nextAction:note||out.nextAction||'',updatedAt:new Date().toISOString()};}
  return {canonicalUrl,positionId,isLead,official,identity,mergeJobs,localDate,summary,updateStatus,company};
});
