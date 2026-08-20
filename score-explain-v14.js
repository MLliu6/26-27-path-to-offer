(function(){
  'use strict';
  if(typeof openMarketJob!=='function'||!window.PTO_MATCHING)return;
  const baseOpen=openMarketJob;
  const $=s=>document.querySelector(s);

  function jobById(id){return (marketJobs||[]).find(j=>String(j.id)===String(id));}
  function enhanceAudit(id){
    const audit=$('.pto-v14-audit');const job=jobById(id);if(!audit||!job)return;
    // Keep the stable semantic hook used by the long-running browser journey,
    // but the visible content is the v1.4 Fit + Evidence model rather than the
    // old additive eight-dimension score.
    audit.classList.add('pto-score-audit');
    const h4=audit.querySelector('h4');
    if(h4&&!h4.textContent.includes('匹配评分明细'))h4.textContent=`匹配评分明细 · ${h4.textContent}`;
    const grid=audit.querySelector('.pto-v14-dims');
    if(!grid||grid.querySelector('[data-v14-source-dim]'))return;
    const match=scoreJob(job,currentProfile());const source=Number(match?.components?.source||0);
    grid.insertAdjacentHTML('beforeend',`<div class="pto-v14-dim" data-v14-source-dim><span>来源可信度 / 7</span><strong>${source.toFixed(1).replace(/\.0$/,'')}</strong></div>`);
  }

  openMarketJob=function(id){const out=baseOpen(id);enhanceAudit(id);return out;};
})();