(function(){
  'use strict';
  if(!window.PTO_ACCOUNT_VAULT||typeof sourceStatus==='undefined')return;
  const V=window.PTO_ACCOUNT_VAULT;
  const C=window.PTO_CONFIG||{};
  const OWNER=String(C.vaultRepositoryOwner||'MLliu6');
  const REPO=String(C.vaultRepositoryName||'26-27-path-to-offer');
  const USER=V.normalizeAccount(C.adminAccount||'MLliu6');
  const UNLOCK_KEY='pto.source-admin-until.v1';
  const TTL=20*60*1000;
  const $=s=>document.querySelector(s);
  const e=v=>typeof esc==='function'?esc(v):String(v||'');

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
  const button=$('#openSourcePanel');if(button)button.onclick=show;
  if(window.PTO_SECURE_ACCOUNT_V2)window.PTO_SECURE_ACCOUNT_V2.showSources=show;
  window.PTO_SOURCE_ADMIN_GATE={show,verify};
})();
