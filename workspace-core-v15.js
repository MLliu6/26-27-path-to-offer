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
  function mergeJobs(...groups){const map=new Map();for(const j of groups.flat()){if(!j||typeof j!=='object'||!role(j)||!company(j))continue;const k=identity(j);if(!map.has(k)||quality(j)>quality(map.get(k)))map.set(k,j);}const all=[...map.values()],concrete=all.filter(j=>!isLead(j)),keys=new Set(concrete.map(j=>company(j)+'|'+role(j)+'|'+location(j))),destinations=new Map();for(const j of all.filter(j=>!isLead(j)||positionId(j)||!keys.has(company(j)+'|'+role(j)+'|'+location(j)))){const u=canonicalUrl(j.u??j.apply_url??j.applyUrl??j.url),k=u?company(j)+'|'+role(j)+'|'+location(j)+'|'+u:identity(j);if(!destinations.has(k)||quality(j)>quality(destinations.get(k)))destinations.set(k,j);}return [...destinations.values()];}
  function localDate(d=new Date()){return [d.getFullYear(),String(d.getMonth()+1).padStart(2,'0'),String(d.getDate()).padStart(2,'0')].join('-');}
  function dateValue(value){const raw=text(value);if(!raw)return '';const numeric=/^\d{10,13}$/.test(raw)?Number(raw)*(raw.length===10?1000:1):raw;const d=new Date(numeric);return Number.isNaN(d.getTime())?'':d.toISOString().slice(0,10);}
  const cityAliases={beijing:'北京',shanghai:'上海',shenzhen:'深圳',guangzhou:'广州',hangzhou:'杭州',nanjing:'南京',chengdu:'成都',wuhan:'武汉',suzhou:'苏州',tianjin:'天津',hefei:'合肥',changsha:'长沙',chongqing:'重庆',"xi'an":'西安',xian:'西安'};
  const cityCodes={'110000':'北京','120000':'天津','310000':'上海','500000':'重庆','440300':'深圳','440100':'广州','330100':'杭州','320100':'南京','320500':'苏州','420100':'武汉','510100':'成都','610100':'西安','340100':'合肥'};
  const cityList='北京 上海 深圳 广州 杭州 南京 成都 武汉 西安 苏州 天津 合肥 长沙 重庆 宁波 青岛 济南 厦门 福州 无锡 郑州 东莞 佛山 珠海 大连 沈阳 长春 哈尔滨 昆明 南宁 贵阳 海口 南昌 常州 扬州 南通 嘉兴 绍兴 温州 石家庄 太原 乌鲁木齐 兰州 银川 西宁 拉萨 呼和浩特 香港 澳门 台北 全国 远程'.split(' ');
  function cityNames(value){const raw=text(value);const names=cityList.filter(c=>raw.includes(c));for(const [alias,city] of Object.entries(cityAliases))if(new RegExp(`\\b${alias}\\b`,'i').test(raw))names.push(city);for(const code of raw.match(/\d{6}/g)||[])if(cityCodes[code])names.push(cityCodes[code]);return [...new Set(names)];}
  const closed=j=>['rejected','signed'].includes(j.status);
  function summary(jobs,date=localDate()){return {total:jobs.length,active:jobs.filter(j=>!closed(j)).length,interview:jobs.filter(j=>/^interview|^hr$/.test(j.status)).length,due:jobs.filter(j=>!closed(j)&&j.followUpAt&&j.followUpAt<=date).length,offer:jobs.filter(j=>['offer','signed'].includes(j.status)).length};}
  function updateStatus(job,status,date,note='',followUpAt=''){if(!job||!/^\d{4}-\d\d-\d\d$/.test(date))throw Error('请选择状态日期');const out=JSON.parse(JSON.stringify(job));out.timeline=Array.isArray(out.timeline)?out.timeline:[];if(status!==out.status||date!==out.statusDate||note)out.timeline.push({status,date,...(note?{note}: {})});return {...out,status,statusDate:date,followUpAt,nextAction:note||out.nextAction||'',updatedAt:new Date().toISOString()};}
  return {canonicalUrl,positionId,isLead,official,identity,mergeJobs,localDate,dateValue,cityNames,summary,updateStatus,company};
});
