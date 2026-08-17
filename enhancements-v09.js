(function(){
  'use strict';
  const $=s=>document.querySelector(s);

  function ensureStyles(){
    if($('#ptoV09Style'))return;
    const style=document.createElement('style');style.id='ptoV09Style';style.textContent=`
      .pto-score-audit{margin-top:14px;padding:14px;border:1px solid var(--line);border-radius:14px;background:color-mix(in srgb,var(--surface) 92%,var(--accent-soft))}
      .pto-score-audit-head{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin-bottom:10px}.pto-score-audit-head h4{font-family:var(--serif);margin:0;font-size:16px}.pto-score-audit-head p{margin:2px 0 0;color:var(--muted);font-size:11px}.pto-score-total{font-family:var(--serif);font-size:25px;color:var(--accent-strong);white-space:nowrap}.pto-score-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px}.pto-score-item{border:1px solid var(--line);background:var(--surface);border-radius:10px;padding:8px 9px;min-width:0}.pto-score-item span{display:block;color:var(--muted);font-size:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.pto-score-item strong{display:block;margin-top:2px;font-family:var(--serif);font-size:15px}.pto-score-note{margin-top:9px;color:var(--muted);font-size:10px;line-height:1.5}.pto-score-note b{color:var(--text)}
      .match-score{position:relative}.match-score:after{content:'8D';position:absolute;right:-4px;top:-5px;font-size:7px;line-height:1;padding:3px;border-radius:999px;background:var(--accent-soft);color:var(--accent-strong);border:1px solid var(--line)}
      @media(max-width:760px){.pto-score-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.pto-score-audit-head{align-items:center}}
    `;document.head.appendChild(style);
  }

  function byId(id){return (marketJobs||[]).find(j=>String(j.id)===String(id));}
  function scoreFor(job){
    const p=typeof currentProfile==='function'?currentProfile():null;if(!p||!window.PTO_MATCHING)return null;
    const age=typeof daysAgo==='function'?daysAgo(job.updatedAt||job.updated_at):999;
    return window.PTO_MATCHING.scoreJob(job,p,{...(state?.preferences||{}),ageDays:age,targetLocations:state?.preferences?.targetLocations||[],targetDirections:state?.preferences?.targetDirections||[]});
  }
  const labels={direction:['方向',30],skills:['技能证据',24],career:['届别/资历',13],location:['地点',10],eligibility:['学历/毕业',8],source:['来源可信度',7],freshness:['新鲜度',5],completeness:['信息完整度',3]};
  function renderAudit(job){
    const match=scoreFor(job);if(!match||match.score===null||!match.components)return '';
    const c=match.components;
    const cells=Object.entries(labels).map(([k,[label,max]])=>`<div class="pto-score-item"><span>${label} / ${max}</span><strong>${Number(c[k]||0).toFixed(1).replace(/\.0$/,'')}</strong></div>`).join('');
    const penalty=Number(c.penalty||0);const cap=Number(c.cap||99);const raw=Number(c.raw||match.score);
    return `<section class="pto-score-audit"><div class="pto-score-audit-head"><div><h4>匹配评分明细</h4><p>方向、技能、届别、城市、学历、来源、新鲜度与信息完整度共同决定。</p></div><div class="pto-score-total">${match.score}</div></div><div class="pto-score-grid">${cells}</div><div class="pto-score-note">原始分 <b>${raw}</b>${penalty?` · 冲突/不确定性扣分 <b>-${penalty}</b>`:''}${cap<99?` · 证据门槛上限 <b>${cap}</b>`:''}。95+ 仅在岗位标题方向、技能证据、校招身份、目标城市和官方来源同时充分时允许出现。</div></section>`;
  }

  const baseOpen=typeof openMarketJob==='function'?openMarketJob:null;
  if(baseOpen){
    openMarketJob=function(id){
      baseOpen(id);
      const job=byId(id),detail=$('#marketJobDetail');if(!job||!detail)return;
      detail.querySelector('.pto-score-audit')?.remove();
      const html=renderAudit(job);if(html)detail.insertAdjacentHTML('beforeend',html);
    };
  }

  const baseRender=typeof renderMarket==='function'?renderMarket:null;
  if(baseRender){
    renderMarket=function(){const out=baseRender.apply(this,arguments);document.querySelectorAll('.match-score').forEach(el=>el.title='v0.9 八维校准评分：方向 / 技能 / 届别资历 / 地点 / 学历毕业 / 来源 / 新鲜度 / 信息完整度');return out;};
  }
  ensureStyles();
})();
