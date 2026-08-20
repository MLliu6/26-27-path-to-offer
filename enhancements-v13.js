(function(){
  'use strict';
  if(!window.PTO_MATCHING||!window.PTO_CAREER_V13||typeof state==='undefined')return;
  const CORE=window.PTO_MATCHING;
  const TAX=window.PTO_CAREER_V13;
  const PROFILE=window.PTO_PROFILE_V05;
  const $=s=>document.querySelector(s);

  function finalizeSignals(signals={}){
    const dirs=(signals.directionScores||[]).map(row=>({...row}));
    if(dirs.length){
      signals.careerDomainScores=dirs;
      signals.careerDomains=dirs.map(x=>x.name).slice(0,5);
      signals.primaryCareerDomain=dirs[0]?.name||'';
      signals.careerDomainConfidence=Number(dirs[0]?.confidence||signals.careerDomainConfidence||0);
      signals.directions=signals.careerDomains.slice(0,4);
      signals.primaryDirection=signals.primaryCareerDomain;
    }
    return signals;
  }
  function rebuildProfile(profile){
    if(!profile?.rawText)return profile;
    const fileName=profile.fileName||`${profile.name||'resume'}.txt`;
    const base=CORE.buildProfile(profile.rawText,fileName);
    const next=PROFILE?.enrichProfile?PROFILE.enrichProfile(base,profile.rawText,fileName,CORE):base;
    profile.signals=finalizeSignals(next.signals||base.signals||{});
    profile.profileVersion=13;
    profile.displayName=profile.displayName||next.displayName||base.displayName;
    return profile;
  }

  // Future file uploads and pasted resumes both call buildResumeProfile. Force a
  // v13 career-domain stamp after all previous section-aware wrappers run.
  if(typeof buildResumeProfile==='function'){
    const previousBuild=buildResumeProfile;
    buildResumeProfile=function(rawText,fileName){
      const profile=previousBuild(rawText,fileName);
      profile.signals=finalizeSignals(profile.signals||{});
      profile.profileVersion=13;
      return profile;
    };
  }

  function resetResumeDerivedPrefs(beforeLocations=[]){
    // Target directions must never leak from a previously uploaded candidate.
    // Users can still set a manual direction afterwards in the profile inspector.
    state.preferences.targetDirections=[];
    // v0.7 silently injected Beijing after any resume. Undo that only when the
    // user had no explicit location preference before this upload.
    if(!beforeLocations.length)state.preferences.targetLocations=[];
    const threshold=$('#scoreThreshold');if(threshold)threshold.value='25';
    const label=$('#scoreThresholdLabel');if(label)label.textContent=threshold?.value||'25';
    const search=$('#jobSearch');if(search)search.value='';
  }

  if(typeof handleResumeFile==='function'){
    const previousHandle=handleResumeFile;
    handleResumeFile=async function(file){
      const beforeId=typeof currentProfile==='function'?currentProfile()?.id||'':'';
      const beforeLocations=[...(state.preferences?.targetLocations||[])];
      await previousHandle(file);
      const current=typeof currentProfile==='function'?currentProfile():null;
      if(current&&current.id!==beforeId){
        rebuildProfile(current);
        resetResumeDerivedPrefs(beforeLocations);
        saveState(false);renderAll();switchView('discover');
        const primary=current.signals?.primaryCareerDomain||current.signals?.primaryDirection||'方向待确认';
        toast(`简历已按“${primary}”画像生成通用岗位推荐`);
      }
    };
  }

  // Pasted-resume path does not go through handleResumeFile. Observe the actual
  // active-resume change and apply exactly the same preference reset.
  document.addEventListener('click',event=>{
    const button=event.target.closest?.('#parsePastedResume');if(!button)return;
    const beforeId=typeof currentProfile==='function'?currentProfile()?.id||'':'';
    const beforeLocations=[...(state.preferences?.targetLocations||[])];
    setTimeout(()=>{
      const current=typeof currentProfile==='function'?currentProfile():null;
      if(!current||current.id===beforeId)return;
      rebuildProfile(current);resetResumeDerivedPrefs(beforeLocations);saveState(false);renderAll();
    },220);
  },true);

  // Existing local profiles are upgraded from the old tech-only ontology when
  // plaintext is still available. Profiles whose raw text was deliberately
  // deleted are left untouched rather than guessed from old derived signals.
  function migrateProfiles(){
    let changed=false;
    for(const profile of state.resumes||[]){
      if(profile.rawText&&profile.profileVersion!==13){rebuildProfile(profile);changed=true;}
    }
    if(changed)saveState(false);
  }

  if(typeof renderProfile==='function'){
    const previousRender=renderProfile;
    renderProfile=function(){
      const out=previousRender.apply(this,arguments);
      const profile=typeof currentProfile==='function'?currentProfile():null;
      const intel=$('#profileIntelligence');
      if(profile&&intel){
        const first=intel.querySelector('.intel-card');
        const eyebrow=first?.querySelector('.eyebrow');if(eyebrow)eyebrow.textContent='CAREER DOMAIN PROFILE';
        const h3=first?.querySelector('h3');if(h3)h3.textContent=profile.signals?.primaryCareerDomain||profile.signals?.primaryDirection||'职业方向证据不足';
        first?.querySelectorAll('.direction-row').forEach(row=>row.setAttribute('title','由专业、实习、项目、科研与技能共同推断的职业领域'));
      }
      return out;
    };
  }

  function neutralizeCopy(){
    const search=$('#jobSearch');if(search)search.placeholder='搜公司 / 岗位 / 专业方向 / 城市…';
    const policy=$('#searchPolicy');if(policy)policy.innerHTML='<b>搜索优先：</b>明确搜索不受 Match 阈值限制；空搜索才依据当前简历的职业领域、JD 证据、届别与用户自选城市排序。';
    const first=$('#ptoFlow .pto-flow-step:nth-child(2) small');
    const profile=typeof currentProfile==='function'?currentProfile():null;
    if(first&&profile)first.textContent=profile.signals?.primaryCareerDomain||`${profile.signals?.skills?.length||0} 个简历信号`;
  }

  const oldRenderAll=typeof renderAll==='function'?renderAll:null;
  if(oldRenderAll){
    renderAll=function(){const out=oldRenderAll.apply(this,arguments);neutralizeCopy();return out;};
  }

  migrateProfiles();
  neutralizeCopy();
  try{renderAll();}catch(_){/* base app will render on load */}
  window.PTO_GENERAL_MATCHING_READY=true;
})();
