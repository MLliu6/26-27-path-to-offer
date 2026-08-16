(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports) module.exports=api;
  root.PTO_PROFILE_V05=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(){
  'use strict';

  const SECTION_RULES=[
    ['skills',/^(专业技能|技能|技能栈|技术栈|skills?|technical skills?)\s*[:：]?$/i,1.45],
    ['experience',/^(实习经历|工作经历|项目实习|实践经历|experience|work experience|internship)\s*[:：]?$/i,1.35],
    ['projects',/^(项目经历|项目经验|projects?|project experience)\s*[:：]?$/i,1.25],
    ['research',/^(科研经历|研究经历|论文|论文发表|研究成果|科研项目|research|publications?)\s*[:：]?$/i,1.2],
    ['education',/^(教育经历|教育背景|学历|education)\s*[:：]?$/i,0.55],
    ['awards',/^(奖项|荣誉|获奖经历|竞赛经历|awards?|honors?)\s*[:：]?$/i,0.7],
    ['summary',/^(个人总结|个人简介|自我评价|求职意向|summary|profile|objective)\s*[:：]?$/i,1.0],
  ];
  const LABELS={skills:'专业技能',experience:'实习/工作',projects:'项目',research:'科研',education:'教育',awards:'奖项',summary:'个人总结',other:'其他'};

  function clean(v){return String(v||'').replace(/\u0000/g,' ').replace(/[\t\r]+/g,' ').replace(/[ ]{2,}/g,' ').trim();}
  function detectHeader(line){
    const value=clean(line).replace(/[【】\[\]#*]/g,'').trim();
    if(value.length>32)return null;
    for(const [name,re,weight] of SECTION_RULES){if(re.test(value))return {name,weight};}
    return null;
  }
  function splitSections(rawText){
    const lines=String(rawText||'').split(/\n/);
    const sections=[]; let current={name:'other',weight:0.8,lines:[]};
    const flush=()=>{const text=current.lines.join('\n').trim();if(text)sections.push({name:current.name,label:LABELS[current.name]||current.name,weight:current.weight,text});};
    for(const raw of lines){
      const h=detectHeader(raw);
      if(h){flush();current={name:h.name,weight:h.weight,lines:[]};continue;}
      current.lines.push(raw);
    }
    flush();
    if(!sections.length&&clean(rawText))sections.push({name:'other',label:'其他',weight:0.8,text:String(rawText)});
    return sections;
  }
  function uniq(xs){return [...new Set((xs||[]).filter(Boolean))];}
  function enrichProfile(baseProfile,rawText,fileName,core){
    if(!baseProfile||!core||typeof core.buildProfile!=='function')return baseProfile;
    const sections=splitSections(rawText);
    const aggregate=new Map();
    const roleVotes=new Map();
    const allSkills=[];
    const evidenceByDirection=new Map();

    const ingest=(signals,weight,label)=>{
      for(const d of signals?.directionScores||[]){
        const row=aggregate.get(d.name)||{name:d.name,score:0,evidence:[]};
        row.score+=(Number(d.rawScore)||0)*weight;
        for(const ev of d.evidence||[]){
          const tagged=label?`${label}:${ev}`:ev;
          if(!row.evidence.includes(tagged))row.evidence.push(tagged);
        }
        aggregate.set(d.name,row);
      }
      for(const role of signals?.recommendedRoles||[])roleVotes.set(role,(roleVotes.get(role)||0)+weight);
      allSkills.push(...(signals?.skills||[]));
    };

    // Preserve full-document context, but keep section evidence dominant.
    ingest(baseProfile.signals||{},0.72,'全文');
    for(const section of sections){
      if(clean(section.text).length<12)continue;
      const partial=core.buildProfile(section.text,`${fileName||'resume'}#${section.name}`);
      ingest(partial?.signals||{},section.weight,section.label);
    }

    const ranked=[...aggregate.values()].filter(x=>x.score>0).sort((a,b)=>b.score-a.score);
    const max=ranked[0]?.score||1;
    const directionScores=ranked.slice(0,6).map((x,i)=>({
      name:x.name,
      rawScore:Math.round(x.score*10)/10,
      confidence:Math.max(20,Math.min(97,Math.round(36+61*(x.score/max)*(i?0.94:1)))),
      evidence:x.evidence.slice(0,10),
    }));
    const recommendedRoles=[...roleVotes.entries()].sort((a,b)=>b[1]-a[1]).map(x=>x[0]).slice(0,14);
    const signals={...(baseProfile.signals||{})};
    if(directionScores.length){
      signals.directionScores=directionScores;
      signals.directions=directionScores.slice(0,4).map(x=>x.name);
      signals.primaryDirection=directionScores[0].name;
    }
    if(recommendedRoles.length)signals.recommendedRoles=recommendedRoles;
    signals.skills=uniq([...(signals.skills||[]),...allSkills]).slice(0,64);
    signals.sectionSummary=sections.map(s=>({name:s.name,label:s.label,chars:clean(s.text).length,weight:s.weight}));
    signals.profileQuality={
      rawChars:clean(rawText).length,
      sectionsDetected:sections.filter(s=>s.name!=='other').length,
      evidenceCount:directionScores.reduce((n,d)=>n+(d.evidence?.length||0),0),
      directionCount:directionScores.length,
    };
    for(const d of directionScores)evidenceByDirection.set(d.name,d.evidence);
    signals.sectionEvidence=Object.fromEntries(evidenceByDirection);
    return {...baseProfile,profileVersion:5,rawText:String(rawText||baseProfile.rawText||''),signals};
  }

  return {splitSections,enrichProfile,LABELS};
});
