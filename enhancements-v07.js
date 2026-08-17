(function(){
  'use strict';
  const $=s=>document.querySelector(s);
  const $$=s=>[...document.querySelectorAll(s)];

  function ensureStyles(){
    if($('#ptoV07Style'))return;
    const style=document.createElement('style');style.id='ptoV07Style';style.textContent=`
      .job-market>#ptoFlow{width:100%;min-width:0}.pto-flow{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin:12px 0 16px}.pto-flow-step{border:1px solid var(--line);border-radius:12px;padding:10px 12px;background:var(--panel);min-width:0}.pto-flow-step.done{border-color:var(--accent);background:color-mix(in srgb,var(--accent) 10%,var(--panel))}.pto-flow-step strong{display:block;font-size:12px;color:var(--text)}.pto-flow-step small{display:block;margin-top:3px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.pto-quick-cities{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0 14px}.pto-quick-cities button{border:1px solid var(--line);background:var(--panel);color:var(--muted);border-radius:999px;padding:5px 9px;font:inherit;font-size:11px;cursor:pointer}.pto-quick-cities button.active{color:var(--accent-strong);border-color:var(--accent);background:color-mix(in srgb,var(--accent) 12%,var(--panel))}.pto-card-actions{display:flex;gap:6px;margin-left:8px}.pto-card-actions .btn,.pto-card-actions .text-btn{white-space:nowrap}.market-card[tabindex="0"]:focus-visible,.market-table tr[tabindex="0"]:focus-visible{outline:2px solid var(--accent);outline-offset:2px}.pto-source-note{font-size:11px;color:var(--muted);padding:8px 10px;border:1px dashed var(--line);border-radius:10px;margin-top:10px}.pto-source-note strong{color:var(--text)}
      @media(max-width:760px){.pto-flow{grid-template-columns:1fr 1fr}.pto-card-actions{width:100%;margin:8px 0 0;justify-content:flex-end}.market-card-foot{flex-wrap:wrap}}
    `;document.head.appendChild(style);
  }

  function flowState(){
    const p=typeof currentProfile==='function'?currentProfile():null;
    const count=Number(($('#marketCount')?.textContent||'0').replace(/,/g,''))||0;
    const saved=(state?.jobs||[]).length;
    return {p,count,saved};
  }
  function renderFlow(){
    const market=$('.job-market');if(!market)return;
    let el=$('#ptoFlow');
    if(!el){el=document.createElement('div');el.id='ptoFlow';}
    // The flow strip belongs inside the second grid column. v0.7 inserted it as
    // a sibling of `.job-market`, making the browser place the actual market in
    // the 205px left rail on the next grid row. Move even an already-rendered
    // strip into the market so stale DOM/cache cannot reproduce the overlap.
    if(el.parentElement!==market)market.prepend(el);
    const {p,count,saved}=flowState();
    const parsed=p?`${p.signals?.skills?.length||0} 个技能信号`:'等待上传';
    el.innerHTML=`<div class="pto-flow">
      <div class="pto-flow-step ${p?'done':''}"><strong>1 · 上传简历</strong><small>${p?esc(p.name):'PDF / DOCX / TXT'}</small></div>
      <div class="pto-flow-step ${p?'done':''}"><strong>2 · 解析画像</strong><small>${parsed}</small></div>
      <div class="pto-flow-step ${p&&count?'done':''}"><strong>3 · 职位匹配</strong><small>${p?`${count.toLocaleString()} 条当前命中`:'上传后生成推荐'}</small></div>
      <div class="pto-flow-step ${saved?'done':''}"><strong>4 · 投递跟踪</strong><small>${saved?`${saved} 条已加入流程`:'查看详情 → 官网投递'}</small></div>
    </div><div class="pto-quick-cities" id="ptoCities"><button data-pto-city="北京">北京优先</button><button data-pto-city="上海">上海</button><button data-pto-city="深圳">深圳</button><button data-pto-city="杭州">杭州</button><button data-pto-city="广州">广州</button><button data-pto-city="国内">全部国内</button></div>`;
    const targets=state?.preferences?.targetLocations||[];
    $$('#ptoCities [data-pto-city]').forEach(b=>b.classList.toggle('active',b.dataset.ptoCity==='国内'?targets.length===0:targets.length===1&&targets[0]===b.dataset.ptoCity));
  }

  function selectCity(city){
    if(!state?.preferences)return;
    state.preferences.targetLocations=city==='国内'?[]:[city];
    const select=$('#jobLocationFilter');if(select){
      const target=city==='国内'?'all':city;
      const opt=[...select.options].find(o=>o.value===target||o.textContent.includes(target));
      select.value=opt?.value||'all';
    }
    saveState(false);renderMarket();toast(city==='国内'?'已切换为国内岗位优先':'已将 '+city+' 设为首要目标城市');
  }

  function jobById(id){return (marketJobs||[]).find(j=>String(j.id)===String(id));}
  function upgradeRows(){
    $$('[data-market-id]').forEach(el=>{
      el.tabIndex=0;el.setAttribute('role','button');el.setAttribute('aria-label','查看岗位详情');
      if(el.matches('.market-card')){
        const foot=el.querySelector('.market-card-foot');if(!foot||foot.querySelector('.pto-card-actions'))return;
        const id=el.dataset.marketId,j=jobById(id);const actions=document.createElement('div');actions.className='pto-card-actions';
        actions.innerHTML=`<button class="text-btn" data-action="detail" data-open-detail="${esc(id)}">查看详情</button>${j?.applyUrl?`<a class="btn tiny ghost" data-action="apply" data-open-apply="${esc(id)}" href="${esc(j.applyUrl)}" target="_blank" rel="noopener noreferrer">官网投递 ↗</a>`:''}`;
        foot.appendChild(actions);
      }
    });
  }

  const baseRender=typeof renderMarket==='function'?renderMarket:null;
  if(baseRender){
    renderMarket=function(){const out=baseRender.apply(this,arguments);upgradeRows();renderFlow();return out;};
  }

  const baseOpen=typeof openMarketJob==='function'?openMarketJob:null;
  if(baseOpen){
    openMarketJob=function(id){
      const j=jobById(id);if(!j){toast('岗位详情暂不可用，正在刷新岗位池');return;}
      baseOpen(id);
      const detail=$('#marketJobDetail');if(!detail)return;
      const actions=detail.querySelector('.detail-actions');
      if(actions&&!actions.querySelector('[data-copy-apply]')){
        const copy=document.createElement('button');copy.className='btn ghost';copy.dataset.copyApply=id;copy.textContent='复制岗位链接';actions.insertBefore(copy,actions.lastElementChild);
      }
      const note=document.createElement('div');note.className='pto-source-note';
      note.innerHTML=`<strong>来源：</strong>${esc(j.sourceLabel||'公开招聘来源')}。${j.applyUrl?'“官网投递”会直接打开该岗位当前公开申请链接。':'该条记录当前没有可验证的直接申请链接，可先加入流程等待刷新。'}`;
      detail.appendChild(note);
    };
  }

  const baseResume=typeof handleResumeFile==='function'?handleResumeFile:null;
  if(baseResume){
    handleResumeFile=async function(file){
      const before=currentProfile()?.id||'';await baseResume(file);const after=currentProfile();
      if(after&&after.id!==before){
        if(!(state.preferences.targetLocations||[]).length)state.preferences.targetLocations=['北京'];
        saveState(false);
        const threshold=$('#scoreThreshold');if(threshold&&Number(threshold.value)<35)threshold.value='35';
        const search=$('#jobSearch');if(search)search.value='';
        renderAll();switchView('discover');renderFlow();toast('简历已解析，已按国内 / 北京优先生成职位推荐');
      }
    };
  }

  document.addEventListener('click',async e=>{
    const city=e.target.closest('[data-pto-city]');if(city){selectCity(city.dataset.ptoCity);return;}
    const detail=e.target.closest('[data-open-detail]');if(detail){e.preventDefault();e.stopPropagation();openMarketJob(detail.dataset.openDetail);return;}
    const copy=e.target.closest('[data-copy-apply]');if(copy){
      const j=jobById(copy.dataset.copyApply),url=j?.applyUrl||j?.noticeUrl||'';
      if(!url){toast('该岗位暂无可复制的公开链接');return;}
      try{await navigator.clipboard.writeText(url);toast('岗位链接已复制');}catch(_){toast('浏览器未授权剪贴板，请使用官网投递按钮');}
    }
  },true);
  document.addEventListener('keydown',e=>{
    const row=e.target.closest?.('[data-market-id]');if(!row||!['Enter',' '].includes(e.key))return;
    if(e.target.closest('[data-action]'))return;e.preventDefault();openMarketJob(row.dataset.marketId);
  });

  ensureStyles();
  window.addEventListener('load',()=>setTimeout(()=>{upgradeRows();renderFlow();},0));
})();
