(function(){
  'use strict';
  if(!window.PTO_MATCHING||!window.PTO_PROFILE_V05||typeof state==='undefined')return;
  const CORE=window.PTO_MATCHING;
  const PROFILE=window.PTO_PROFILE_V05;

  const oldBuild=buildResumeProfile;
  const oldRenderProfile=renderProfile;
  const oldInspectProfile=inspectProfile;

  buildResumeProfile=function(rawText,fileName){
    const base=oldBuild(rawText,fileName);
    const enriched=PROFILE.enrichProfile(base,rawText,fileName,CORE);
    enriched.id=base.id||uid('resume');
    enriched.uploadedAt=base.uploadedAt||new Date().toISOString();
    return enriched;
  };

  function qualityLabel(q){
    if(!q)return '待分析';
    if((q.sectionsDetected||0)>=4&&(q.evidenceCount||0)>=8)return '结构清晰';
    if((q.sectionsDetected||0)>=2&&(q.evidenceCount||0)>=4)return '可用';
    return '建议检查解析文本';
  }
  function ensureV5Style(){
    if(document.querySelector('#ptoV05Style'))return;
    const style=document.createElement('style');style.id='ptoV05Style';style.textContent=`
      .section-cloud{display:flex;flex-wrap:wrap;gap:5px}.section-chip{font-size:10px;padding:4px 7px;border-radius:999px;border:1px solid var(--line);background:#fafbf8;color:var(--muted)}
      .section-chip strong{color:var(--text);font-weight:600}.quality-line{display:flex;align-items:center;justify-content:space-between;gap:8px;margin:8px 0;font-size:11px;color:var(--muted)}
      .quality-badge{padding:3px 7px;border-radius:999px;background:var(--accent-soft);color:var(--accent-strong);font-size:10px}
      .role-cloud span[data-role-search]{cursor:pointer;transition:.18s ease}.role-cloud span[data-role-search]:hover{transform:translateY(-1px);border-color:var(--accent)}
      .profile-inspector .section-audit{border:1px solid var(--line);border-radius:12px;padding:11px;margin-top:10px;background:var(--surface-2)}
    `;document.head.appendChild(style);
  }

  renderProfile=function(){
    oldRenderProfile();
    const p=currentProfile();if(!p)return;
    const s=p.signals||{};const q=s.profileQuality||{};const sections=(s.sectionSummary||[]).filter(x=>x.chars>0);
    const intel=document.querySelector('#profileIntelligence');
    if(intel&&!document.querySelector('#resumeStructureCard')){
      const card=document.createElement('article');card.id='resumeStructureCard';card.className='intel-card';
      intel.appendChild(card);
    }
    const card=document.querySelector('#resumeStructureCard');
    if(card){
      card.innerHTML=`<p class="eyebrow">RESUME STRUCTURE</p><h3>解析质量 · ${esc(qualityLabel(q))}</h3><div class="quality-line"><span>${q.rawChars||0} 字符</span><span>${q.sectionsDetected||0} 个结构段</span><span>${q.evidenceCount||0} 条方向证据</span></div><div class="section-cloud">${sections.length?sections.map(x=>`<span class="section-chip"><strong>${esc(x.label)}</strong> · ${x.chars}</span>`).join(''):'<span class="section-chip">未识别明确章节标题</span>'}</div><p style="margin-top:9px">技能、实习和项目证据会比教育背景获得更高权重，降低“学校/课程词”误导岗位方向的概率。</p>`;
    }
    document.querySelectorAll('.role-cloud span').forEach(el=>{
      el.dataset.roleSearch='1';el.title='点击搜索这个岗位方向';
      el.onclick=()=>{const search=document.querySelector('#jobSearch');if(!search)return;search.value=el.textContent.trim();switchView('discover');renderMarket();search.focus();};
    });
  };

  inspectProfile=function(){
    oldInspectProfile();
    const p=currentProfile();if(!p)return;const s=p.signals||{};const q=s.profileQuality||{};const sections=(s.sectionSummary||[]).filter(x=>x.chars>0);
    const inspector=document.querySelector('.profile-inspector');const actions=inspector?.querySelector('.modal-actions');
    if(inspector&&actions&&!inspector.querySelector('.section-audit')){
      const block=document.createElement('div');block.className='section-audit';
      block.innerHTML=`<p class="eyebrow">SECTION-AWARE PARSING · V5</p><strong>方向推断不再把整份简历当成一袋关键词</strong><p class="muted">已识别 ${q.sectionsDetected||0} 个明确章节；技能 / 实习 / 项目 / 科研分别加权，教育和奖项只提供弱证据。</p><div class="section-cloud" style="margin-top:8px">${sections.map(x=>`<span class="section-chip">${esc(x.label)} · ${x.chars}</span>`).join('')||'<span class="section-chip">未识别章节</span>'}</div>`;
      actions.insertAdjacentElement('beforebegin',block);
    }
    const reparse=document.querySelector('#reparseResume');
    if(reparse)reparse.onclick=()=>{
      if(!p.rawText){toast('原始解析文本已删除，无法重算');return;}
      const base=CORE.buildProfile(p.rawText,p.fileName||`${p.name}.txt`);
      const next=PROFILE.enrichProfile(base,p.rawText,p.fileName||`${p.name}.txt`,CORE);
      p.signals=next.signals;p.profileVersion=5;p.displayName=next.displayName||p.displayName;
      saveState();closeModal();toast('画像已按 v5 分章节规则重新生成');
    };
  };

  function migrate(){
    let changed=false;
    for(const p of state.resumes||[]){
      if(p.rawText&&p.profileVersion!==5){
        const base=CORE.buildProfile(p.rawText,p.fileName||`${p.name}.txt`);
        const next=PROFILE.enrichProfile(base,p.rawText,p.fileName||`${p.name}.txt`,CORE);
        p.signals=next.signals;p.profileVersion=5;p.displayName=p.displayName||next.displayName;changed=true;
      }
    }
    if(changed)saveState(false);
  }

  // enhancements-v04 bound the visible button before this wrapper existed.
  // Rebind it here so “查看解析结果” actually opens the section-aware v5
  // inspector instead of a stale v4 function object captured by the old handler.
  function bindV5Inspector(){
    const button=document.querySelector('#inspectProfileBtn');
    if(button)button.onclick=inspectProfile;
  }

  ensureV5Style();migrate();renderAll();bindV5Inspector();
})();
