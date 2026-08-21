(function(){
  'use strict';
  if(!window.PTO_ACCOUNT_VAULT||typeof sourceStatus==='undefined')return;
  const V=window.PTO_ACCOUNT_VAULT;
  const C=window.PTO_CONFIG||{};
  const OWNER=String(C.vaultRepositoryOwner||'MLliu6');
  const REPO=String(C.vaultRepositoryName||'26-27-path-to-offer');
  const USER=V.normalizeAccount(C.adminAccount||'MLliu6');
  const DEFAULT_USER_REPO='path-to-offer-vault';
  const LOCAL_PREFIX='pto.secure.local.v2.';
  const DEVICE_HINT_KEY='pto.secure.device-account.v1';
  const UNLOCK_KEY='pto.source-admin-until.v1';
  const TTL=20*60*1000;
  const $=s=>document.querySelector(s);
  const e=v=>typeof esc==='function'?esc(v):String(v||'');

  function readDeviceHint(){
    try{
      const raw=localStorage.getItem(DEVICE_HINT_KEY);
      if(!raw)return null;
      const parsed=JSON.parse(raw);
      const username=V.normalizeAccount(parsed?.username);
      if(!username)return null;
      const owner=String(parsed?.owner||username).trim();
      const repo=String(parsed?.repo||'').trim();
      return {version:1,username,owner,repo,mode:String(parsed?.mode||'locked'),updatedAt:String(parsed?.updatedAt||'')};
    }catch(_){return null;}
  }
  function rememberDeviceAccount(value={}){
    const username=V.normalizeAccount(value?.username);
    if(!username)return null;
    const owner=String(value?.owner||username).trim();
    const repo=String(value?.repo||(owner.toLowerCase()===OWNER.toLowerCase()?REPO:DEFAULT_USER_REPO)).trim();
    const mode=['local','github'].includes(String(value?.mode||''))?String(value.mode):'locked';
    const safe={version:1,username,owner,repo,mode,updatedAt:new Date().toISOString()};
    // Device hint is intentionally non-secret: never persist password/token here.
    localStorage.setItem(DEVICE_HINT_KEY,JSON.stringify(safe));
    return safe;
  }
  function currentSession(){return window.PTO_ACCOUNT_SESSION&&typeof window.PTO_ACCOUNT_SESSION==='object'?window.PTO_ACCOUNT_SESSION:null;}
  function preferredRepo(hint){
    if(hint?.repo)return hint.repo;
    const owner=String(hint?.owner||hint?.username||'');
    return owner.toLowerCase()===OWNER.toLowerCase()?REPO:DEFAULT_USER_REPO;
  }

  const accountApi=window.PTO_SECURE_ACCOUNT_V2;
  const originalAccountOpen=accountApi&&typeof accountApi.openAccount==='function'?accountApi.openAccount:null;

  function decorateAccountModal(){
    if(currentSession())return;
    const hint=readDeviceHint();
    if(!hint)return;
    const localUser=$('#secureLocalUser');
    const remoteUser=$('#secureRemoteUser');
    const remoteRepo=$('#secureRemoteRepo');
    if(localUser&&!localUser.value)localUser.value=hint.username;
    if(remoteUser&&!remoteUser.value)remoteUser.value=hint.owner||hint.username;
    if(remoteRepo&&(!remoteRepo.value||remoteRepo.value===DEFAULT_USER_REPO))remoteRepo.value=preferredRepo(hint);
    const strong=$('.account-status strong');
    const small=$('.account-status small');
    if(strong)strong.textContent=`${hint.username} · 已锁定（仅本机记住）`;
    if(small)small.textContent='密码和 Token 均未保存；输入密码后解锁本机密文，或从 GitHub 读取远端账户。';
  }
  function openRememberedAccount(){
    if(originalAccountOpen)originalAccountOpen();
    decorateAccountModal();
  }
  function syncAccountButton(){
    const button=$('#githubLoginBtn');if(!button)return;
    const active=currentSession();
    if(active?.username){
      button.innerHTML=`<span class="sync-status-dot active"></span><span>${e(active.username)}</span>`;
      button.title=`${active.mode==='github'?'跨设备加密仓库':'本机加密账户'} · 点击管理`;
      if(originalAccountOpen)button.onclick=openRememberedAccount;
      return;
    }
    const hint=readDeviceHint();
    if(hint){
      button.innerHTML=`<span class="sync-status-dot"></span><span>${e(hint.username)} · 已锁定</span>`;
      button.title='仅此浏览器记住账号；密码和 Token 未保存';
      if(originalAccountOpen)button.onclick=openRememberedAccount;
    }
  }
  function installSessionObserver(){
    let current=window.PTO_ACCOUNT_SESSION||null;
    try{
      const descriptor=Object.getOwnPropertyDescriptor(window,'PTO_ACCOUNT_SESSION');
      if(descriptor&&!descriptor.configurable)return false;
      Object.defineProperty(window,'PTO_ACCOUNT_SESSION',{
        configurable:true,enumerable:true,
        get(){return current;},
        set(value){
          current=value;
          if(value?.username)rememberDeviceAccount(value);
          setTimeout(syncAccountButton,0);
        }
      });
      if(current?.username)rememberDeviceAccount(current);
      return true;
    }catch(_){return false;}
  }
  async function migrateKnownLocalVault(){
    // Upgrade path for the owner's existing browser: infer mlliu6 only when
    // this device already has the matching encrypted local vault. A fresh
    // browser/device therefore never defaults to the owner's account.
    if(readDeviceHint())return false;
    try{
      const id=await V.accountId(USER);
      if(!localStorage.getItem(`${LOCAL_PREFIX}${id}`))return false;
      rememberDeviceAccount({username:USER,owner:OWNER,repo:REPO,mode:'locked'});
      return true;
    }catch(_){return false;}
  }

  function unlocked(){return Number(sessionStorage.getItem(UNLOCK_KEY)||0)>Date.now();}
  function rows(){
    const list=sourceStatus?.sources||[];
    return list.length?list.map(s=>`<div class="source-status-row"><div><strong>${e(s.label||s.name||'招聘源')}</strong><small>${e(s.url||'')}</small></div><span class="source-health ${s.ok?'ok':'bad'}">${s.ok?`${Number(s.count||0).toLocaleString()} 条${s.preserved_previous?' · 保留上次有效数据':''}`:`异常 · ${e(s.error||'unknown')}`}</span></div>`).join(''):'<div class="empty-state"><strong>尚无刷新记录</strong></div>';
  }
  async function verify(password){
    const id=await V.accountId(USER);
    const remote=await V.fetchGithubVault({owner:OWNER,repo:REPO,id});
    if(!remote)throw new Error('管理员加密凭证尚未初始化');
    const context=`github:${OWNER.toLowerCase()}/${REPO.toLowerCase()}/${id}`;
    const payload=await V.decryptJson(remote.vault,password,context);
    if(V.normalizeAccount(payload.username)!==USER)throw new Error('管理员账户校验失败');
    sessionStorage.setItem(UNLOCK_KEY,String(Date.now()+TTL));
    return true;
  }
  function show(){
    const content=rows();
    if(unlocked()){
      openModal('岗位源与刷新状态',`<div class="source-modal"><p><strong>管理员视图。</strong>重点官网快线约每 10 分钟检查；全国深度联邦约每 2 小时检查。外部站点临时异常时保留上次有效数据。</p>${content}<div class="source-foot"><span>此门禁用于控制普通用户的信息密度，并非公开前端中的强安全边界。</span></div></div>`);
      return;
    }
    openModal('岗位源与刷新状态',`<div class="admin-source-wrap"><div class="admin-source-blur source-modal" aria-hidden="true"><p>管理员详细来源、数量、错误与抓取诊断。</p>${content}</div><div class="admin-source-gate"><div class="admin-source-card"><h3>管理员信息已雾化</h3><p>输入管理员密码后查看详细岗位源健康状态。验证只解密独立管理员凭证，不会切换或覆盖你当前的求职账户。</p><input id="sourceAdminPassword" type="password" autocomplete="current-password" placeholder="管理员密码"><button class="btn primary" id="sourceAdminVerify">验证并查看</button><div class="vault-admin-proof">密码只在当前浏览器本地参与 AES-GCM 解密。</div></div></div></div>`);
    $('#sourceAdminVerify')?.addEventListener('click',async()=>{
      try{await verify($('#sourceAdminPassword')?.value||'');closeModal();show();}
      catch(err){toast(err.message||'管理员密码错误');}
    });
  }

  installSessionObserver();
  if(accountApi&&originalAccountOpen)accountApi.openAccount=openRememberedAccount;
  const accountButton=$('#githubLoginBtn');if(accountButton)accountButton.onclick=openRememberedAccount;
  migrateKnownLocalVault().finally(syncAccountButton);
  syncAccountButton();

  const button=$('#openSourcePanel');if(button)button.onclick=show;
  if(window.PTO_SECURE_ACCOUNT_V2)window.PTO_SECURE_ACCOUNT_V2.showSources=show;
  window.PTO_SOURCE_ADMIN_GATE={show,verify};
  window.PTO_DEVICE_ACCOUNT_HINT={key:DEVICE_HINT_KEY,read:readDeviceHint,remember:rememberDeviceAccount,migrateKnownLocalVault,sync:syncAccountButton};
})();
