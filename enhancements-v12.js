(function(){
  'use strict';
  if(typeof state==='undefined'||typeof emptyState!=='function')return;

  const CONFIG=window.PTO_CONFIG||{};
  const ACCOUNT_INDEX_KEY='pto.accounts.v1';
  const ACTIVE_ACCOUNT_KEY='pto.account.active.v1';
  const VAULT_PREFIX='pto.vault.v1.';
  const ADMIN_SESSION_KEY='pto.source.admin.until';
  const ADMIN_TOKEN=CONFIG.sourceAdminToken||'UFRPLVNvdXJjZXMtN0txOS1SMm1WLTIwMjc=';
  const encoder=new TextEncoder();
  const decoder=new TextDecoder();
  let activeVault=null;
  let persistTimer=null;
  let persistChain=Promise.resolve();

  function byId(id){return document.getElementById(id);}
  function bytesToBase64(bytes){
    let binary='';const array=bytes instanceof Uint8Array?bytes:new Uint8Array(bytes);
    for(let i=0;i<array.length;i+=0x8000)binary+=String.fromCharCode(...array.subarray(i,i+0x8000));
    return btoa(binary);
  }
  function base64ToBytes(value){const raw=atob(String(value||''));const out=new Uint8Array(raw.length);for(let i=0;i<raw.length;i++)out[i]=raw.charCodeAt(i);return out;}
  function randomBytes(n){const out=new Uint8Array(n);crypto.getRandomValues(out);return out;}
  async function sha256(value){return new Uint8Array(await crypto.subtle.digest('SHA-256',encoder.encode(String(value||''))));}
  async function accountId(username){return [...await sha256(`PTO-ACCOUNT-v1\u0000${username.trim().toLowerCase()}`)].map(x=>x.toString(16).padStart(2,'0')).join('').slice(0,32);}
  async function authToken(username,password){return bytesToBase64(await sha256(`PTO-REMOTE-AUTH-v1\u0000${username.trim().toLowerCase()}\u0000${password}`));}
  async function deriveKey(username,password,salt){
    const material=await crypto.subtle.importKey('raw',encoder.encode(`${username.trim().toLowerCase()}\u0000${password}`),'PBKDF2',false,['deriveKey']);
    return crypto.subtle.deriveKey({name:'PBKDF2',salt,iterations:310000,hash:'SHA-256'},material,{name:'AES-GCM',length:256},false,['encrypt','decrypt']);
  }
  async function encryptJson(key,value){const iv=randomBytes(12);const plain=encoder.encode(JSON.stringify(value));const cipher=await crypto.subtle.encrypt({name:'AES-GCM',iv},key,plain);return {iv:bytesToBase64(iv),cipher:bytesToBase64(cipher)};}
  async function decryptJson(key,box){const plain=await crypto.subtle.decrypt({name:'AES-GCM',iv:base64ToBytes(box.iv)},key,base64ToBytes(box.cipher));return JSON.parse(decoder.decode(plain));}
  function accountIndex(){try{return JSON.parse(localStorage.getItem(ACCOUNT_INDEX_KEY)||'{}');}catch(_){return {};}}
  function saveAccountIndex(index){localStorage.setItem(ACCOUNT_INDEX_KEY,JSON.stringify(index));}
  function vaultKey(id){return `${VAULT_PREFIX}${id}`;}
  function localEnvelope(id){try{return JSON.parse(localStorage.getItem(vaultKey(id))||'null');}catch(_){return null;}}
  function storeLocalEnvelope(envelope){localStorage.setItem(vaultKey(envelope.accountId),JSON.stringify(envelope));}
  function hasUserData(value=state){return !!((value.jobs||[]).length||(value.resumes||[]).length||(value.reviews||[]).length||(value.assets||[]).length);}
  function normalizeLoadedState(value){return typeof normalizeState==='function'?normalizeState(value||{}):{...emptyState(),...(value||{})};}
  function remoteConfigured(){return !!String(CONFIG.syncApiBase||'').trim();}
  function remoteUrl(id){return `${String(CONFIG.syncApiBase||'').replace(/\/$/,'')}/v1/vault/${encodeURIComponent(id)}`;}
  async function remoteGet(id,token){
    if(!remoteConfigured())return null;
    const response=await fetch(remoteUrl(id),{headers:{'X-PTO-Auth':token},cache:'no-store'});
    if(response.status===404)return null;
    if(!response.ok)throw new Error(`同步服务读取失败：HTTP ${response.status}`);
    return response.json();
  }
  async function remotePut(envelope,token){
    if(!remoteConfigured())return;
    const payload={...envelope,state:envelope.remoteState||envelope.state};delete payload.remoteState;
    const response=await fetch(remoteUrl(envelope.accountId),{method:'PUT',headers:{'Content-Type':'application/json','X-PTO-Auth':token},body:JSON.stringify(payload)});
    if(!response.ok)throw new Error(`同步服务写入失败：HTTP ${response.status}`);
  }
  function stateForRemote(value){
    const copy=JSON.parse(JSON.stringify(value||{}));
    if(CONFIG.syncRawResumeText!==true){for(const resume of copy.resumes||[])delete resume.rawText;}
    return copy;
  }
  async function makeEnvelope(username,password,value,existing=null){
    const id=existing?.accountId||await accountId(username);const salt=existing?.salt?base64ToBytes(existing.salt):randomBytes(16);const key=await deriveKey(username,password,salt);
    const verifier=existing?.verifier||await encryptJson(key,{ok:'PTO_ACCOUNT_OK',accountId:id});
    const fullState=await encryptJson(key,value);const remoteState=await encryptJson(key,stateForRemote(value));
    return {version:1,accountId:id,usernameHint:username.trim(),salt:bytesToBase64(salt),verifier,state:fullState,remoteState,updatedAt:new Date().toISOString()};
  }
  async function verifyEnvelope(username,password,envelope){
    const key=await deriveKey(username,password,base64ToBytes(envelope.salt));const check=await decryptJson(key,envelope.verifier);
    if(check?.ok!=='PTO_ACCOUNT_OK'||check?.accountId!==envelope.accountId)throw new Error('账号或密码不正确');
    return key;
  }
  async function persistVaultNow(){
    if(!activeVault)return;
    const value=JSON.parse(JSON.stringify(state));
    const envelope=await makeEnvelope(activeVault.username,activeVault.password,value,activeVault.envelope);
    activeVault.envelope=envelope;storeLocalEnvelope(envelope);
    const index=accountIndex();index[envelope.accountId]={username:activeVault.username,updatedAt:envelope.updatedAt,remote:remoteConfigured()};saveAccountIndex(index);
    if(remoteConfigured()){
      try{await remotePut(envelope,activeVault.token);activeVault.remoteError='';}
      catch(err){activeVault.remoteError=String(err?.message||err);console.warn('Encrypted sync failed; local vault retained.',err);}
    }
    updateAccountButton();
  }
  function scheduleVaultPersist(){
    clearTimeout(persistTimer);persistTimer=setTimeout(()=>{persistChain=persistChain.then(persistVaultNow).catch(err=>console.error('Vault persist failed',err));},180);
  }

  const baseSaveState=saveState;
  saveState=function(render=true){
    if(!activeVault)return baseSaveState(render);
    localStorage.removeItem(STORAGE_KEY);scheduleVaultPersist();if(render)renderAll();
  };

  async function unlockAccount(username,password,{migrate=false,envelopeOverride=null}={}){
    const cleanUser=String(username||'').trim();if(cleanUser.length<3)throw new Error('账号至少 3 个字符');if(String(password||'').length<10)throw new Error('密码至少 10 个字符');
    const id=await accountId(cleanUser);const token=await authToken(cleanUser,password);
    let envelope=envelopeOverride;
    if(!envelope&&remoteConfigured()){
      try{envelope=await remoteGet(id,token);}catch(err){console.warn('Remote vault lookup failed; trying local copy.',err);}
    }
    if(!envelope)envelope=localEnvelope(id);
    let loaded;
    if(envelope){
      const key=await verifyEnvelope(cleanUser,password,envelope);loaded=await decryptJson(key,envelope.state);
    }else{
      loaded=migrate?JSON.parse(JSON.stringify(state)):emptyState();envelope=await makeEnvelope(cleanUser,password,loaded);
    }
    activeVault={accountId:id,username:cleanUser,password,token,envelope,remoteError:''};
    state=normalizeLoadedState(loaded);localStorage.setItem(ACTIVE_ACCOUNT_KEY,id);localStorage.removeItem(STORAGE_KEY);storeLocalEnvelope(envelope);
    const index=accountIndex();index[id]={username:cleanUser,updatedAt:envelope.updatedAt,remote:remoteConfigured()};saveAccountIndex(index);
    await persistVaultNow();renderAll();updateAccountButton();closeAccountDialog();toast(remoteConfigured()?'加密账户已解锁并启用跨设备同步':'本机加密账户已解锁');
  }
  function lockAccount(){
    if(activeVault)scheduleVaultPersist();activeVault=null;state=emptyState();localStorage.removeItem(ACTIVE_ACCOUNT_KEY);localStorage.removeItem(STORAGE_KEY);renderAll();updateAccountButton();closeAccountDialog();toast('账户已锁定');
  }
  function updateAccountButton(){
    const text=byId('githubLoginText');const button=byId('githubLoginBtn');if(!text||!button)return;
    if(activeVault){text.textContent=activeVault.remoteError?'账户 · 本地已保存':'账户 · 已解锁';button.title=remoteConfigured()?'加密账户与跨设备同步':'本机加密账户';}
    else{const id=localStorage.getItem(ACTIVE_ACCOUNT_KEY);const meta=accountIndex()[id];text.textContent=meta?`解锁 ${meta.username}`:'账户 / 同步';button.title='账号密码、本机加密与同步';}
  }

  function ensureAccountDialog(){
    let overlay=byId('ptoAccountOverlay');if(overlay)return overlay;
    overlay=document.createElement('div');overlay.id='ptoAccountOverlay';overlay.className='pto-account-overlay hidden';overlay.innerHTML=`<section class="pto-account-card" role="dialog" aria-modal="true" aria-labelledby="ptoAccountTitle"><button class="icon-btn pto-account-close" aria-label="关闭">×</button><p class="eyebrow">PRIVATE LOCAL VAULT</p><h2 id="ptoAccountTitle">账户与加密同步</h2><p class="pto-account-intro">简历与求职记录默认只保存在当前浏览器。账户密码用于加密本机数据；配置同步服务后，同一账号密码可在其他设备解锁同一份端到端加密数据。</p><div class="pto-sync-state"></div><label><span>自定义账号</span><input id="ptoAccountName" autocomplete="username" placeholder="至少 3 个字符"></label><label><span>密码</span><input id="ptoAccountPassword" type="password" autocomplete="current-password" placeholder="至少 10 个字符"></label><label class="check-row pto-migrate-row"><input id="ptoAccountMigrate" type="checkbox" checked><span>新建账户时迁入当前本机记录</span></label><div class="pto-account-error" aria-live="polite"></div><div class="pto-account-actions"><button class="btn ghost" id="ptoVaultImport">导入加密账户文件</button><button class="btn ghost" id="ptoVaultExport">导出加密账户文件</button><button class="btn danger ghost hidden" id="ptoAccountLock">锁定账户</button><button class="btn primary" id="ptoAccountUnlock">解锁 / 创建</button></div><input id="ptoVaultFile" type="file" accept=".json" hidden><small class="pto-account-foot">不会把原始简历临时提交到 GitHub。Git 提交历史无法保证彻底删除，不适合承载候选人隐私数据。</small></section>`;
    document.body.appendChild(overlay);
    overlay.querySelector('.pto-account-close').onclick=closeAccountDialog;overlay.onclick=e=>{if(e.target===overlay)closeAccountDialog();};
    byId('ptoAccountUnlock').onclick=async()=>{
      const error=overlay.querySelector('.pto-account-error');error.textContent='';
      try{await unlockAccount(byId('ptoAccountName').value,byId('ptoAccountPassword').value,{migrate:byId('ptoAccountMigrate').checked});}
      catch(err){error.textContent=String(err?.message||err);}
    };
    byId('ptoAccountLock').onclick=lockAccount;
    byId('ptoVaultExport').onclick=()=>{
      if(!activeVault){overlay.querySelector('.pto-account-error').textContent='请先解锁账户';return;}
      persistChain=persistChain.then(persistVaultNow).then(()=>{
        const blob=new Blob([JSON.stringify(activeVault.envelope,null,2)],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=`path-to-offer-vault-${activeVault.accountId.slice(0,8)}.json`;a.click();URL.revokeObjectURL(a.href);toast('加密账户文件已导出');
      });
    };
    byId('ptoVaultImport').onclick=()=>byId('ptoVaultFile').click();
    byId('ptoVaultFile').onchange=async event=>{
      const file=event.target.files?.[0];if(!file)return;const error=overlay.querySelector('.pto-account-error');
      try{const envelope=JSON.parse(await file.text());await unlockAccount(byId('ptoAccountName').value,byId('ptoAccountPassword').value,{envelopeOverride:envelope});}
      catch(err){error.textContent=`导入失败：${String(err?.message||err)}`;}finally{event.target.value='';}
    };
    return overlay;
  }
  function openAccountDialog(){
    const overlay=ensureAccountDialog();overlay.classList.remove('hidden');const id=activeVault?.accountId||localStorage.getItem(ACTIVE_ACCOUNT_KEY);const meta=accountIndex()[id];
    byId('ptoAccountName').value=activeVault?.username||meta?.username||'';byId('ptoAccountPassword').value='';
    overlay.querySelector('.pto-account-error').textContent='';overlay.querySelector('.pto-sync-state').innerHTML=remoteConfigured()?'<strong>跨设备同步：已配置</strong><span>服务端只保存 AES-GCM 密文。</span>':'<strong>跨设备同步：尚未配置</strong><span>当前可使用本机加密账户，或导出加密账户文件到其他设备导入。</span>';
    byId('ptoAccountLock').classList.toggle('hidden',!activeVault);byId('ptoAccountUnlock').classList.toggle('hidden',!!activeVault);byId('ptoAccountMigrate').closest('label').classList.toggle('hidden',!!activeVault);byId('ptoVaultExport').disabled=!activeVault;
    setTimeout(()=>byId(activeVault?'ptoVaultExport':'ptoAccountPassword')?.focus(),20);
  }
  function closeAccountDialog(){byId('ptoAccountOverlay')?.classList.add('hidden');}

  function companyInitial(company){
    const value=String(company||'').replace(/^示例\s*[·.-]?\s*/,'').trim();const chinese=value.match(/[\u3400-\u9fff]/);if(chinese)return chinese[0];const latin=value.match(/[A-Za-z0-9]/);return latin?latin[0].toUpperCase():'企';
  }
  function repairCompanyAvatars(){
    for(const card of document.querySelectorAll('.job-card')){
      const id=card.dataset.id||card.dataset.jobId||card.getAttribute('data-id')||card.getAttribute('data-job-id');let job=id?(state.jobs||[]).find(x=>String(x.id)===String(id)):null;
      if(!job){job=(state.jobs||[]).find(x=>card.textContent.includes(String(x.company||'')));}
      if(!job)continue;
      let avatar=card.querySelector('.company-avatar,.job-avatar,.job-logo,.company-logo,.avatar');
      if(!avatar){avatar=[...card.querySelectorAll('span,div')].find(el=>/^[ABC]$/.test(el.textContent.trim())&&el.children.length===0&&el.getBoundingClientRect().width<=64);}
      if(!avatar)continue;avatar.textContent=companyInitial(job.company);avatar.title=job.company;avatar.setAttribute('aria-label',`${job.company} 首字标识`);avatar.classList.add('pto-company-initial');
    }
  }
  const baseRenderPipeline=renderPipeline;
  renderPipeline=function(){const out=baseRenderPipeline.apply(this,arguments);queueMicrotask(repairCompanyAvatars);return out;};
  new MutationObserver(records=>{if(records.some(r=>[...r.addedNodes].some(n=>n.nodeType===1&&(n.matches?.('.job-card')||n.querySelector?.('.job-card')))))repairCompanyAvatars();}).observe(document.body,{childList:true,subtree:true});

  function redactResume(text,displayName=''){
    let value=String(text||'');
    const rules=[
      [/\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/gi,'[EMAIL]'],
      [/(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)/g,'[PHONE]'],
      [/(?<!\d)\d{17}[\dXx](?!\d)/g,'[ID]'],
      [/(?:微信|WeChat|QQ|电话|手机|邮箱)\s*[:：]?\s*[A-Za-z0-9_.@+-]{5,}/gi,'[CONTACT]'],
      [/https?:\/\/\S+/gi,'[URL]'],
    ];
    for(const [pattern,replacement] of rules)value=value.replace(pattern,replacement);
    if(displayName&&displayName.length>=2)value=value.split(displayName).join('[NAME]');
    return value;
  }
  function diagnosticFor(profile){
    const signals=profile?.signals||{};const sections=window.PTO_PROFILE_V05?.splitSections?.(profile.rawText||'')||[];
    return {
      schema:'path-to-offer.resume-diagnostic.v1',generatedAt:new Date().toISOString(),fileName:profile.fileName||profile.name||'',profileVersion:profile.profileVersion||null,
      parser:{rawChars:String(profile.rawText||'').length,quality:signals.profileQuality||{},sectionSummary:signals.sectionSummary||[]},
      extracted:{primaryDirection:signals.primaryDirection||'',directions:signals.directionScores||[],skills:signals.skills||[],recommendedRoles:signals.recommendedRoles||[],degree:signals.degree||'',graduationYear:signals.graduationYear||'',mentionedCities:signals.mentionedCities||[]},
      redactedSectionPreviews:sections.map(section=>({section:section.label||section.name,weight:section.weight,preview:redactResume(section.text,profile.displayName||'').slice(0,900)})),
      privacyNote:'Email, phone, ID number, URL, explicit contact handles and detected display name are redacted. Review the file before sharing.'
    };
  }
  function downloadDiagnostic(){
    const profile=currentProfile();if(!profile){toast('请先上传并解析简历');return;}const diagnostic=diagnosticFor(profile);const blob=new Blob([JSON.stringify(diagnostic,null,2)],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=`resume-parser-diagnostic-${today()}.json`;a.click();URL.revokeObjectURL(a.href);toast('匿名解析诊断已导出，请分享前人工检查');
  }
  const baseInspectProfile=inspectProfile;
  inspectProfile=function(){
    baseInspectProfile.apply(this,arguments);const actions=document.querySelector('.profile-inspector .modal-actions');if(actions&&!byId('exportResumeDiagnostic')){const button=document.createElement('button');button.type='button';button.className='btn ghost';button.id='exportResumeDiagnostic';button.textContent='导出匿名解析诊断';button.onclick=downloadDiagnostic;actions.prepend(button);}
  };

  function adminPassphrase(){try{return decoder.decode(base64ToBytes(ADMIN_TOKEN));}catch(_){return '';}}
  function adminUnlocked(){return Number(sessionStorage.getItem(ADMIN_SESSION_KEY)||0)>Date.now();}
  function setPageFog(on){document.documentElement.classList.toggle('pto-admin-fog',on);}
  function ensureAdminGate(){
    let overlay=byId('ptoAdminGate');if(overlay)return overlay;
    overlay=document.createElement('div');overlay.id='ptoAdminGate';overlay.className='pto-admin-gate hidden';overlay.innerHTML=`<section class="pto-admin-card" role="dialog" aria-modal="true" aria-labelledby="ptoAdminTitle"><div class="pto-admin-lock">源</div><p class="eyebrow">ADMIN DIAGNOSTICS</p><h2 id="ptoAdminTitle">岗位源与刷新状态</h2><p>该面板包含抓取接口、失败原因和源健康信息。输入管理员密码后临时解锁。</p><label><span>管理员密码</span><input id="ptoAdminPassword" type="password" autocomplete="current-password"></label><div class="pto-admin-error" aria-live="polite"></div><div class="pto-admin-actions"><button class="btn ghost" id="ptoAdminCancel">取消</button><button class="btn primary" id="ptoAdminUnlock">解锁面板</button></div></section>`;document.body.appendChild(overlay);
    const close=()=>{overlay.classList.add('hidden');setPageFog(false);byId('ptoAdminPassword').value='';};byId('ptoAdminCancel').onclick=close;overlay.onclick=e=>{if(e.target===overlay)close();};
    const unlock=()=>{const input=byId('ptoAdminPassword');const error=overlay.querySelector('.pto-admin-error');if(input.value===adminPassphrase()){sessionStorage.setItem(ADMIN_SESSION_KEY,String(Date.now()+(Number(CONFIG.sourceAdminSessionMinutes)||20)*60000));close();rawShowSources();}else{error.textContent='密码不正确';overlay.querySelector('.pto-admin-card').classList.remove('shake');requestAnimationFrame(()=>overlay.querySelector('.pto-admin-card').classList.add('shake'));}};
    byId('ptoAdminUnlock').onclick=unlock;byId('ptoAdminPassword').onkeydown=e=>{if(e.key==='Enter')unlock();};return overlay;
  }
  const rawShowSources=showSources;
  showSources=function(){
    if(adminUnlocked())return rawShowSources();const overlay=ensureAdminGate();overlay.classList.remove('hidden');overlay.querySelector('.pto-admin-error').textContent='';setPageFog(true);setTimeout(()=>byId('ptoAdminPassword').focus(),30);
  };
  const sourceButton=byId('openSourcePanel');if(sourceButton)sourceButton.onclick=showSources;

  function installStyles(){
    if(byId('ptoV12Style'))return;const style=document.createElement('style');style.id='ptoV12Style';style.textContent=`
      .pto-account-overlay,.pto-admin-gate{position:fixed;inset:0;z-index:1900;display:grid;place-items:center;padding:20px;background:rgba(26,31,29,.36);backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px)}
      .pto-account-overlay.hidden,.pto-admin-gate.hidden{display:none}.pto-account-card,.pto-admin-card{position:relative;width:min(620px,100%);max-height:90vh;overflow:auto;border:1px solid var(--line);border-radius:22px;background:var(--surface);padding:26px;box-shadow:0 28px 90px rgba(0,0,0,.22)}
      .pto-account-card h2,.pto-admin-card h2{font-family:var(--serif);margin:4px 0 7px}.pto-account-intro,.pto-admin-card>p{color:var(--muted);line-height:1.65}.pto-account-close{position:absolute;right:16px;top:14px}.pto-account-card label,.pto-admin-card label{display:grid;gap:6px;margin-top:13px}.pto-account-card label>span,.pto-admin-card label>span{font-size:11px;color:var(--muted)}
      .pto-account-card input,.pto-admin-card input{width:100%;border:1px solid var(--line);border-radius:11px;background:var(--surface-2);color:var(--text);padding:11px 12px}.pto-sync-state{display:flex;justify-content:space-between;gap:14px;border:1px solid var(--line);border-radius:12px;padding:10px 12px;background:var(--accent-soft);font-size:11px}.pto-sync-state span{color:var(--muted);text-align:right}.pto-account-actions,.pto-admin-actions{display:flex;gap:8px;justify-content:flex-end;flex-wrap:wrap;margin-top:18px}.pto-account-error,.pto-admin-error{min-height:18px;margin-top:8px;color:#a34e4e;font-size:11px}.pto-account-foot{display:block;color:var(--muted);line-height:1.55;margin-top:14px}.pto-admin-lock{width:48px;height:48px;border-radius:15px;display:grid;place-items:center;background:var(--accent-soft);color:var(--accent-strong);font-family:var(--serif);font-weight:700}.pto-admin-card.shake{animation:ptoShake .28s ease}.pto-admin-fog .app-shell{filter:blur(8px);pointer-events:none;user-select:none}.pto-company-initial{font-family:var(--serif)!important;font-weight:700!important;text-transform:uppercase}.pto-migrate-row{display:flex!important}
      @keyframes ptoShake{25%{transform:translateX(-6px)}50%{transform:translateX(5px)}75%{transform:translateX(-3px)}}
      @media(max-width:640px){.pto-account-card,.pto-admin-card{padding:22px 17px;border-radius:18px}.pto-account-actions .btn{flex:1}.pto-sync-state{display:grid}.pto-sync-state span{text-align:left}}
    `;document.head.appendChild(style);
  }

  function bootstrapLockedAccount(){
    const id=localStorage.getItem(ACTIVE_ACCOUNT_KEY);if(!id)return;const envelope=localEnvelope(id);if(!envelope){localStorage.removeItem(ACTIVE_ACCOUNT_KEY);return;}state=emptyState();localStorage.removeItem(STORAGE_KEY);renderAll();
  }

  installStyles();ensureAccountDialog();bootstrapLockedAccount();updateAccountButton();repairCompanyAvatars();
  const accountButton=byId('githubLoginBtn');if(accountButton)accountButton.onclick=openAccountDialog;
})();
