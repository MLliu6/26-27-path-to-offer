"""Draft-only assembly of fixes demonstrated by the browser regression."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'workspace-v15.js';s=p.read_text()
s=s.replace("visibleMarketJobs=function(){return baseVisible().filter(j=>{", """function leadRows(){
    // A verification queue is not a recommendation. Do not hide uncertain leads
    // behind the resume-fit threshold, but preserve explicit metadata/search filters.
    const q=$('#jobSearch')?.value||'',loc=$('#jobLocationFilter')?.value||'all',typ=$('#jobTypeFilter')?.value||'all',batch=$('#jobBatchFilter')?.value||'all';
    return marketJobs.filter(j=>C.isLead(j)&&state.decisions[j.id]!=='hidden'&&(loc==='all'||j.location.includes(loc))&&(typ==='all'||j.companyType===typ)&&(batch==='all'||j.batch===batch)&&window.PTO_MATCHING.searchMatch(j,q).matched).map(j=>({...j,match:{score:null,reasons:[],hits:[],components:{}}}));
  }
  visibleMarketJobs=function(){return (prefs.evidence==='leads'?leadRows():baseVisible()).filter(j=>{""")
a=s.index('  renderMarketFilters=function(){');b=s.index('\n',a)
s=s[:a]+'''  renderMarketFilters=function(){
    const selected=$('#jobLocationFilter')?.value||'all';baseFilters();const sel=$('#jobLocationFilter');if(!sel)return;
    const cities=['北京','上海','深圳','广州','杭州','南京','成都','武汉','西安','苏州','天津','合肥','长沙','重庆'];
    const observed=[...new Set(marketJobs.flatMap(j=>String(j.location||'').split(/[ ,，、/]+/).filter(x=>x.length>=2&&x.length<=24)))].sort((a,b)=>a.localeCompare(b,'zh-CN'));
    const popular=cities.filter(c=>observed.some(x=>x.includes(c)));
    const rest=observed.filter(x=>!popular.includes(x));if(selected!=='all'&&!popular.includes(selected)&&!rest.includes(selected))rest.push(selected);
    const options=xs=>xs.map(c=>`<option value="${esc(c)}">${esc(c)}</option>`).join('');
    sel.innerHTML='<option value="all">全部地点</option><optgroup label="常用城市">'+options(popular)+'</optgroup><optgroup label="其他已观测地点">'+options(rest)+'</optgroup>';sel.value=selected;
  };''' +s[b:]
s=s.replace("degraded?'部分来源需要关注':'岗位目录已载入'", "degraded?'部分信源降级':'岗位目录已载入'")
s=s.replace("} · ${bad}/${s.length} 个采集组异常<br>", "} · ${marketJobs.length.toLocaleString()} 岗位 · ${bad}/${s.length} 个采集组异常<br>")
s=s.replace("r.usedPrevious?' · 保留上次数据'", "r.usedPrevious?' · 已保留上一版数据'")
s=s.replace("    const leads=marketJobs.filter(C.isLead).length;", "    const leads=marketJobs.filter(C.isLead).length;\n    if(!currentProfile()&&Number(($('#marketCount')?.textContent||'0').replace(/,/g,''))>0)$('#jobMarketEmpty')?.classList.add('hidden');")
s=s.replace("if(live&&JSON.stringify(live)===JSON.stringify(next))Object.assign(live,before);", "if(live&&JSON.stringify(live)===JSON.stringify(next)){for(const key of Object.keys(live))delete live[key];Object.assign(live,before);}")
s=s.replace("$('#v15ResetFilters').onclick=()=>{prefs.kind=prefs.evidence='all';", "$('#v15ResetFilters').onclick=()=>{prefs.kind=prefs.evidence='all';$('#jobSearch').value='';")
p.write_text(s)
p=ROOT/'workspace-v15.css';s=p.read_text()+'''
/* Fix off-canvas overflow; retain a usable bottom navigation on small screens. */
html body .drawer:not(.open){visibility:hidden;pointer-events:none}
html body .drawer.open{visibility:visible;pointer-events:auto}
html body :is(.main-nav,.view-switch,.drawer-head,.timeline-box,.intel-card,.detail-facts div,.job-table th){background:var(--surface-2)!important;background-image:none!important;border-color:var(--line)!important;color:var(--text)}
html body :is(.jd-text,.intel-card p,.source-foot,.profile-summary){color:var(--muted)!important}
html body .main-nav{box-shadow:none}
html body select{border:1px solid var(--line);border-radius:8px;padding:7px 10px}
html body .market-head h2>span:not(#marketCount){display:none!important}
html body .v15-toolbar{align-items:center}
html body .v15-toolbar label{white-space:nowrap}
html body .v15-source-row{overflow-wrap:anywhere}
@media(max-width:760px){
  html body .topbar{display:flex;height:auto;min-height:62px;flex-wrap:nowrap}
  html body .main-nav{position:fixed;left:12px;right:12px;bottom:12px;top:auto;width:auto;box-sizing:border-box;background:var(--surface)!important;z-index:100;border:1px solid var(--line)!important}
  html body main{padding-bottom:94px}
  html body .v15-toolbar label{flex:1 1 42%;min-width:0;white-space:normal}
  html body .v15-toolbar label select{width:100%;min-width:0}
  html body .v15-summary{min-width:0}
  html body :is(.kanban,.view,.discovery-layout,.job-market,.app-shell){min-width:0;max-width:100%}
}
''';p.write_text(s)
p=ROOT/'tests/workspace_v15_smoke.py';s=p.read_text().replace("assert '部分来源' in page.locator('#feedHealth').inner_text()", "assert '部分信源降级' in page.locator('#feedHealth').inner_text()")
s=s.replace("assert page.locator('#jobMarketCards .market-card').count()==1", "assert page.locator('#jobMarketCards .market-card').count()==1, page.evaluate('({count:visibleMarketJobs().length,threshold:document.querySelector(\"#scoreThreshold\").value,body:document.body.innerText.slice(0,2500)})')")
p.write_text(s)
print('Polished verification queue semantics, responsive surfaces and safe undo.')
