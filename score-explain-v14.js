(function(){
  'use strict';
  if(typeof openMarketJob!=='function'||!window.PTO_MATCHING)return;
  const baseOpen=openMarketJob;
  const $=s=>document.querySelector(s);

  function jobById(id){return (marketJobs||[]).find(j=>String(j.id)===String(id));}
  function enhanceAudit(id){
    const audit=$('.pto-v14-audit');const job=jobById(id);if(!audit||!job)return;
    audit.classList.add('pto-score-audit');
    const match=scoreJob(job,currentProfile()),c=match.components||{};
    const dimensions=[['职业方向',c.domainExact?'同领域':c.domainMismatch?'领域差异较大':'相邻方向或待确认'],['岗位技能',c.skillRequired?`${c.skillHits} / ${c.skillRequired} 项`:'待补充'],['届别与学历',(match.reasons||[]).filter(r=>/届符合|学历/.test(r)).join(' · ')||'待确认'],['来源可信度 / 7',`${Number(c.source||0)} / 7`]];
    audit.innerHTML=`<div class="pto-v14-audit-head"><div><h4>匹配评分明细</h4><p>结合职业方向、岗位要求与求职偏好，判断当前简历的适配程度。</p></div><div class="pto-v14-scores"><div class="pto-v14-score"><small>匹配度</small><strong>${match.score??'—'}</strong><span>${esc(match.band||'待补充')}</span></div><div class="pto-v14-score"><small>信息充分度</small><strong>${match.evidenceConfidence??'—'}</strong><span>${esc(match.evidenceLabel||'待核验')}</span></div></div></div><div class="pto-v14-dims">${dimensions.map(([label,value])=>`<div class="pto-v14-dim"><span>${esc(label)}</span><strong>${esc(value)}</strong></div>`).join('')}</div>${match.hits?.length?`<p><strong>已匹配</strong> ${match.hits.map(esc).join(' · ')}</p>`:''}${c.missingSkills?.length?`<p><strong>待补充证据</strong> ${c.missingSkills.map(esc).join(' · ')}</p>`:''}${c.calibrationCap<80?`<p>${(match.reasons||[]).filter(x=>/冲突|不满足|社会招聘/.test(x)||x===c.roleGap).map(esc).join(' · ')||'结合具体岗位要求评估后再投递'}</p>`:''}`;
  }

  openMarketJob=function(id){const out=baseOpen(id);enhanceAudit(id);return out;};

  // Load the kanban timeline only after the older account/pipeline enhancers have
  // finished defining pipelineCard. Keeping it last prevents an older override
  // from silently removing the visible status history.
  if(!window.PTO_PIPELINE_TIMELINE_V14&&!document.querySelector('script[data-pto-timeline-v14]')){
    const script=document.createElement('script');
    script.dataset.ptoTimelineV14='1';
    script.src=`pipeline-timeline-v14.js?v=${encodeURIComponent(window.PTO_CONFIG?.buildVersion||window.PTO_CONFIG?.version||'1.4.0')}`;
    script.onerror=()=>console.warn('Path to Offer kanban timeline enhancement failed to load');
    document.head.appendChild(script);
  }
})();
