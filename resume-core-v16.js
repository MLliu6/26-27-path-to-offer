(function(root,factory){
  const api=factory();root.PTO_RESUME_V16=api;
  if(typeof module==='object'&&module.exports)module.exports=api;
  if(typeof document!=='undefined'&&typeof state!=='undefined')api.install();
})(typeof globalThis!=='undefined'?globalThis:this,function(){
  'use strict';
  function cleanText(value){return String(value||'').replace(/[\u0000\u200b\ufeff]/g,'').replace(/\r\n?/g,'\n').replace(/[ \t]+/g,' ').replace(/\n{3,}/g,'\n\n').trim();}
  function decodeText(buffer){
    const bytes=new Uint8Array(buffer);
    if(bytes[0]===255&&bytes[1]===254)return cleanText(new TextDecoder('utf-16le').decode(bytes));
    if(bytes[0]===254&&bytes[1]===255)return cleanText(new TextDecoder('utf-16be').decode(bytes));
    try{return cleanText(new TextDecoder('utf-8',{fatal:true}).decode(bytes));}
    catch(_){return cleanText(new TextDecoder('gb18030').decode(bytes));}
  }
  function pdfText(items){
    const lines=[];let line='',last=null;
    for(const item of items||[]){
      if(typeof item.str!=='string')continue;
      const y=Number(item.transform?.[5]),oldY=Number(last?.transform?.[5]);
      if(line&&last&&(last.hasEOL||Number.isFinite(y)&&Number.isFinite(oldY)&&Math.abs(y-oldY)>Math.max(2,Number(item.height||10)*.4))){lines.push(line);line='';}
      const gap=Number(item.transform?.[4])-Number(last?.transform?.[4])-Number(last?.width||0);
      const joinChinese=/[\u3400-\u9fff]$/.test(line)&&/^[\u3400-\u9fff]/.test(item.str)&&gap<Math.max(3,Number(item.height||10)*.6);
      line+=(line&&!joinChinese?' ':'')+item.str;last=item;
    }
    if(line)lines.push(line);return cleanText(lines.join('\n'));
  }
  function quality(text){
    const value=cleanText(text),chars=value.replace(/\s/g,'').length;
    const readable=(value.match(/[\p{L}\p{N}]/gu)||[]).length;
    const replacement=(value.match(/\ufffd/g)||[]).length;
    const sections=(value.match(/教育背景|教育经历|专业技能|项目经历|实习经历|工作经历|科研经历|education|experience|skills|projects/gi)||[]).length;
    const needsReview=chars<80||replacement>chars*.02||readable<chars*.55;
    return {chars,sections,needsReview,label:chars<30?'文本待补充':needsReview?'请核对文本':sections>=2?'结构清晰':'文本已提取'};
  }
  async function extract(file,onProgress=()=>{}){
    const ext=String(file.name||'').split('.').pop().toLowerCase();
    if(!['pdf','docx','txt'].includes(ext))throw new Error('请选择 PDF、DOCX 或 TXT 文件');
    if(file.size>20*1024*1024)throw new Error('文件超过 20 MB，请压缩后重试');
    const buffer=await file.arrayBuffer();
    if(ext==='txt')return {text:decodeText(buffer),warnings:[]};
    if(ext==='docx'){
      if(!globalThis.mammoth)throw new Error('DOCX 解析组件加载失败，请刷新后重试或粘贴简历文字');
      const result=await mammoth.extractRawText({arrayBuffer:buffer});
      return {text:cleanText(result.value),warnings:result.messages?.length?['部分 Word 格式已转换为纯文本，请核对内容。']:[]};
    }
    if(!globalThis.pdfjsLib)throw new Error('PDF 解析组件加载失败，请刷新后重试或粘贴简历文字');
    pdfjsLib.GlobalWorkerOptions.workerSrc=new URL('vendor/pdf.worker.min.js',document.baseURI).href;
    let pdf;
    try{
      pdf=await pdfjsLib.getDocument({data:new Uint8Array(buffer),isEvalSupported:false}).promise;
      if(pdf.numPages>30)throw new Error('简历超过 30 页，请选择简历正文后重新导入');
      const pages=[];let blank=0;
      for(let i=1;i<=pdf.numPages;i++){
        onProgress(`正在读取第 ${i} / ${pdf.numPages} 页…`);
        const page=await pdf.getPage(i),content=await page.getTextContent(),text=pdfText(content.items);
        if(text.replace(/\s/g,'').length<15)blank++;pages.push(text);page.cleanup();
      }
      return {text:cleanText(pages.join('\n\n')),warnings:blank?[`${blank} 页未提取到足够文字。图片或扫描页请先进行 OCR，再粘贴文字。`]:[]};
    }catch(error){
      if(error.name==='PasswordException')throw new Error('PDF 有密码保护，请导入解锁后的副本');
      if(error.name==='InvalidPDFException')throw new Error('PDF 文件无法读取，请重新导出或粘贴简历文字');
      throw error;
    }finally{if(pdf)await pdf.destroy();}
  }
  function install(){
    const $=s=>document.querySelector(s);
    let importSequence=0;
    function preview(text,fileName,warnings=[],existing=null){
      const owner=state,ownerId=window.PTO_ACCOUNT_SESSION?.id||'guest';
      openModal(existing?'编辑简历画像':'确认简历解析',`<div class="stack-form pto-resume-preview"><p class="muted">核对文字、学历与毕业届别，确认后用于岗位匹配。</p><label>简历版本名称<input id="resumePreviewName" value="${esc(existing?.name||fileName.replace(/\.(pdf|docx|txt)$/i,''))}" maxlength="100"></label><div class="form-grid"><label>最高学历<select id="resumePreviewDegree"><option value="">待确认</option>${['大专','本科','硕士','博士'].map(d=>`<option>${d}</option>`).join('')}</select></label><label>毕业届别<input id="resumePreviewYear" type="number" min="2020" max="2040" placeholder="例如 2027"></label></div><div role="status" id="resumePreviewQuality"></div>${warnings.map(w=>`<p class="muted">${esc(w)}</p>`).join('')}<label>解析文本<textarea id="resumePreviewText" rows="12" spellcheck="false">${esc(text)}</textarea></label><div class="modal-actions"><button type="button" class="btn ghost" id="resumePreviewCancel">取消</button><button type="button" class="btn primary" id="resumePreviewSave">${existing?'保存画像':'确认并匹配'}</button></div></div>`);
      const inferred=window.PTO_MATCHING.buildProfile(text,fileName).signals||{};
      $('#resumePreviewDegree').value=existing?.signals?.degree||inferred.degree||'';
      $('#resumePreviewYear').value=existing?.signals?.graduationYear||inferred.graduationYear||'';
      const summary=document.createElement('div');summary.id='resumeParsedSummary';summary.className='resume-parse-summary';$('#resumePreviewQuality').after(summary);
      const sections=document.createElement('div');sections.id='resumeParsedSections';summary.after(sections);
      function update(){
        const raw=$('#resumePreviewText').value,q=quality(raw),parts=window.PTO_PROFILE_V05.splitSections(raw),profile=window.PTO_MATCHING.buildProfile(raw,fileName).signals||{};
        const recognized=parts.filter(p=>p.name!=='other');
        $('#resumePreviewQuality').textContent=`${q.label} · ${q.chars} 字 · ${recognized.length} 个已识别章节`;$('#resumePreviewSave').disabled=q.chars<30;
        const skills=[...new Set([...(profile.skills||[]),...(window.PTO_MATCHING.skillEvidence?.(raw)||[])])];
        summary.innerHTML=`<h3>解析概览</h3><p>${esc(profile.primaryCareerDomain||profile.primaryDirection||'补充经历后识别求职方向')}</p><div class="resume-preview-skills">${skills.map(s=>`<span>${esc(s)}</span>`).join('')}</div><p>${skills.length?'识别到 '+skills.length+' 项技能，可在下方原文中核对。':'暂未识别到明确技能，请核对技能章节。'}</p>${!profile.graduationYear?'<p>毕业年份待确认，请填写上方毕业届别。</p>':''}${!recognized.length?'<p>尚未识别章节标题，已保留全部文字。可补充“教育背景”“项目经历”等标题。</p>':''}`;
        sections.innerHTML=parts.map((p,i)=>`<details class="resume-section" ${i===0?'open':''}><summary><span>${esc(p.name==='other'?'基本信息 / 未分组内容':p.label)}</span><small>${p.text.length} 字</small></summary><pre>${esc(p.text)}</pre></details>`).join('');
      }
      let previewTimer;$('#resumePreviewText').addEventListener('input',()=>{const q=quality($('#resumePreviewText').value);$('#resumePreviewSave').disabled=q.chars<30;clearTimeout(previewTimer);previewTimer=setTimeout(()=>{if($('#resumeParsedSummary')===summary)update();},200);});update();
      $('#resumePreviewCancel').onclick=closeModal;
      $('#resumePreviewSave').onclick=async()=>{
        if(state!==owner||(window.PTO_ACCOUNT_SESSION?.id||'guest')!==ownerId){toast('账户已切换，请重新导入简历');closeModal();return;}
        const input=$('#resumePreviewText').value,year=$('#resumePreviewYear').value,degree=$('#resumePreviewDegree').value;
        if(year&&(!/^20\d{2}$/.test(year)||Number(year)<2020||Number(year)>2040)){toast('请填写 2020–2040 之间的毕业年份');return;}
        const next=buildResumeProfile(input,fileName);next.name=$('#resumePreviewName').value.trim()||'我的简历';
        const saveButton=$('#resumePreviewSave');saveButton.disabled=true;
        next.signals.degree=degree;next.signals.graduationYear=year;next.signals.profileQuality={...(next.signals.profileQuality||{}),...quality(input),confirmed:true};
        next.profileOverrides={degree,graduationYear:year};
        const previous=[...state.resumes],active=state.activeResumeId;
        if(existing){Object.assign(next,{id:existing.id,uploadedAt:existing.uploadedAt});state.resumes=state.resumes.map(r=>r.id===existing.id?next:r);}
        else state.resumes.unshift(next);
        state.activeResumeId=next.id;
        try{saveState(false);if(window.PTO_SECURE_ACCOUNT_V2)await window.PTO_SECURE_ACCOUNT_V2.flushLocal();}
        catch(_){state.resumes=previous;state.activeResumeId=active;saveButton.disabled=false;toast('保存失败，请保留当前文本并重试');return;}
        window.PTO_RANKING_V14?.clearCache();closeModal();renderAll();switchView('discover');toast(existing?'画像已更新':'简历已确认，匹配已更新');
      };
    }
    handleResumeFile=async function(file){
      if(!file)return;const sequence=++importSequence,owner=state;
      toast('正在解析简历…');
      try{const result=await extract(file,message=>{if(sequence===importSequence&&state===owner)toast(message);});if(sequence!==importSequence||state!==owner)return;preview(result.text,file.name,result.warnings);}
      catch(error){toast(error.message||'文件解析失败，请尝试粘贴文字');}
      finally{for(const selector of ['#resumeImport','#libraryResumeImport','#replaceResumeInput']){const input=$(selector);if(input)input.value='';}}
    };
    extractResumeText=async function(file){return (await extract(file)).text;};
    pasteResume=function(){preview('','我的简历.txt');};
    const paste=$('#pasteResumeBtn');if(paste)paste.onclick=pasteResume;
    const baseBuild=buildResumeProfile;
    buildResumeProfile=function(text,name){
      const p=baseBuild(text,name);
      p.signals.skills=[...new Set([...(p.signals.skills||[]),...(window.PTO_MATCHING.skillEvidence?.(text)||[])])];
      p.signals.profileQuality={...(p.signals.profileQuality||{}),...quality(text)};return p;
    };
    const baseInspect=inspectProfile;
    inspectProfile=function(){
      baseInspect();const current=currentProfile();if(!current)return;
      const parsed=document.createElement('details');parsed.className='resume-section';
      parsed.innerHTML='<summary>按章节查看完整解析</summary>'+window.PTO_PROFILE_V05.splitSections(current.rawText||'').map(p=>`<section class="resume-section"><h3>${esc(p.name==='other'?'基本信息 / 未分组内容':p.label)}</h3><pre>${esc(p.text)}</pre></section>`).join('');
      $('#modalBody').prepend(parsed);
      const actions=$('#modalBody .modal-actions');if(!actions)return;
      const button=document.createElement('button');button.type='button';button.className='btn primary';button.id='editResumeProfile';button.textContent='编辑解析结果';button.onclick=()=>preview(current.rawText||'',current.fileName||current.name+'.txt',[],current);actions.prepend(button);
    };
    const inspect=$('#inspectProfileBtn');if(inspect)inspect.onclick=inspectProfile;
    // Older version enrichers run at startup. Reapply explicit user choices
    // whenever a profile is read, including after unlocking another account.
    const baseCurrent=currentProfile;
    currentProfile=function(){const p=baseCurrent();if(p?.profileOverrides&&p.signals)Object.assign(p.signals,p.profileOverrides);return p;};
    window.PTO_RESUME_V16.preview=preview;
  }
  return {cleanText,decodeText,pdfText,quality,extract,install};
});
