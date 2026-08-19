(function(){
  'use strict';
  if(!window.PTO_ACCOUNT_VAULT||typeof state==='undefined')return;

  const VAULT=window.PTO_ACCOUNT_VAULT;
  const ACCOUNT_PREFIX='pto.secure.local.v1.';
  const ADMIN_ACCOUNT='mlliu6';
  const DEFAULT_OWNER='MLliu6';
  const DEFAULT_REPO='26-27-path-to-offer';
  const guestSnapshot=JSON.parse(JSON.stringify(state));
  const originalSaveState=saveState;
  const originalInspectProfile=inspectProfile;
  let accountSession=null;
  let adminUnlocked=false;
  let persistTimer=null;

  const $=selector=>document.querySelector(selector);
  const clone=value=>JSON.parse(JSON.stringify(value));
  const localKey=id=>`${ACCOUNT_PREFIX}${id}`;
  const normalizeLoadedState=value=>typeof normalizeState==='function'?normalizeState(value||{}):value||{};
  const accountButton=()=>$('#githubLoginBtn');

  function injectStyles(){
    if($('#ptoV12Style'))return;
    const style=document.createElement('style');
    style.id='ptoV12Style';
    style.textContent=`
      .company-avatar{width:32px;height:32px;border-radius:11px;display:grid;place-items:center;flex:0 0 auto;background:var(--accent-soft);color:var(--accent-strong);font-family:var(--serif);font-weight:700;font-size:15px;border:1px solid color-mix(in srgb,var(--accent) 42%,var(--line))}
      .pipeline-card-title{display:flex;align-items:center;gap:10px;min-width:0}.pipeline-card-title>div{min-width:0}.pipeline-card-title h3{margin:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.pipeline-card-title p{margin:2px 0 0}
      .job-priority-badge{display:inline-flex;align-items:center;padding:3px 7px;border-radius:999px;background:var(--surface-2);border:1px solid var(--line);font-size:9px;color:var(--muted)}
      .account-modal{display:grid;gap:14px}.account-status{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;padding:13px 14px;border-radius:14px;background:var(--surface-2);border:1px solid var(--line)}.account-status strong{display:block}.account-status small{display:block;color:var(--muted);margin-top:3px}
      .account-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.account-panel{border:1px solid var(--line);border-radius:15px;padding:14px;background:var(--surface)}.account-panel h3{font-family:var(--serif);font-size:15px;margin:0 0 5px}.account-panel>p{font-size:10px;color:var(--muted);line-height:1.55;margin:0 0 11px}.account-panel label{display:grid;gap:5px;margin:8px 0}.account-panel label span{font-size:10px;color:var(--muted)}.account-panel input{width:100%}.account-actions{display:flex;gap:7px;flex-wrap:wrap;margin-top:10px}.account-note{font-size:10px;line-height:1.55;color:var(--muted);padding:10px 12px;border-left:3px solid var(--accent);background:var(--accent-soft);border-radius:8px}
      .sync-status-dot{width:8px;height:8px;border-radius:50%;background:#b1b7ad;display:inline-block;margin-right:5px}.sync-status-dot.active{background:var(--accent-strong)}
      .admin-source-wrap{position:relative;min-height:290px}.admin-source-blur{filter:blur(7px);opacity:.52;pointer-events:none;user-select:none}.admin-source-gate{position:absolute;inset:0;display:grid;place-items:center;padding:18px}.admin-source-card{width:min(430px,100%);background:color-mix(in srgb,var(--surface) 94%,transparent);backdrop-filter:blur(18px);border:1px solid var(--line);border-radius:17px;padding:18px;box-shadow:0 18px 50px rgba(0,0,0,.12);text-align:center}.admin-source-card h3{font-family:var(--serif);margin:0 0 6px}.admin-source-card p{font-size:11px;color:var(--muted);line-height:1.55}.admin-source-card input{width:100%;margin-top:8px}.admin-source-card .btn{margin-top:8px;width:100%}
      .privacy-audit-box{border:1px solid var(--line);border-radius:13px;padding:12px;margin-top:12px;background:var(--surface-2)}.privacy-audit-box h4{font-family:var(--serif);margin:0 0 4px}.privacy-audit-box p{font-size:10px;color:var(--muted);line-height:1.5;margin:0}.privacy-audit-actions{display:flex;gap:7px;flex-wrap:wrap;margin-top:9px}
      .parsed-text-view{white-space:pre-wrap;max-height:52vh;overflow:auto;background:var(--surface-2);border:1px solid var(--line);border-radius:12px;padding:12px;font:11px/1.65 ui-monospace,SFMono-Regular,Consolas,monospace}
      @media(max-width:840px){.account-grid{grid-template-columns:1fr}.pipeline-card-title{align-items:flex-start}.company-avatar{width:29px;height:29px}}
    `;
    document.head.appendChild(style);
  }

  function companyInitial(company){
    const value=String(company||'').replace(/^示例\s*[·•-]?\s*/,'').trim();
    const chinese=value.match(/[\u3400-\u9fff]/);
    if(chinese)return chinese[0];
    const latin=value.match(/[A-Za-z0-9]/);
    return latin?latin[0].toUpperCase():'企';
  }

  pipelineCard=function(j){
    return `<article class="job-card" draggable="true" data-job-id="${esc(j.id)}"><div class="job-meta"><span class="job-priority-badge">优先 ${esc(j.priority||'B')}</span><span class="date">${fmt(j.statusDate)}</span></div><div class="pipeline-card-title"><span class="company-avatar" aria-hidden="true">${esc(companyInitial(j.company))}</span><div><h3>${esc(j.company)}</h3><p>${esc(j.role)}</p></div></div><div class="job-meta"><span class="date">${esc(j.location||'地点待定')}</span>${j.matchAtSave!=null?`<span class="date">match ${j.matchAtSave}</span>`:''}</div></article>`;
  };

  function setButtonState(){
    const button=accountButton();if(!button)return;
    if(accountSession){
      button.innerHTML=`<span class="sync-status-dot active"></span><span>${esc(accountSession.username)}</span>`;
      button.title=`${accountSession.mode==='github'?'GitHub 加密同步':'本机加密账户'} · 点击管理`;
    }else{
      button.innerHTML='<span class="sync-status-dot"></span><span>账户 / 同步</span>';
      button.title='本地账户与跨设备加密同步';
    }
    button.onclick=openAccountModal;
  }

  async function saveLocalEncrypted(){
    if(!accountSession)return;
    const includeResumeText=!!accountSession.includeResumeText;
    const payload={
      username:accountSession.username,
      state:VAULT.sanitizeState(state,{includeResumeText}),
      includeResumeText,
      mode:accountSession.mode,
      revision:Number(accountSession.revision||0),
      updatedAt:new Date().toISOString()
    };
    const vault=await VAULT.encryptJson(payload,accountSession.password,`local:${accountSession.id}`);
    localStorage.setItem(localKey(accountSession.id),JSON.stringify(vault));
    accountSession.localUpdatedAt=payload.updatedAt;
  }
  function queueLocalPersist(){
    if(!accountSession)return;
    accountSession.dirty=true;
    clearTimeout(persistTimer);
    persistTimer=setTimeout(()=>saveLocalEncrypted().catch(err=>console.warn('Encrypted local save failed',err)),240);
  }

  saveState=function(render=true){
    if(!accountSession){originalSaveState(render);return;}
    if(render)renderAll();
    queueLocalPersist();
  };

  function activateAccount(payload,session){
    accountSession={...session,revision:Number(payload.revision||0),includeResumeText:!!payload.includeResumeText,dirty:false};
    window.PTO_ACCOUNT_SESSION=accountSession;
    state=normalizeLoadedState(clone(payload.state||{}));
    localStorage.removeItem(STORAGE_KEY);
    if(typeof LEGACY_KEY!=='undefined')localStorage.removeItem(LEGACY_KEY);
    saveLocalEncrypted().catch(err=>console.warn(err));
    setButtonState();
    renderAll();
  }

  async function createLocalAccount(username,password,includeResumeText){
    const normalized=VAULT.normalizeAccount(username),id=await VAULT.accountId(normalized);
    const existing=localStorage.getItem(localKey(id));
    if(existing&&!confirm('该本机账户已存在。用当前页面数据覆盖它？'))return;
    const payload={username:normalized,state:VAULT.sanitizeState(state,{includeResumeText}),includeResumeText,mode:'local',revision:1,updatedAt:new Date().toISOString()};
    activateAccount(payload,{mode:'local',username:normalized,id,password,includeResumeText});
    toast('本机加密账户已创建');closeModal();
  }
  async function loginLocalAccount(username,password){
    const normalized=VAULT.normalizeAccount(username),id=await VAULT.accountId(normalized);
    const raw=localStorage.getItem(localKey(id));if(!raw)throw new Error('此设备上没有该本机账户');
    const payload=await VAULT.decryptJson(JSON.parse(raw),password,`local:${id}`);
    if(VAULT.normalizeAccount(payload.username)!==normalized)throw new Error('账户校验失败');
    activateAccount(payload,{mode:'local',username:normalized,id,password,includeResumeText:!!payload.includeResumeText});
    toast('本机账户已解锁');closeModal();
  }
  async function enrollGithubAccount(username,password,token,includeResumeText){
    const normalized=VAULT.normalizeAccount(username),id=await VAULT.accountId(normalized);
    if(!token||token.length<20)throw new Error('首次绑定需要仅授权本仓库 Contents 读写的 Fine-grained Token');
    const remote=await VAULT.fetchGithubVault({owner:DEFAULT_OWNER,repo:DEFAULT_REPO,id});
    if(remote&&!confirm('远端已存在同名加密账户。确定覆盖？'))return;
    const payload={username:normalized,state:VAULT.sanitizeState(state,{includeResumeText}),includeResumeText,mode:'github',token,owner:DEFAULT_OWNER,repo:DEFAULT_REPO,revision:Number(remote?.vault?.revision||0)+1,updatedAt:new Date().toISOString()};
    const vault=await VAULT.encryptJson(payload,password,`github:${id}`);
    const saved=await VAULT.putGithubVault({owner:DEFAULT_OWNER,repo:DEFAULT_REPO,id,token,vault,sha:remote?.sha||''});
    activateAccount(payload,{mode:'github',username:normalized,id,password,token,owner:DEFAULT_OWNER,repo:DEFAULT_REPO,remoteSha:saved.sha,remoteUpdatedAt:payload.updatedAt,remoteVerified:true,includeResumeText});
    if(normalized===ADMIN_ACCOUNT)adminUnlocked=true;
    toast('跨设备加密账户已初始化');closeModal();
  }
  async function loginGithubAccount(username,password,{activate=true}={}){
    const normalized=VAULT.normalizeAccount(username),id=await VAULT.accountId(normalized);
    const remote=await VAULT.fetchGithubVault({owner:DEFAULT_OWNER,repo:DEFAULT_REPO,id});
    if(!remote)throw new Error('没有找到该跨设备账户；首次使用需在有写权限的设备初始化');
    const payload=await VAULT.decryptJson(remote.vault,password,`github:${id}`);
    if(VAULT.normalizeAccount(payload.username)!==normalized)throw new Error('账户校验失败');
    if(!payload.token)throw new Error('远端账户缺少同步凭据，请重新初始化');
    if(activate){
      activateAccount(payload,{mode:'github',username:normalized,id,password,token:payload.token,owner:payload.owner||DEFAULT_OWNER,repo:payload.repo||DEFAULT_REPO,remoteSha:remote.sha,remoteUpdatedAt:payload.updatedAt,remoteVerified:true,includeResumeText:!!payload.includeResumeText});
      if(normalized===ADMIN_ACCOUNT)adminUnlocked=true;
      toast('跨设备账户已解锁');closeModal();
    }
    return {payload,remote,id,normalized};
  }
  async function pushGithub(){
    if(accountSession?.mode!=='github')throw new Error('当前不是 GitHub 跨设备账户');
    const remote=await VAULT.fetchGithubVault({owner:accountSession.owner,repo:accountSession.repo,id:accountSession.id});
    let remotePayload=null;
    if(remote){
      remotePayload=await VAULT.decryptJson(remote.vault,accountSession.password,`github:${accountSession.id}`);
      if(accountSession.dirty&&remotePayload.updatedAt&&accountSession.remoteUpdatedAt&&remotePayload.updatedAt!==accountSession.remoteUpdatedAt){
        if(!confirm('远端数据在本次会话后发生过变化。仍用当前设备覆盖？'))return;
      }
    }
    const revision=Math.max(Number(accountSession.revision||0),Number(remotePayload?.revision||0))+1;
    const payload={username:accountSession.username,state:VAULT.sanitizeState(state,{includeResumeText:accountSession.includeResumeText}),includeResumeText:accountSession.includeResumeText,mode:'github',token:accountSession.token,owner:accountSession.owner,repo:accountSession.repo,revision,updatedAt:new Date().toISOString()};
    const vault=await VAULT.encryptJson(payload,accountSession.password,`github:${accountSession.id}`);
    const saved=await VAULT.putGithubVault({owner:accountSession.owner,repo:accountSession.repo,id:accountSession.id,token:accountSession.token,vault,sha:remote?.sha||accountSession.remoteSha||''});
    Object.assign(accountSession,{revision,remoteSha:saved.sha,remoteUpdatedAt:payload.updatedAt,dirty:false});
    await saveLocalEncrypted();toast('已加密同步到 GitHub');openAccountModal();
  }
  async function pullGithub(){
    if(accountSession?.mode!=='github')throw new Error('当前不是 GitHub 跨设备账户');
    const result=await loginGithubAccount(accountSession.username,accountSession.password,{activate:false});
    if(accountSession.dirty&&!confirm('当前设备有未推送改动。仍用远端数据覆盖？'))return;
    activateAccount(result.payload,{mode:'github',username:result.normalized,id:result.id,password:accountSession.password,token:result.payload.token,owner:result.payload.owner||DEFAULT_OWNER,repo:result.payload.repo||DEFAULT_REPO,remoteSha:result.remote.sha,remoteUpdatedAt:result.payload.updatedAt,remoteVerified:true,includeResumeText:!!result.payload.includeResumeText});
    toast('已读取远端加密数据');openAccountModal();
  }
  function logoutAccount(){
    accountSession=null;window.PTO_ACCOUNT_SESSION=null;adminUnlocked=false;
    state=normalizeLoadedState(clone(guestSnapshot));
    originalSaveState(false);setButtonState();renderAll();closeModal();toast('已退出加密账户');
  }

  function accountModalHtml(){
    const active=accountSession?`${accountSession.username} · ${accountSession.mode==='github'?'跨设备加密同步':'本机加密账户'}`:'访客模式 · 数据保存在当前浏览器';
    const dirty=accountSession?.dirty?'有未同步改动':'本机已保存';
    return `<div class="account-modal"><div class="account-status"><div><strong>${esc(active)}</strong><small>${esc(dirty)}；简历原文${accountSession?.includeResumeText?'会加密同步':'默认仅留在本机'}</small></div>${accountSession?'<button class="text-btn quiet" id="accountLogout">退出</button>':''}</div><div class="account-grid"><section class="account-panel"><h3>本机加密账户</h3><p>适合在同一设备切换多个候选人。账号密码只用于解密当前浏览器中的 AES-GCM 数据。</p><label><span>自定义账号</span><input id="localAccountName" autocomplete="username" placeholder="例如 apophisML"></label><label><span>密码</span><input id="localAccountPassword" type="password" autocomplete="current-password" placeholder="至少 10 位"></label><label class="check-row"><input id="localIncludeResume" type="checkbox"><span>加密账户中保留简历原文</span></label><div class="account-actions"><button class="btn primary" id="localLogin">解锁</button><button class="btn ghost" id="localCreate">用当前数据创建</button></div></section><section class="account-panel"><h3>跨设备 GitHub 实验同步</h3><p>首次初始化需一个仅授权本仓库 Contents 读写的 Fine-grained Token。之后新设备只需相同账号密码；远端仅保存强加密密文。</p><label><span>自定义账号</span><input id="remoteAccountName" autocomplete="username" placeholder="管理员建议使用 MLliu6"></label><label><span>密码</span><input id="remoteAccountPassword" type="password" autocomplete="current-password" placeholder="建议 14 位以上强密码"></label><label><span>首次初始化 Token（之后可留空）</span><input id="remoteToken" type="password" autocomplete="off" placeholder="github_pat_…"></label><label class="check-row"><input id="remoteIncludeResume" type="checkbox"><span>将简历原文一并加密同步（默认关闭）</span></label><div class="account-actions"><button class="btn primary" id="remoteLogin">跨设备登录</button><button class="btn ghost" id="remoteEnroll">首次初始化</button>${accountSession?.mode==='github'?'<button class="btn ghost" id="remotePull">拉取</button><button class="btn ghost" id="remotePush">推送</button>':''}</div></section></div><div class="account-note"><strong>隐私边界：</strong>不会把明文简历提交到 GitHub。Git 删除操作不会抹掉历史，因此系统不实现“上传明文后再删除”。实验同步的密文和加密后的受限 Token 会进入公开 Git 历史，只应用强密码，并将 Token 权限限制到这个仓库的 Contents。</div></div>`;
  }
  function bindAccountModal(){
    $('#accountLogout')?.addEventListener('click',logoutAccount);
    $('#localLogin')?.addEventListener('click',()=>runBusy($('#localLogin'),()=>loginLocalAccount($('#localAccountName').value,$('#localAccountPassword').value)));
    $('#localCreate')?.addEventListener('click',()=>runBusy($('#localCreate'),()=>createLocalAccount($('#localAccountName').value,$('#localAccountPassword').value,$('#localIncludeResume').checked)));
    $('#remoteLogin')?.addEventListener('click',()=>runBusy($('#remoteLogin'),()=>loginGithubAccount($('#remoteAccountName').value,$('#remoteAccountPassword').value)));
    $('#remoteEnroll')?.addEventListener('click',()=>runBusy($('#remoteEnroll'),()=>enrollGithubAccount($('#remoteAccountName').value,$('#remoteAccountPassword').value,$('#remoteToken').value,$('#remoteIncludeResume').checked)));
    $('#remotePull')?.addEventListener('click',()=>runBusy($('#remotePull'),pullGithub));
    $('#remotePush')?.addEventListener('click',()=>runBusy($('#remotePush'),pushGithub));
  }
  async function runBusy(button,fn){
    if(button){button.disabled=true;button.dataset.old=button.textContent;button.textContent='处理中…';}
    try{await fn();}catch(err){console.error(err);toast(err.message||'操作失败');if(button){button.disabled=false;button.textContent=button.dataset.old||'重试';}}
  }
  function openAccountModal(){openModal('账户与加密同步',accountModalHtml());bindAccountModal();}

  function download(name,content,type='application/json'){
    const blob=new Blob([content],{type});const link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download=name;link.click();setTimeout(()=>URL.revokeObjectURL(link.href),1000);
  }
  async function downloadResumeAudit(){
    const profile=currentProfile();if(!profile)throw new Error('尚未上传简历');
    const raw=String(profile.rawText||'');
    const audit={
      format:'path-to-offer-resume-audit/v1',generatedAt:new Date().toISOString(),fileName:profile.fileName||profile.name,
      rawTextSha256:await VAULT.sha256(raw),rawCharacters:raw.length,profileVersion:profile.profileVersion||0,
      signals:profile.signals||{},rawText:raw
    };
    download(`resume-parse-audit-${today()}.json`,JSON.stringify(audit,null,2));toast('解析审计包已在本地下载');
  }
  function enhanceProfileInspector(){
    const profile=currentProfile(),inspector=$('.profile-inspector');if(!profile||!inspector||inspector.querySelector('#privacyAuditBox'))return;
    const actions=inspector.querySelector('.modal-actions');const box=document.createElement('section');box.id='privacyAuditBox';box.className='privacy-audit-box';
    box.innerHTML='<h4>本地解析审计</h4><p>直接核对浏览器提取到的文本、章节和画像信号，不把简历上传到公开仓库。</p><div class="privacy-audit-actions"><button class="btn ghost" id="viewParsedText">查看解析文本</button><button class="btn ghost" id="downloadResumeAudit">下载审计包</button></div>';
    actions?.insertAdjacentElement('beforebegin',box);
    $('#viewParsedText').onclick=()=>openModal('简历原始解析文本',`<div class="parsed-text-view">${esc(profile.rawText||'当前账户未保留简历原文')}</div>`);
    $('#downloadResumeAudit').onclick=()=>downloadResumeAudit().catch(err=>toast(err.message));
  }
  inspectProfile=function(){originalInspectProfile();enhanceProfileInspector();};
  $('#inspectProfileBtn')?.addEventListener('click',()=>setTimeout(enhanceProfileInspector,0));

  function sourceRowsHtml({blurred=false}={}){
    const sources=sourceStatus?.sources||[];
    if(!sources.length)return '<div class="empty-state"><strong>尚无刷新记录</strong><p>定时任务完成后会显示岗位源状态。</p></div>';
    return sources.map(s=>`<div class="source-status-row"><div><strong>${esc(s.label||s.name||'招聘源')}</strong><small>${esc(blurred?'https://••••••••/••••':s.url||'')}</small></div><span class="source-health ${s.ok?'ok':'bad'}">${s.ok?`${Number(s.count||0).toLocaleString()} 条`:`异常 · ${esc(blurred?'详细信息已锁定':s.error||'unknown')}`}</span></div>`).join('');
  }
  function showFullSources(){
    openModal('岗位源与刷新状态',`<div class="source-modal"><p><strong>管理员视图。</strong>重点企业官网快线约每 10 分钟运行，全国深度联邦按较低频率轮询。这里只展示公开招聘源健康信息，不包含候选人简历。</p>${sourceRowsHtml()}<div class="source-foot"><span>公开站点临时失败时保留上一版有效岗位，避免空数据覆盖。</span></div></div>`);
  }
  async function unlockAdmin(password){
    const result=await loginGithubAccount(ADMIN_ACCOUNT,password,{activate:false});
    if(result.normalized!==ADMIN_ACCOUNT)throw new Error('管理员账户不匹配');
    adminUnlocked=true;sessionStorage.setItem('pto.admin.unlocked','1');showFullSources();
  }
  showSources=function(){
    if(adminUnlocked||sessionStorage.getItem('pto.admin.unlocked')==='1'){showFullSources();return;}
    const blurred=`<div class="source-modal admin-source-blur"><p>详细源地址、异常信息与抓取健康账本</p>${sourceRowsHtml({blurred:true})}</div>`;
    openModal('岗位源与刷新状态',`<div class="admin-source-wrap">${blurred}<div class="admin-source-gate"><div class="admin-source-card"><h3>管理员信息已雾化</h3><p>输入管理员账户密码后查看详细岗位源、错误和刷新状态。候选人侧只能看到聚合健康摘要。</p><input id="adminSourcePassword" type="password" autocomplete="current-password" placeholder="管理员密码"><button class="btn primary" id="adminSourceUnlock">解锁管理员视图</button><button class="text-btn" id="adminAccountSetup">管理员首次初始化 / 账户管理 →</button></div></div></div>`);
    $('#adminSourceUnlock').onclick=()=>runBusy($('#adminSourceUnlock'),()=>unlockAdmin($('#adminSourcePassword').value));
    $('#adminAccountSetup').onclick=openAccountModal;
  };
  $('#openSourcePanel')?.addEventListener('click',event=>{event.preventDefault();showSources();});

  injectStyles();setButtonState();
  window.PTO_ACCOUNT_UI={open:openAccountModal,loginGithubAccount,createLocalAccount,loginLocalAccount,pushGithub,pullGithub,downloadResumeAudit,companyInitial};
})();
