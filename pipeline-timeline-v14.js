(function(){
  'use strict';
  if(typeof state==='undefined'||typeof pipelineCard!=='function'||typeof stageName!=='function')return;

  const MAX_VISIBLE=4;

  function ensureStyles(){
    if(document.querySelector('#ptoPipelineTimelineV14Style'))return;
    const style=document.createElement('style');
    style.id='ptoPipelineTimelineV14Style';
    style.textContent=`
      .pipeline-mini-timeline{margin-top:11px;padding:10px 10px 9px;border:1px solid var(--line);border-radius:12px;background:color-mix(in srgb,var(--surface-2) 78%,var(--accent-soft) 22%)}
      .pipeline-mini-timeline-head{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:8px}.pipeline-mini-timeline-head span:first-child{font-size:9px;font-weight:700;letter-spacing:.06em;color:var(--muted);text-transform:uppercase}.pipeline-mini-timeline-head small{font-size:9px;color:var(--muted)}
      .pipeline-mini-timeline-track{display:flex;align-items:stretch;gap:0;min-width:0;overflow:hidden}.pipeline-timeline-node{position:relative;display:grid;grid-template-columns:10px minmax(0,1fr);gap:5px;align-items:start;min-width:0;flex:1;padding-right:9px}.pipeline-timeline-node:last-child{padding-right:0}.pipeline-timeline-node:not(:last-child):after{content:'';position:absolute;left:7px;right:-3px;top:5px;height:1px;background:var(--line);z-index:0}.pipeline-timeline-dot{position:relative;z-index:1;width:8px;height:8px;margin-top:1px;border-radius:50%;background:var(--surface);border:2px solid var(--muted)}.pipeline-timeline-node.done .pipeline-timeline-dot{border-color:var(--accent-strong);background:var(--accent-soft)}.pipeline-timeline-node.current .pipeline-timeline-dot{border-color:var(--accent-strong);background:var(--accent-strong);box-shadow:0 0 0 3px var(--accent-soft)}
      .pipeline-timeline-copy{position:relative;z-index:1;min-width:0}.pipeline-timeline-copy strong{display:block;font-size:10px;line-height:1.2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.pipeline-timeline-copy small{display:block;margin-top:3px;color:var(--muted);font-size:9px;white-space:nowrap}.pipeline-timeline-node.current .pipeline-timeline-copy strong{color:var(--accent-strong)}.pipeline-timeline-ellipsis{flex:0 0 auto;align-self:flex-start;margin:0 5px 0 0;color:var(--muted);font-size:11px;line-height:10px}
      .job-card:hover .pipeline-mini-timeline{border-color:color-mix(in srgb,var(--accent) 45%,var(--line))}
      @media(max-width:760px){.pipeline-mini-timeline{padding:9px 8px}.pipeline-mini-timeline-track{overflow-x:auto;scrollbar-width:none}.pipeline-mini-timeline-track::-webkit-scrollbar{display:none}.pipeline-timeline-node{flex:0 0 92px}.pipeline-mini-timeline-head small{display:none}}
    `;
    document.head.appendChild(style);
  }

  function timelineEvents(job){
    const raw=Array.isArray(job?.timeline)?job.timeline.filter(x=>x&&x.status):[];
    const rows=raw.map(x=>({status:String(x.status),date:x.date||''}));
    const currentStatus=String(job?.status||'');
    const currentDate=job?.statusDate||'';
    if(currentStatus&&(!rows.length||rows[rows.length-1].status!==currentStatus||String(rows[rows.length-1].date||'')!==String(currentDate||''))){
      rows.push({status:currentStatus,date:currentDate});
    }
    if(!rows.length&&currentStatus)rows.push({status:currentStatus,date:currentDate});
    return rows;
  }

  function miniTimeline(job){
    const events=timelineEvents(job);
    if(!events.length)return '';
    const clipped=events.slice(-MAX_VISIBLE);
    const hidden=Math.max(0,events.length-clipped.length);
    const currentIndex=events.length-1;
    const visibleStart=events.length-clipped.length;
    const nodes=clipped.map((event,index)=>{
      const absoluteIndex=visibleStart+index;
      const isCurrent=absoluteIndex===currentIndex;
      return `<div class="pipeline-timeline-node ${isCurrent?'current':'done'}" data-timeline-status="${esc(event.status)}"><span class="pipeline-timeline-dot" aria-hidden="true"></span><div class="pipeline-timeline-copy"><strong>${esc(stageName(event.status))}</strong><small>${esc(fmt(event.date))}</small></div></div>`;
    }).join('');
    const current=clipped[clipped.length-1];
    return `<div class="pipeline-mini-timeline" data-pipeline-timeline="${esc(job.id)}" aria-label="状态时间线，当前 ${esc(stageName(current.status))}"><div class="pipeline-mini-timeline-head"><span>状态轨迹</span><small>${events.length} 个节点 · 当前 ${esc(stageName(current.status))}</small></div><div class="pipeline-mini-timeline-track">${hidden?`<span class="pipeline-timeline-ellipsis" title="更早还有 ${hidden} 个节点">…</span>`:''}${nodes}</div></div>`;
  }

  function companyInitial(company){
    const value=String(company||'').replace(/^示例\s*[·•-]?\s*/,'').trim();
    const chinese=value.match(/[\u3400-\u9fff]/);
    if(chinese)return chinese[0];
    const latin=value.match(/[A-Za-z0-9]/);
    return latin?latin[0].toUpperCase():'企';
  }

  pipelineCard=function(j){
    return `<article class="job-card" draggable="true" data-job-id="${esc(j.id)}"><div class="job-meta"><span class="job-priority-badge">优先 ${esc(j.priority||'B')}</span><span class="date">${fmt(j.statusDate)}</span></div><div class="pipeline-card-title"><span class="company-avatar" aria-hidden="true">${esc(companyInitial(j.company))}</span><div><h3>${esc(j.company)}</h3><p>${esc(j.role)}</p></div></div><div class="job-meta"><span class="date">${esc(j.location||'地点待定')}</span>${j.matchAtSave!=null?`<span class="date">match ${j.matchAtSave}</span>`:''}</div>${miniTimeline(j)}</article>`;
  };

  ensureStyles();
  window.PTO_PIPELINE_TIMELINE_V14={timelineEvents,miniTimeline,maxVisible:MAX_VISIBLE};
})();