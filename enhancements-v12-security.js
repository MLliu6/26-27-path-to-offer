(function(){
  'use strict';
  if(!window.PTO_ACCOUNT_VAULT||typeof state==='undefined')return;

  const VAULT=window.PTO_ACCOUNT_VAULT;
  const CONFIG=window.PTO_CONFIG||{};
  const LOCAL_PREFIX='pto.secure.local.v2.';
  const APP_OWNER=String(CONFIG.vaultRepositoryOwner||'MLliu6');
  const APP_REPO=String(CONFIG.vaultRepositoryName||'26-27-path-to-offer');
  const ADMIN_ACCOUNT=VAULT.normalizeAccount(CONFIG.adminAccount||'MLliu6');
  const DEFAULT_USER_REPO='path-to-offer-vault';
  const baseSaveState=saveState;
  const initialGuest=JSON.parse(JSON.stringify(state));
  let session=null;
  let adminUnlocked=false;
  let saveTimer=null;

  const $=s=>document.querySelector(s);
  const clone=v=>JSON.parse(JSON.stringify(v));
  const normalize=v=>typeof normalizeState==='function'?normalizeState(v||{}):(v||{});
  const localKey=id=>`${LOCAL_PREFIX}${id}`;
  const escaped=v=>typeof esc==='function'?esc(v):String(v||'');

  function injectSecurityStyles(){
    if($('#ptoV12SecurityStyle'))return;
    const style=document.createElement('style');
    style.id='ptoV12SecurityStyle';
    style.textContent=`
      .vault-security-note{font-size:10px;line-height:1.55;color:var(--muted);padding:10px 12px;border-radius:10px;background:var(--accent-soft);border:1px solid color-mix(in srgb,var(--accent) 35%,var(--line));margin-top:9px}
      .vault-security-note strong{color:var(--text)}.vault-inline{display:grid;grid-template-columns:1fr 1fr;gap:8px}.vault-check{display:flex!important;grid-template-columns:none!important;align-items:flex-start;gap:7px;margin:9px 0!important}.vault-check input{width:auto!important;margin-top:2px}.vault-check span{line-height:1.45}.vault-session-actions{display:flex;gap:7px;flex-wrap:wrap}.vault-admin-proof{font-size:9px;color:var(--muted);margin-top:8px}.company-avatar{user-select:none}
      @media(max-width:700px){.vault-inline{grid-template-columns:1fr}}
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

  // The company mark and the A/B/C priority are independent UI concepts.
  pipelineCard=function(job){
    return `<article class="job-card" draggable="true" data-job-id="${escaped(job.id)}"><div class="job-meta"><span class="job-priority-badge">优先 ${escaped(job.priority||'B')}</span><span class="date">${fmt(job.statusDate)}</span></div><div class="pipeline-card-title"><span class="company-avatar" aria-label="${escaped(job.company)}">${escaped(companyInitial(job.company))}</span><div><h3>${escaped(job.company)}</h3><p>${escaped(job.role)}</p></div></div><div class="job-meta"><span class="date">${escaped(job.location||'地点待定')}</span>${job.matchAtSave!=null?`<span class="date">match ${job.matchAtSave}</span>`:''}</div></article>`;
  };

  async function accountSpec(username,owner='',repo=''){
    const account=VAULT.normalizeAccount(username);
    if(!account)throw new Error('账号不能为空');
    const resolvedOwner=String(owner||account).trim();
    const resolvedRepo=String(repo||(resolvedOwner.toLowerCase()===APP_OWNER.toLowerCase()?APP_REPO:DEFAULT_USER_REPO)).trim();
    if(!/^[A-Za-z0-9_.-]{1,100}$/.test(resolvedOwner))throw new Error('GitHub owner 格式不正确');
    if(!/^[A-Za-z0-9_.-]{1,100}$/.test(resolvedRepo))throw new Error('GitHub 仓库名格式不正确');
    return {username:account,owner:resolvedOwner,repo:resolvedRepo,id:await VAULT.accountId(account)};
  }
  const remoteContext=spec=>`github:${spec.owner.toLowerCase()}/${spec.repo.toLowerCase()}/${spec.id}`;

  function setAccountButton(){
    const button=$('#githubLoginBtn');if(!button)return;
    if(session){
      button.innerHTML=`<span class="sync-status-dot active"></span><span>${escaped(session.username)}</span>`;
      button.title=`${session.mode==='github'?'跨设备加密仓库':'本机加密账户'} · 点击管理`;
    }else{
      button.innerHTML='<span class="sync-status-dot"></span><span>账户 / 同步</span>';
      button.title='本地账户与用户自有 GitHub 加密同步';
    }
    button.onclick=openSecureAccountModal;
  }

  async function persistEncryptedLocal(){
    if(!session)return;
    const payload={
      username:session.username,
      owner:session.owner||'',repo:session.repo||'',mode:session.mode,
      includeResumeText:!!session.includeResumeText,
      portableWrite:!!session.portableWrite,
      writeToken:session.portableWrite?(session.token||''):'',
      revision:Number(session.revision||0),
      updatedAt:new Date().toISOString(),
      state:VAULT.sanitizeState(state,{includeResumeText:!!session.includeResumeText})
    };
    const vault=await VAULT.encryptJson(payload,session.password,`local:${session.id}`);
    localStorage.setItem(localKey(session.id),JSON.stringify(vault));
    session.localUpdatedAt=payload.updatedAt;
  }
  function queuePersist(){
    if(!session)return;
    session.dirty=true;clearTimeout(saveTimer);
    saveTimer=setTimeout(()=>persistEncryptedLocal().catch(err=>console.warn('local vault save failed',err)),180);
  }

  saveState=function(render=true){
    if(!session){baseSaveState(render);return;}
    if(render)renderAll();
    queuePersist();
  };

  function activate(payload,next){
    session={...next,username:VAULT.normalizeAccount(payload.username),revision:Number(payload.revision||0),includeResumeText:!!payload.includeResumeText,portableWrite:!!payload.portableWrite,dirty:false};
    if(!session.token&&payload.writeToken)session.token=payload.writeToken;
    window.PTO_ACCOUNT_SESSION=session;
    state=normalize(clone(payload.state||{}));
    if(typeof STORAGE_KEY!=='undefined')localStorage.removeItem(STORAGE_KEY);
    if(typeof LEGACY_KEY!=='undefined')localStorage.removeItem(LEGACY_KEY);
    setAccountButton();renderAll();
  }

  async function createLocal(username,password,includeResumeText){
    const spec=await accountSpec(username);
    const key=localKey(spec.id);
    if(localStorage.getItem(key)&&!confirm('该本机账户已存在。用当前页面数据覆盖？'))return;
    const payload={username:spec.username,state:VAULT.sanitizeState(state,{includeResumeText}),includeResumeText,mode:'local',revision:1,updatedAt:new Date().toISOString()};
    activate(payload,{...spec,mode:'local',password,includeResumeText});
    // Do not expose a successful account session before its encrypted snapshot
    // actually exists. This also closes the crash/reload window between UI
    // activation and asynchronous localStorage encryption.
    await persistEncryptedLocal();
    session.dirty=false;
    toast('本机加密账户已创建');closeModal();
  }
  async function unlockLocal(username,password){
    const spec=await accountSpec(username);
    const raw=localStorage.getItem(localKey(spec.id));
    if(!raw)throw new Error('此设备没有该本机账户；跨设备数据请使用右侧 GitHub 加密仓库');
    const payload=await VAULT.decryptJson(JSON.parse(raw),password,`local:${spec.id}`);
    activate(payload,{...spec,mode:'local',password,includeResumeText:!!payload.includeResumeText});
    await persistEncryptedLocal();
    session.dirty=false;
    toast('本机账户已解锁');closeModal();
  }

  async function fetchRemote(spec,token=''){
    return VAULT.fetchGithubVault({owner:spec.owner,repo:spec.repo,id:spec.id,token});
  }
  async function initializeRemote({username,password,owner,repo,token,includeResumeText,portableWrite}){
    const spec=await accountSpec(username,owner,repo);
    if(!token||token.length<20)throw new Error('首次初始化需要仅授权该仓库 Contents 读写的 Fine-grained Token');
    await VAULT.verifyGithubToken({token,expectedLogin:spec.owner});
    const remote=await fetchRemote(spec,token);
    if(remote&&!confirm('远端已有同名加密账户。确定覆盖？'))return;
    const payload={
      username:spec.username,owner:spec.owner,repo:spec.repo,mode:'github',
      includeResumeText,portableWrite,writeToken:portableWrite?token:'',
      revision:Number(remote?.vault?.revision||0)+1,updatedAt:new Date().toISOString(),
      state:VAULT.sanitizeState(state,{includeResumeText})
    };
    const vault=await VAULT.encryptJson(payload,password,remoteContext(spec));
    const saved=await VAULT.putGithubVault({...spec,token,vault,sha:remote?.sha||''});
    activate(payload,{...spec,mode:'github',password,token,remoteSha:saved.sha,remoteUpdatedAt:payload.updatedAt,remoteVerified:true,includeResumeText,portableWrite});
    await persistEncryptedLocal();
    adminUnlocked=spec.username===ADMIN_ACCOUNT&&spec.owner.toLowerCase()===APP_OWNER.toLowerCase()&&spec.repo.toLowerCase()===APP_REPO.toLowerCase();
    toast('用户自有 GitHub 加密仓库已初始化');closeModal();
  }
  async function unlockRemote({username,password,owner,repo,token=''},{activateAccount=true}={}){
    const spec=await accountSpec(username,owner,repo);
    const remote=await fetchRemote(spec,token);
    if(!remote)throw new Error('未找到远端账户。公共仓库可直接读取；私有仓库需提供 Token');
    const payload=await VAULT.decryptJson(remote.vault,password,remoteContext(spec));
    if(VAULT.normalizeAccount(payload.username)!==spec.username)throw new Error('账户校验失败');
    const localToken=token||payload.writeToken||'';
    if(activateAccount){
      activate(payload,{...spec,mode:'github',password,token:localToken,remoteSha:remote.sha,remoteUpdatedAt:payload.updatedAt,remoteVerified:true,includeResumeText:!!payload.includeResumeText,portableWrite:!!payload.portableWrite});
      await persistEncryptedLocal();
      adminUnlocked=spec.username===ADMIN_ACCOUNT&&spec.owner.toLowerCase()===APP_OWNER.toLowerCase()&&spec.repo.toLowerCase()===APP_REPO.toLowerCase();
      toast('跨设备加密账户已解锁');closeModal();
    }
    return {spec,payload,remote,token:localToken};
  }
  async function pushRemote(){
    if(session?.mode!=='github')throw new Error('当前不是跨设备 GitHub 加密账户');
    const token=session.token;
    if(!token)throw new Error('当前设备没有写入 Token；读取不受影响，写回时请重新初始化或使用便携写入');
    await VAULT.verifyGithubToken({token,expectedLogin:session.owner});
    const remote=await fetchRemote(session,token);
    const remotePayload=remote?await VAULT.decryptJson(remote.vault,session.password,remoteContext(session)):null;
    if(session.dirty&&remotePayload?.updatedAt&&session.remoteUpdatedAt&&remotePayload.updatedAt!==session.remoteUpdatedAt&&!confirm('远端已被其他设备更新。仍用当前设备覆盖？'))return;
    const revision=Math.max(Number(session.revision||0),Number(remotePayload?.revision||0))+1;
    const payload={
      username:session.username,owner:session.owner,repo:session.repo,mode:'github',
      includeResumeText:!!session.includeResumeText,portableWrite:!!session.portableWrite,
      writeToken:session.portableWrite?token:'',revision,updatedAt:new Date().toISOString(),
      state:VAULT.sanitizeState(state,{includeResumeText:!!session.includeResumeText})
    };
    const vault=await VAULT.encryptJson(payload,session.password,remoteContext(session));
    const saved=await VAULT.putGithubVault({...session,token,vault,sha:remote?.sha||session.remoteSha||''});
    Object.assign(session,{revision,remoteSha:saved.sha,remoteUpdatedAt:payload.updatedAt,dirty:false});
    await persistEncryptedLocal();toast('已加密同步到用户自有 GitHub 仓库');openSecureAccountModal();
  }
  async function pullRemote(){
    if(session?.mode!=='github')throw new Error('当前不是跨设备 GitHub 加密账户');
    if(session.dirty&&!confirm('当前设备有未同步改动。仍用远端覆盖？'))return;
    const result=await unlockRemote(session,{activateAccount:false});
    activate(result.payload,{...result.spec,mode:'github',password:session.password,token:session.token||result.token,remoteSha:result.remote.sha,remoteUpdatedAt:result.payload.updatedAt,remoteVerified:true,includeResumeText:!!result.payload.includeResumeText,portableWrite:!!result.payload.portableWrite});
    await persistEncryptedLocal();
    toast('已读取远端加密数据');openSecureAccountModal();
  }
  function logout(){
    session=null;window.PTO_ACCOUNT_SESSION=null;adminUnlocked=false;
    state=normalize(clone(initialGuest));
    if(typeof STORAGE_KEY!=='undefined')localStorage.removeItem(STORAGE_KEY);
    if(typeof LEGACY_KEY!=='undefined')localStorage.removeItem(LEGACY_KEY);
    setAccountButton();renderAll();closeModal();toast('已退出账户');
  }

  function value(id){return $(id)?.value?.trim()||'';}
  function checked(id){return !!$(id)?.checked;}
  function accountHtml(){
    const active=session?`${session.username} · ${session.mode==='github'?'跨设备加密仓库':'本机加密账户'}`:'访客模式 · 数据保存在当前浏览器';
    const admin=session&&adminUnlocked?' · 管理员已验证':'';
    return `<div class="account-modal"><div class="account-status"><div><strong>${escaped(active)}${admin}</strong><small>${session?.dirty?'有未保存/同步改动':'本机状态已保存'}；简历原文${session?.includeResumeText?'包含在加密数据中':'默认仅留在当前浏览器'}</small></div>${session?'<button class="text-btn quiet" id="secureLogout">退出</button>':''}</div>
    ${session?`<div class="vault-session-actions">${session.mode==='github'?'<button class="btn primary" id="securePush">同步到 GitHub</button><button class="btn ghost" id="securePull">读取 GitHub</button>':''}<button class="btn ghost" id="secureExport">导出当前账户数据</button></div>`:''}
    <div class="account-grid"><section class="account-panel"><h3>本机加密账户</h3><p>账号密码只在此浏览器派生 AES-GCM 密钥；不联网，不创建传统服务器账号。</p><label><span>自定义账号</span><input id="secureLocalUser" autocomplete="username"></label><label><span>密码（至少 10 位）</span><input id="secureLocalPass" type="password" autocomplete="current-password"></label><label class="vault-check"><input id="secureLocalResume" type="checkbox"><span>把简历解析原文也放入本机加密账户</span></label><div class="account-actions"><button class="btn primary" id="secureLocalUnlock">解锁</button><button class="btn ghost" id="secureLocalCreate">创建 / 覆盖</button></div></section>
    <section class="account-panel"><h3>跨设备 GitHub 加密仓库</h3><p>账号默认等于 GitHub 用户名，默认仓库为 <code>path-to-offer-vault</code>；你本人可使用本项目仓库。公共仓库支持新设备仅凭账号密码读取，写入仍需 Token，除非明确开启便携写入凭据。</p><div class="vault-inline"><label><span>账号 / GitHub owner</span><input id="secureRemoteUser" autocomplete="username" value="${escaped(session?.username||'')}"></label><label><span>仓库</span><input id="secureRemoteRepo" value="${escaped(session?.repo||DEFAULT_USER_REPO)}"></label></div><label><span>加密密码</span><input id="secureRemotePass" type="password" autocomplete="current-password"></label><label><span>Fine-grained Token（首次写入 / 私有仓库读取）</span><input id="secureRemoteToken" type="password" autocomplete="off" placeholder="仅限该仓库 Contents 读写"></label><label class="vault-check"><input id="secureRemoteResume" type="checkbox"><span>把简历解析原文纳入远端加密包（默认关闭）</span></label><label class="vault-check"><input id="securePortableWrite" type="checkbox"><span>便携写入：把最小权限 Token 一并加密，使新设备只凭账号密码也可写回。安全性低于每台设备单独输入 Token。</span></label><div class="account-actions"><button class="btn primary" id="secureRemoteUnlock">跨设备读取</button><button class="btn ghost" id="secureRemoteInit">首次初始化 / 覆盖</button></div><div class="vault-security-note"><strong>零明文原则：</strong>仓库中只有 AES-GCM 密文；密码从不上传。Git 删除不能抹除历史，因此系统不会把明文简历“上传后再删”。</div></section></div></div>`;
  }
  function bindAccountActions(){
    $('#secureLogout')?.addEventListener('click',logout);
    $('#secureExport')?.addEventListener('click',()=>{const blob=new Blob([JSON.stringify(VAULT.sanitizeState(state,{includeResumeText:!!session?.includeResumeText}),null,2)],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=`path-to-offer-account-${today()}.json`;a.click();URL.revokeObjectURL(a.href);});
    $('#securePush')?.addEventListener('click',()=>pushRemote().catch(err=>toast(err.message)));
    $('#securePull')?.addEventListener('click',()=>pullRemote().catch(err=>toast(err.message)));
    $('#secureLocalCreate')?.addEventListener('click',()=>createLocal(value('#secureLocalUser'),value('#secureLocalPass'),checked('#secureLocalResume')).catch(err=>toast(err.message)));
    $('#secureLocalUnlock')?.addEventListener('click',()=>unlockLocal(value('#secureLocalUser'),value('#secureLocalPass')).catch(err=>toast(err.message)));
    const remoteArgs=()=>({username:value('#secureRemoteUser'),owner:value('#secureRemoteUser'),repo:value('#secureRemoteRepo'),password:value('#secureRemotePass'),token:value('#secureRemoteToken'),includeResumeText:checked('#secureRemoteResume'),portableWrite:checked('#securePortableWrite')});
    $('#secureRemoteInit')?.addEventListener('click',()=>initializeRemote(remoteArgs()).catch(err=>toast(err.message)));
    $('#secureRemoteUnlock')?.addEventListener('click',()=>unlockRemote(remoteArgs()).catch(err=>toast(err.message)));
  }
  function openSecureAccountModal(){openModal('账户、隐私与同步',accountHtml());bindAccountActions();}

  function sourceRowsHtml(){
    const sources=sourceStatus?.sources||[];
    if(!sources.length)return '<div class="empty-state"><strong>尚无刷新记录</strong><p>定时任务完成后显示来源、数量、最近错误与保留状态。</p></div>';
    return sources.map(source=>`<div class="source-status-row"><div><strong>${escaped(source.label||source.name||'招聘源')}</strong><small>${escaped(source.url||'')}</small></div><span class="source-health ${source.ok?'ok':'bad'}">${source.ok?`${Number(source.count||0).toLocaleString()} 条${source.preserved_previous?' · 保留上次有效数据':''}`:`异常 · ${escaped(source.error||'unknown')}`}</span></div>`).join('');
  }
  function adminVerified(){return !!(adminUnlocked&&session?.username===ADMIN_ACCOUNT&&session?.remoteVerified&&String(session.owner).toLowerCase()===APP_OWNER.toLowerCase()&&String(session.repo).toLowerCase()===APP_REPO.toLowerCase());}
  function showAdminSources(){
    const rows=sourceRowsHtml();
    if(adminVerified()){
      openModal('岗位源与刷新状态',`<div class="source-modal"><p><strong>管理员视图。</strong>重点企业官网约每 10 分钟刷新；全国深度联邦约每 2 小时刷新。失败时保留上一版有效数据。</p>${rows}<div class="source-foot"><span>界面门禁用于减少普通用户的信息噪音；由于站点代码和公开 feed 位于公共仓库，它不是数据保密边界。</span></div></div>`);return;
    }
    openModal('岗位源与刷新状态',`<div class="admin-source-wrap"><div class="admin-source-blur source-modal" aria-hidden="true"><p>管理员详细来源、数量、错误与抓取诊断。</p>${rows}</div><div class="admin-source-gate"><div class="admin-source-card"><h3>管理员信息已雾化</h3><p>输入管理员加密账户密码后查看详细来源健康状态。账号固定为 ${escaped(ADMIN_ACCOUNT)}，验证目标固定为 ${escaped(APP_OWNER)}/${escaped(APP_REPO)}。</p><input id="secureAdminPass" type="password" autocomplete="current-password" placeholder="管理员密码"><input id="secureAdminToken" type="password" autocomplete="off" placeholder="私有仓库时填写 Token（公共仓库可留空）"><button class="btn primary" id="secureAdminUnlock">解锁管理员视图</button><div class="vault-admin-proof">密码只在浏览器本地用于解密管理员 vault，不会发送给招聘源。</div></div></div></div>`);
    $('#secureAdminUnlock')?.addEventListener('click',async()=>{
      try{
        await unlockRemote({username:ADMIN_ACCOUNT,password:value('#secureAdminPass'),owner:APP_OWNER,repo:APP_REPO,token:value('#secureAdminToken')},{activateAccount:true});
        adminUnlocked=true;closeModal();showAdminSources();
      }catch(err){toast(err.message||'管理员验证失败');}
    });
  }
  showSources=showAdminSources;

  injectSecurityStyles();
  setAccountButton();
  const sourceButton=$('#openSourcePanel');if(sourceButton)sourceButton.onclick=showAdminSources;
  window.PTO_SECURE_ACCOUNT_V2={openAccount:openSecureAccountModal,showSources:showAdminSources,companyInitial};
})();