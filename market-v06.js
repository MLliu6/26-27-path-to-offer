(function(){
  'use strict';
  if(typeof renderMarket!=='function'||typeof visibleMarketJobs!=='function')return;

  // Feed schema v4 uses one-character transport keys to keep a 60k static
  // catalogue practical on GitHub Pages. The rest of the app continues to use
  // the stable descriptive in-memory model.
  const baseNormalizeMarketJob=normalizeMarketJob;
  normalizeMarketJob=function(j){
    if(j&&j.c!==undefined&&j.r!==undefined){
      return {
        id:j.i||uid('feed'),source:'federated',sourceLabel:j.x||'公开招聘来源',sourceUrl:'',
        company:j.c||'',department:j.m||'',role:j.r||'',location:j.l||'',salary:j.p||'',
        batch:j.b||'',companyType:j.y||'',industry:j.h||'',graduation:j.g||'',education:j.e||'',
        updatedAt:j.t||'',noticeUrl:j.n||'',applyUrl:j.u||j.n||'',jd:j.d||j.r||'',tags:[]
      };
    }
    return baseNormalizeMarketJob(j);
  };

  const PAGE_SIZE=60;
  let visibleLimit=PAGE_SIZE;
  let lastSignature='';
  let filterCache={len:-1,locations:[],types:[],batches:[]};

  function signature(){
    return [
      document.querySelector('#jobSearch')?.value||'',
      document.querySelector('#jobLocationFilter')?.value||'all',
      document.querySelector('#jobTypeFilter')?.value||'all',
      document.querySelector('#jobBatchFilter')?.value||'all',
      document.querySelector('#scoreThreshold')?.value||'',
      document.querySelector('#freshOnly')?.checked?'1':'0',
      marketSort,marketMode,currentProfile()?.id||'',
      (state.preferences.targetDirections||[]).join('|'),
      (state.preferences.targetLocations||[]).join('|'),
    ].join('::');
  }

  function ensurePager(){
    let el=document.querySelector('#marketPager');
    if(!el){
      el=document.createElement('div');el.id='marketPager';el.className='market-pager';
      const market=document.querySelector('.job-market');market?.appendChild(el);
    }
    return el;
  }
  function ensurePerfStyles(){
    if(document.querySelector('#ptoMarketV06Style'))return;
    const style=document.createElement('style');style.id='ptoMarketV06Style';style.textContent=`
      .market-pager{display:flex;align-items:center;justify-content:center;gap:12px;padding:20px 4px 8px;color:var(--muted);font-size:11px}.market-pager.hidden{display:none}.market-pager strong{color:var(--text)}
      .market-render-meta{font-size:10px;color:var(--muted);margin-left:8px;font-weight:400}.market-render-meta b{color:var(--accent-strong);font-weight:600}
    `;document.head.appendChild(style);
  }

  // Computing select options from 60k rows on every state update is wasted
  // work. Cache the values until the catalogue length changes.
  renderMarketFilters=function(){
    if(filterCache.len!==marketJobs.length){
      filterCache.len=marketJobs.length;
      filterCache.locations=[...new Set(marketJobs.flatMap(j=>String(j.location||'').split(/[ ,，、/]+/).filter(x=>x.length>=2&&x.length<=10)))].sort((a,b)=>a.localeCompare(b,'zh-CN'));
      filterCache.types=[...new Set(marketJobs.map(j=>j.companyType).filter(Boolean))].sort((a,b)=>a.localeCompare(b,'zh-CN'));
      filterCache.batches=[...new Set(marketJobs.map(j=>j.batch).filter(Boolean))].sort((a,b)=>a.localeCompare(b,'zh-CN'));
    }
    fillSelect('#jobLocationFilter',filterCache.locations,'全部地点');
    fillSelect('#jobTypeFilter',filterCache.types,'全部企业性质');
    fillSelect('#jobBatchFilter',filterCache.batches,'全部批次');
  };

  function bindShownRows(){
    document.querySelectorAll('[data-market-id]').forEach(el=>el.addEventListener('click',e=>{if(e.target.closest('[data-action]'))return;openMarketJob(el.dataset.marketId);}));
    document.querySelectorAll('[data-save-job]').forEach(b=>b.onclick=e=>{e.stopPropagation();promoteMarketJob(b.dataset.saveJob);});
    document.querySelectorAll('[data-hide-job]').forEach(b=>b.onclick=e=>{e.stopPropagation();state.decisions[b.dataset.hideJob]='hidden';saveState(false);renderMarket();toast('已隐藏该岗位');});
  }

  renderMarket=function(){
    const sig=signature();if(sig!==lastSignature){visibleLimit=PAGE_SIZE;lastSignature=sig;}
    const t0=performance.now();
    const rows=visibleMarketJobs();
    const rankingMs=Math.round(performance.now()-t0);
    const p=currentProfile();const q=(document.querySelector('#jobSearch')?.value||'').trim();
    const shown=rows.slice(0,visibleLimit);
    document.querySelector('#marketCount').textContent=rows.length.toLocaleString();

    const head=document.querySelector('.market-head h2');
    let meta=document.querySelector('#marketRenderMeta');
    if(head&&!meta){meta=document.createElement('span');meta.id='marketRenderMeta';meta.className='market-render-meta';head.appendChild(meta);}
    if(meta)meta.innerHTML=`显示 <b>${shown.length.toLocaleString()}</b> · 排序 ${rankingMs} ms`;

    const empty=document.querySelector('#jobMarketEmpty');
    if(!marketJobs.length){
      empty.classList.remove('hidden');
      empty.innerHTML='<div class="empty-orbit">⌁</div><h3>岗位聚合源目前是空的</h3><p>后台联邦检索器会每两小时刷新；不会用虚构职位填充页面。</p><button class="text-btn" id="emptySourcesBtn">查看岗位源状态 →</button>';
      document.querySelector('#jobMarketCards').innerHTML='';document.querySelector('#jobMarketTable').innerHTML='';document.querySelector('#emptySourcesBtn').onclick=showSources;ensurePager().classList.add('hidden');return;
    }
    if(q&&!rows.length){
      empty.classList.remove('hidden');
      empty.innerHTML=`<div class="empty-orbit">⌕</div><h3>当前岗位池暂未命中“${esc(q)}”</h3><p>明确搜索已经绕过最低 Match 阈值与“30 天内”过滤，因此这里的 0 代表当前联邦岗位池确实没有命中，而不是简历匹配把它过滤掉。</p><button class="text-btn" id="emptySourcesBtn">查看岗位源状态 →</button>`;
      document.querySelector('#emptySourcesBtn').onclick=showSources;
    }else if(!p&&!q){
      empty.classList.remove('hidden');empty.innerHTML='<div class="empty-orbit">CV</div><h3>岗位池已就绪</h3><p>可直接搜索公司/岗位；上传简历后再生成个性化排序与解释。</p>';
    }else if(!rows.length){
      empty.classList.remove('hidden');empty.innerHTML='<div class="empty-orbit">0</div><h3>当前推荐条件没有命中</h3><p>降低最低匹配度、关闭“30 天内”，或调整目标方向与城市。</p>';
    }else empty.classList.add('hidden');

    const cards=document.querySelector('#jobMarketCards');cards.innerHTML=shown.map(marketJobCard).join('');cards.classList.toggle('hidden',marketMode!=='cards');
    const table=document.querySelector('#jobMarketTable');table.classList.toggle('hidden',marketMode!=='table');table.innerHTML=marketJobTable(shown);
    bindShownRows();

    const pager=ensurePager();pager.classList.toggle('hidden',rows.length<=shown.length);
    if(rows.length>shown.length){
      pager.innerHTML=`<span>已显示 <strong>${shown.length.toLocaleString()}</strong> / ${rows.length.toLocaleString()}</span><button class="btn ghost" id="marketLoadMore">再显示 ${Math.min(PAGE_SIZE,rows.length-shown.length)} 条</button>`;
      document.querySelector('#marketLoadMore').onclick=()=>{visibleLimit+=PAGE_SIZE;renderMarket();};
    }else pager.innerHTML=rows.length?`<span>已显示全部 <strong>${rows.length.toLocaleString()}</strong> 条匹配结果</span>`:'';
  };

  ensurePerfStyles();
})();
