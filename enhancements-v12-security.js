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
  let persistChain=Promise.resolve(), pendingWrites=0;
  const ADMIN_PROOF_KEY='pto.source-admin-until.v2';
  const ADMIN_PROOF_TTL=20*60*1000;

  const $=s=>document.querySelector(s);
  const clone=v=>JSON.parse(JSON.stringify(v));
  const normalize=v=>typeof normalizeState==='function'?normalizeState(v||{}):(v||{});
  const localKey=id=>`${LOCAL_PREFIX}${id}`;
  const withAccountLock=(id,fn)=>navigator.locks?navigator.locks.request(`pto-account-${id}`,fn):fn();
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
  const isReservedAdminTarget=spec=>spec.username===ADMIN_ACCOUNT&&String(spec.owner).toLowerCase()===APP_OWNER.toLowerCase()&&String(spec.repo).toLowerCase()===APP_REPO.toLowerCase();
  async function guardLocalVaultBeforeRemoteActivation(spec,password){
    const raw=localStorage.getItem(localKey(spec.id));
    if(!raw)return;
    try{await VAULT.decryptJson(JSON.parse(raw),password,`local:${spec.id}`);}
    catch(_){throw new Error('此设备已有由另一密码保护的本机账户。为防止覆盖，跨设备读取已被阻止；请打开“数据恢复”。');}
  }

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

  function persistEncryptedLocal(){
    // Capture identity before asynchronous encryption and serialize writes.
    const active=session;
    if(!active)return Promise.resolve();
    const payload={
      username:active.username,owner:active.owner||'',repo:active.repo||'',mode:active.mode,
      includeResumeText:!!active.includeResumeText,portableWrite:!!active.portableWrite,
      writeToken:active.portableWrite?(active.token||''):'',revision:Number(active.revision||0),
      updatedAt:new Date().toISOString(),state:VAULT.sanitizeState(state,{includeResumeText:true})
    };
    pendingWrites++;
    const task=persistChain.catch(()=>{}).then(async()=>{
      const vault=await VAULT.encryptJson(payload,active.password,`local:${active.id}`);
      await withAccountLock(active.id,()=>{
        const key=localKey(active.id),current=localStorage.getItem(key);
        if(active.persistedVault!==undefined&&current!==active.persistedVault)throw new Error('另一标签页已更新此账户，请先导出当前数据，再重新登录');
        const raw=JSON.stringify(vault);localStorage.setItem(key,raw);active.persistedVault=raw;
      });
      active.localUpdatedAt=payload.updatedAt;
    });
    persistChain=task;
    return task.finally(()=>{pendingWrites--;});
  }
  async function flushLocal(){clearTimeout(saveTimer);saveTimer=null;await persistEncryptedLocal();}
  function queuePersist(){
    if(!session)return;
    session.dirty=true;clearTimeout(saveTimer);
    saveTimer=setTimeout(()=>{saveTimer=null;persistEncryptedLocal().catch(err=>{console.warn('local vault save failed',err);toast('加密保存失败，请勿关闭页面；请导出备份或释放浏览器空间。');});},180);
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
    if(localStorage.getItem(key))throw new Error('此设备已有该账户，请登录或使用其他用户名');
    if(session)throw new Error('请先退出当前账户，再创建自己的账户');
    const payload={username:spec.username,state:VAULT.sanitizeState(state,{includeResumeText:true}),includeResumeText:true,mode:'local',revision:1,updatedAt:new Date().toISOString()};
    const raw=await withAccountLock(spec.id,async()=>{
      if(localStorage.getItem(key))throw new Error('此设备已有该账户，请登录或使用其他用户名');
      const vault=await VAULT.encryptJson(payload,password,`local:${spec.id}`);
      if(localStorage.getItem(key))throw new Error('此设备已有该账户，请登录或使用其他用户名');
      const serialized=JSON.stringify(vault);localStorage.setItem(key,serialized);return serialized;
    });
    activate(payload,{...spec,mode:'local',password,includeResumeText,persistedVault:raw});
    session.dirty=false;
    toast('本机加密账户已创建');closeModal();
  }
  async function unlockLocal(username,password){
    const spec=await accountSpec(username);
    const raw=localStorage.getItem(localKey(spec.id));
    if(!raw)throw new Error('此设备还没有该账户，请创建账户或导入加密备份');
    const payload=await VAULT.decryptJson(JSON.parse(raw),password,`local:${spec.id}`);
    if(VAULT.normalizeAccount(payload.username)!==spec.username)throw new Error('账户数据校验失败');
    if(session)await flushLocal();
    activate(payload,{...spec,mode:'local',password,includeResumeText:!!payload.includeResumeText,persistedVault:raw});
    session.dirty=false;
    toast('本机账户已解锁');closeModal();
  }

  async function fetchRemote(spec,token=''){
    return VAULT.fetchGithubVault({owner:spec.owner,repo:spec.repo,id:spec.id,token});
  }
  async function requirePrivateRepository(spec,token){
    const response=await fetch(`https://api.github.com/repos/${encodeURIComponent(spec.owner)}/${encodeURIComponent(spec.repo)}`,{headers:{Accept:'application/vnd.github+json',Authorization:`Bearer ${token}`},cache:'no-store'});
    if(!response.ok)throw new Error('无法读取仓库，请检查名称和 Token 权限');
    if(!(await response.json()).private)throw new Error('个人账户同步需要私有仓库，请在 GitHub 创建私有仓库后连接');
  }
  async function initializeRemote({username,password,owner,repo,token,includeResumeText,portableWrite}){
    const spec=await accountSpec(username,owner,repo);
    if(isReservedAdminTarget(spec))throw new Error('主仓库中的该路径仅用于信源管理员验证，不是个人求职账户；请使用本机账户或独立私有仓库。');
    if(!token||token.length<20)throw new Error('首次初始化需要仅授权该仓库 Contents 读写的 Fine-grained Token');
    await VAULT.verifyGithubToken({token,expectedLogin:spec.owner});
    await requirePrivateRepository(spec,token);
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
    if(activateAccount&&isReservedAdminTarget(spec))throw new Error('该远端文件是信源管理员凭据，不是个人求职账户；已阻止覆盖本机数据。');
    const localToken=token||payload.writeToken||'';
    if(activateAccount){
      await guardLocalVaultBeforeRemoteActivation(spec,password);
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
    await requirePrivateRepository(session,token);
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
  async function logout(){
    await flushLocal();
    session=null;window.PTO_ACCOUNT_SESSION=null;adminUnlocked=false;
    state=normalize(clone(initialGuest));
    if(typeof STORAGE_KEY!=='undefined')localStorage.removeItem(STORAGE_KEY);
    if(typeof LEGACY_KEY!=='undefined')localStorage.removeItem(LEGACY_KEY);
    setAccountButton();renderAll();closeModal();toast('已退出账户');
  }

  function value(id){const el=$(id);return el?.type==='password'?(el.value||''):(el?.value?.trim()||'');}
  function checked(id){return !!$(id)?.checked;}
  function accountHtml(){
    const active=session?session.username:'你的求职账户';
    return `<div class="account-modal"><div class="account-status"><div><strong>${escaped(active)}</strong><small>${session?state.jobs.length+' 条投递记录 · '+state.resumes.length+' 份简历':'在这台设备上，保存属于自己的求职进度。'}</small></div>${session?'<button class="text-btn quiet" id="secureLogout">退出账户</button>':''}</div>
    ${session?`<div class="vault-session-actions">${session.mode==='github'?'<button class="btn primary" id="securePush">同步到私有仓库</button><button class="btn ghost" id="securePull">读取私有仓库</button>':''}<button class="btn primary" id="secureBackup">导出加密备份</button><button class="btn ghost" id="secureExport">导出完整数据</button></div>`:''}
    <div class="account-grid">${session?'':`<section class="account-panel"><h3>登录本机账户</h3><p>新设备上的新用户，可以设置自己的用户名和密码。</p><form id="secureLocalForm"><label><span>用户名</span><input id="secureLocalUser" autocomplete="username" required maxlength="80" placeholder="设置或输入你的用户名"></label><label><span>密码</span><input id="secureLocalPass" type="password" autocomplete="current-password" minlength="10" required placeholder="至少 10 位"></label><input id="secureLocalResume" type="checkbox" checked hidden><div class="account-actions"><button class="btn primary" id="secureLocalUnlock" type="submit">登录</button><button class="btn ghost" id="secureLocalCreate" type="button">创建新账户</button></div></form><p class="v15-note">账户保存在当前浏览器。换设备时，导入加密备份并使用原密码登录。</p></section>`}
    <details class="account-panel account-advanced"><summary>高级：私有仓库同步</summary><p>连接自己的 GitHub 私有仓库，在多台设备间同步。</p><div class="vault-inline"><label><span>GitHub 用户名</span><input id="secureRemoteUser" autocomplete="username" value="${escaped(session?.username||'')}"></label><label><span>私有仓库名称</span><input id="secureRemoteRepo" value="${escaped(session?.repo||DEFAULT_USER_REPO)}"></label></div><label><span>加密密码</span><input id="secureRemotePass" type="password" autocomplete="current-password"></label><label><span>仓库访问 Token</span><input id="secureRemoteToken" type="password" autocomplete="off" placeholder="仅授权该私有仓库 Contents 读写"></label><label class="vault-check"><input id="secureRemoteResume" type="checkbox"><span>同步简历原文</span></label><input id="securePortableWrite" type="checkbox" hidden><div class="account-actions"><button class="btn primary" id="secureRemoteUnlock">读取账户</button><button class="btn ghost" id="secureRemoteInit">连接并同步</button></div></details></div><p id="secureAccountError" role="alert"></p><div class="account-actions"><button class="text-btn" id="secureRestore">导入加密备份</button><a class="text-btn" href="./recovery.html">恢复历史记录</a></div></div>`;
  }
  function bindAccountActions(){
    $('#secureLogout')?.addEventListener('click',()=>logout().catch(err=>toast('退出前保存失败：'+err.message)));
    $('#secureExport')?.addEventListener('click',()=>{const blob=new Blob([JSON.stringify(VAULT.sanitizeState(state,{includeResumeText:true}),null,2)],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=`path-to-offer-account-${today()}.json`;a.click();URL.revokeObjectURL(a.href);});
    $('#securePush')?.addEventListener('click',()=>pushRemote().catch(err=>toast(err.message)));
    $('#securePull')?.addEventListener('click',()=>pullRemote().catch(err=>toast(err.message)));
    let busy=false;
    async function runLocal(create){
      if(busy)return;
      const form=$('#secureLocalForm');if(!form?.reportValidity())return;
      const username=value('#secureLocalUser'),password=value('#secureLocalPass');
      if(create&&VAULT.normalizeAccount(username)!==username.trim().toLowerCase()){$('#secureAccountError').textContent='用户名请使用英文字母、数字或 . _ @ + -';return;}
      busy=true;const buttons=[...form.querySelectorAll('button')];buttons.forEach(b=>b.disabled=true);
      $('#secureAccountError').textContent='';
      try{await (create?createLocal(username,password,true):unlockLocal(username,password));}
      catch(err){if($('#secureAccountError'))$('#secureAccountError').textContent=err.message;toast(err.message);}
      finally{busy=false;buttons.forEach(b=>b.disabled=false);}
    }
    $('#secureLocalForm')?.addEventListener('submit',e=>{e.preventDefault();runLocal(false);});
    $('#secureLocalCreate')?.addEventListener('click',()=>runLocal(true));
    $('#secureBackup')?.addEventListener('click',()=>window.PTO_WORKSPACE_V15?.backup());
    $('#secureRestore')?.addEventListener('click',()=>$('#v15Restore')?.click());
    const remoteArgs=()=>({username:value('#secureRemoteUser'),owner:value('#secureRemoteUser'),repo:value('#secureRemoteRepo'),password:value('#secureRemotePass'),token:value('#secureRemoteToken'),includeResumeText:checked('#secureRemoteResume'),portableWrite:checked('#securePortableWrite')});
    $('#secureRemoteInit')?.addEventListener('click',()=>initializeRemote(remoteArgs()).catch(err=>toast(err.message)));
    $('#secureRemoteUnlock')?.addEventListener('click',()=>unlockRemote(remoteArgs()).catch(err=>toast(err.message)));
  }
  function openSecureAccountModal(){
    openModal('账户、隐私与同步',accountHtml());bindAccountActions();

  }
  function installRecoveryEntry(){
    if($('#ptoRecoveryTop'))return;
    const anchor=$('#addJobBtn');if(!anchor)return;
    const link=document.createElement('a');link.id='ptoRecoveryTop';link.className='btn ghost';link.href='./recovery.html';link.textContent='数据恢复';link.title='检查本机加密快照与旧版缓存';anchor.parentNode.insertBefore(link,anchor);
  }

  function sourceRowsHtml(){
    const sources=sourceStatus?.sources||[];
    if(!sources.length)return '<div class="empty-state"><strong>尚无刷新记录</strong><p>定时任务完成后显示来源、数量、最近错误与保留状态。</p></div>';
    return sources.map(source=>`<div class="source-status-row"><div><strong>${escaped(source.label||source.name||'招聘源')}</strong><small>${escaped(source.url||'')}</small></div><span class="source-health ${source.ok?'ok':'bad'}">${source.ok?`${Number(source.count||0).toLocaleString()} 条${source.preserved_previous?' · 保留上次有效数据':''}`:`异常 · ${escaped(source.error||'unknown')}`}</span></div>`).join('');
  }
  function adminVerified(){return Number(sessionStorage.getItem(ADMIN_PROOF_KEY)||0)>Date.now();}
  function showAdminSources(){
    const rows=sourceRowsHtml();
    if(adminVerified()){
      openModal('岗位源与刷新状态',`<div class="source-modal"><p><strong>管理员视图。</strong>重点企业官网约每 10 分钟刷新；全国深度联邦约每 2 小时刷新。失败时保留上一版有效数据。</p>${rows}<div class="source-foot"><span>界面门禁用于减少普通用户的信息噪音；由于站点代码和公开 feed 位于公共仓库，它不是数据保密边界。</span></div></div>`);return;
    }
    openModal('岗位源与刷新状态',`<div class="admin-source-wrap"><div class="admin-source-blur source-modal" aria-hidden="true"><p>管理员详细来源、数量、错误与抓取诊断。</p>${rows}</div><div class="admin-source-gate"><div class="admin-source-card"><h3>管理员信息已雾化</h3><p>输入管理员加密账户密码后查看详细来源健康状态。账号固定为 ${escaped(ADMIN_ACCOUNT)}，验证目标固定为 ${escaped(APP_OWNER)}/${escaped(APP_REPO)}。</p><input id="secureAdminPass" type="password" autocomplete="current-password" placeholder="管理员密码"><input id="secureAdminToken" type="password" autocomplete="off" placeholder="私有仓库时填写 Token（公共仓库可留空）"><button class="btn primary" id="secureAdminUnlock">解锁管理员视图</button><div class="vault-admin-proof">密码只在浏览器本地用于解密管理员 vault，不会发送给招聘源。</div></div></div></div>`);
    $('#secureAdminUnlock')?.addEventListener('click',async()=>{
      try{
        const proof=await unlockRemote({username:ADMIN_ACCOUNT,password:value('#secureAdminPass'),owner:APP_OWNER,repo:APP_REPO,token:value('#secureAdminToken')},{activateAccount:false});
        if(VAULT.normalizeAccount(proof.payload.username)!==ADMIN_ACCOUNT)throw new Error('管理员账户校验失败');
        sessionStorage.setItem(ADMIN_PROOF_KEY,String(Date.now()+ADMIN_PROOF_TTL));
        adminUnlocked=true;closeModal();showAdminSources();
      }catch(err){toast(err.message||'管理员验证失败');}
    });
  }
  showSources=showAdminSources;

  injectSecurityStyles();
  setAccountButton();

  const sourceButton=$('#openSourcePanel');if(sourceButton)sourceButton.onclick=showAdminSources;
  window.PTO_SECURE_ACCOUNT_V2={openAccount:openSecureAccountModal,showSources:showAdminSources,companyInitial,flushLocal,pending:()=>!!saveTimer||pendingWrites>0};
  document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='hidden'&&session&&(saveTimer||pendingWrites))flushLocal().catch(err=>console.warn('vault flush failed',err));});
})();
