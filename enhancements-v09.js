(function(){
  'use strict';
  const $=s=>document.querySelector(s);
  let prioritySources=[];
  const ALIASES={
    '中石油':'中国石油','cnpc':'中国石油','中石化':'中国石化','sinopec':'中国石化','中海油':'中国海油',
    '国网':'国家电网','南网':'南方电网','航天科技':'航天科技集团','航天科工':'航天科工集团','中电科':'中国电科',
    '工行':'中国工商银行','icbc':'中国工商银行','建行':'中国建设银行','ccb':'中国建设银行','中行':'中国银行','boc':'中国银行',
    '农行':'中国农业银行','abc':'中国农业银行','交行':'交通银行','邮储':'中国邮政储蓄银行','招行':'招商银行',
    'galbot':'银河通用','银河':'银河通用','rhino':'辉羲智能','辉羲':'辉羲智能'
  };

  function ensureStyles(){
    if($('#ptoV09Style'))return;
    const style=document.createElement('style');style.id='ptoV09Style';style.textContent=`
      .pto-score-audit{margin-top:14px;padding:14px;border:1px solid var(--line);border-radius:14px;background:color-mix(in srgb,var(--surface) 92%,var(--accent-soft))}
      .pto-score-audit-head{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin-bottom:10px}.pto-score-audit-head h4{font-family:var(--serif);margin:0;font-size:16px}.pto-score-audit-head p{margin:2px 0 0;color:var(--muted);font-size:11px}.pto-score-total{font-family:var(--serif);font-size:25px;color:var(--accent-strong);white-space:nowrap}.pto-score-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px}.pto-score-item{border:1px solid var(--line);background:var(--surface);border-radius:10px;padding:8px 9px;min-width:0}.pto-score-item span{display:block;color:var(--muted);font-size:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.pto-score-item strong{display:block;margin-top:2px;font-family:var(--serif);font-size:15px}.pto-score-note{margin-top:9px;color:var(--muted);font-size:10px;line-height:1.5}.pto-score-note b{color:var(--text)}
      .match-score{position:relative}.match-score:after{content:'8D';position:absolute;right:-4px;top:-5px;font-size:7px;line-height:1;padding:3px;border-radius:999px;background:var(--accent-soft);color:var(--accent-strong);border:1px solid var(--line)}
      .pto-source-fallback{text-align:left;max-width:720px;margin:14px auto 0;border:1px solid var(--line);border-radius:14px;padding:15px 16px;background:var(--surface);box-shadow:0 8px 22px rgba(0,0,0,.035)}.pto-source-fallback-top{display:flex;gap:12px;align-items:flex-start}.pto-source-fallback-icon{width:39px;height:39px;border-radius:12px;display:grid;place-items:center;background:var(--accent-soft);color:var(--accent-strong);font-family:var(--serif);font-weight:700;flex:0 0 auto}.pto-source-fallback h4{margin:0;font-family:var(--serif);font-size:16px}.pto-source-fallback p{margin:4px 0 0!important;font-size:11px}.pto-source-fallback-actions{display:flex;gap:8px;justify-content:flex-end;margin-top:12px}.pto-source-state{display:inline-flex;margin-top:8px;padding:3px 7px;border-radius:999px;background:var(--accent-soft);color:var(--accent-strong);font-size:9px}.pto-source-state.warn{background:#f4efe3;color:#8c7347}
      @media(max-width:760px){.pto-score-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.pto-score-audit-head{align-items:center}.pto-source-fallback-actions{justify-content:stretch}.pto-source-fallback-actions .btn{flex:1}}
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

  function sourceHealth(company){
    const group=(sourceStatus?.sources||[]).find(s=>s?.name==='priority-official-sources');
    const rows=group?.diagnostics?.watch||[];
    return rows.find(x=>String(x.company||'')===company)||null;
  }
  function normalizedCompanyQuery(q){
    const s=String(q||'').trim().toLowerCase();if(!s)return '';
    for(const [alias,name] of Object.entries(ALIASES))if(s===alias.toLowerCase())return name;
    const hit=prioritySources.find(x=>String(x.company||'').toLowerCase()===s||String(x.company||'').toLowerCase().includes(s));
    return hit?.company||'';
  }
  function renderSourceFallback(){
    const q=$('#jobSearch')?.value?.trim()||'';const count=Number(($('#marketCount')?.textContent||'0').replace(/,/g,''))||0;
    if(!q||count)return;
    const company=normalizedCompanyQuery(q);if(!company)return;
    const src=prioritySources.find(x=>x.company===company);if(!src)return;
    const empty=$('#jobMarketEmpty');if(!empty)return;
    let card=$('#ptoSourceFallback');if(card)card.remove();
    const health=sourceHealth(company);const verified=!!health?.year_2027;const ok=health?.ok!==false;
    const message=verified
      ? '该企业官方招聘源已检测到 2027 招聘信号，但当前标准化岗位池尚未提取出与你筛选条件一致的岗位。系统会继续在两小时刷新中解析岗位详情。'
      : '系统已经持续监测该企业的官方招聘入口，但当前刷新尚未取得可验证的 2027 岗位明细。这里不会用旧岗位或第三方猜测冒充当前校招。';
    empty.insertAdjacentHTML('beforeend',`<div class="pto-source-fallback" id="ptoSourceFallback"><div class="pto-source-fallback-top"><div class="pto-source-fallback-icon">源</div><div><h4>${esc(company)} · 官方招聘源已纳入雷达</h4><p>${message}</p><span class="pto-source-state ${ok?'':'warn'}">${verified?'发现 2027 招聘信号':ok?'官方入口可访问 · 等待岗位解析':'官方入口本轮访问异常 · 保留监测'}</span></div></div><div class="pto-source-fallback-actions"><a class="btn ghost" href="${esc(src.url)}" target="_blank" rel="noopener noreferrer">打开官方招聘 ↗</a><button class="btn primary" id="ptoRetrySource">重新刷新岗位</button></div></div>`);
    $('#ptoRetrySource')?.addEventListener('click',()=>$('#refreshFeedBtn')?.click());
  }
  async function loadPrioritySources(){
    try{
      const r=await fetch(`./sources/priority_official_sources.json?v=${encodeURIComponent(window.PTO_CONFIG?.version||Date.now())}`,{cache:'no-store'});
      if(r.ok){const j=await r.json();prioritySources=Array.isArray(j.watch)?j.watch:[];}
    }catch(_){prioritySources=[];}
    renderSourceFallback();
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
    renderMarket=function(){
      const out=baseRender.apply(this,arguments);
      document.querySelectorAll('.match-score').forEach(el=>el.title='v0.9 八维校准评分：方向 / 技能 / 届别资历 / 地点 / 学历毕业 / 来源 / 新鲜度 / 信息完整度');
      renderSourceFallback();
      return out;
    };
  }
  ensureStyles();
  loadPrioritySources();
})();
