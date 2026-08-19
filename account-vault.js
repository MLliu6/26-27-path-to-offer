(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  root.PTO_ACCOUNT_VAULT=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(){
  'use strict';
  const VERSION=1;
  const KDF_ITERATIONS=650000;
  const te=new TextEncoder();
  const td=new TextDecoder();
  const cryptoApi=()=>globalThis.crypto;

  function normalizeAccount(value){return String(value||'').trim().toLowerCase().replace(/\s+/g,'-').replace(/[^a-z0-9._@+-]/g,'').slice(0,80);}
  function assertPassword(password){if(String(password||'').length<10)throw new Error('密码至少需要 10 位');}
  function bytesToBase64(bytes){
    if(typeof Buffer!=='undefined')return Buffer.from(bytes).toString('base64');
    let out='';const a=new Uint8Array(bytes);for(let i=0;i<a.length;i++)out+=String.fromCharCode(a[i]);return btoa(out);
  }
  function base64ToBytes(value){
    if(typeof Buffer!=='undefined')return new Uint8Array(Buffer.from(String(value||''),'base64'));
    const raw=atob(String(value||''));const out=new Uint8Array(raw.length);for(let i=0;i<raw.length;i++)out[i]=raw.charCodeAt(i);return out;
  }
  function bytesToHex(bytes){return [...new Uint8Array(bytes)].map(value=>value.toString(16).padStart(2,'0')).join('');}
  async function digest(value){return new Uint8Array(await cryptoApi().subtle.digest('SHA-256',te.encode(String(value||''))));}
  async function accountId(username){
    const normalized=normalizeAccount(username);
    if(!normalized)throw new Error('账号不能为空');
    return bytesToHex(await digest(`path-to-offer:${normalized}`));
  }
  async function deriveKey(password,salt,iterations=KDF_ITERATIONS){
    assertPassword(password);
    const base=await cryptoApi().subtle.importKey('raw',te.encode(String(password)),{name:'PBKDF2'},false,['deriveKey']);
    return cryptoApi().subtle.deriveKey({name:'PBKDF2',hash:'SHA-256',salt,iterations},base,{name:'AES-GCM',length:256},false,['encrypt','decrypt']);
  }
  async function encryptJson(value,password,context='path-to-offer'){
    const salt=cryptoApi().getRandomValues(new Uint8Array(16));
    const iv=cryptoApi().getRandomValues(new Uint8Array(12));
    const key=await deriveKey(password,salt);
    const plain=te.encode(JSON.stringify(value));
    const cipher=await cryptoApi().subtle.encrypt({name:'AES-GCM',iv,additionalData:te.encode(context)},key,plain);
    return {schema:'pto-encrypted-vault',version:VERSION,kdf:'PBKDF2-SHA256',iterations:KDF_ITERATIONS,cipher:'AES-GCM-256',salt:bytesToBase64(salt),iv:bytesToBase64(iv),context,ciphertext:bytesToBase64(new Uint8Array(cipher)),updatedAt:new Date().toISOString()};
  }
  async function decryptJson(vault,password,context=vault?.context||'path-to-offer'){
    if(!vault||vault.schema!=='pto-encrypted-vault')throw new Error('远端账户文件格式无效');
    if(context&&vault.context&&String(context)!==String(vault.context))throw new Error('账户数据上下文不匹配');
    const salt=base64ToBytes(vault.salt),iv=base64ToBytes(vault.iv),cipher=base64ToBytes(vault.ciphertext);
    try{
      const key=await deriveKey(password,salt,Number(vault.iterations)||KDF_ITERATIONS);
      const plain=await cryptoApi().subtle.decrypt({name:'AES-GCM',iv,additionalData:te.encode(context)},key,cipher);
      return JSON.parse(td.decode(plain));
    }catch(error){
      if(String(error?.message||'').includes('上下文不匹配'))throw error;
      throw new Error('账号或密码错误，或者加密数据已损坏');
    }
  }
  function sanitizeState(value,{includeResumeText=false}={}){
    const clone=JSON.parse(JSON.stringify(value||{}));
    for(const resume of clone.resumes||[]){delete resume.file;delete resume.bytes;delete resume.arrayBuffer;if(!includeResumeText)delete resume.rawText;}
    for(const review of clone.reviews||[]){delete review.file;delete review.bytes;delete review.arrayBuffer;}
    return clone;
  }
  function vaultPath(id){return `vaults/v1/${id}.json`;}
  function githubHeaders(token){
    const headers={'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'};
    if(token)headers.Authorization=`Bearer ${token}`;
    return headers;
  }
  async function verifyGithubToken({token,expectedLogin=''}){
    if(!token)throw new Error('需要 GitHub Fine-grained Token');
    const response=await fetch('https://api.github.com/user',{headers:githubHeaders(token),cache:'no-store'});
    if(!response.ok)throw new Error(`GitHub Token 校验失败：HTTP ${response.status}`);
    const payload=await response.json();
    const login=String(payload.login||'');
    if(!login)throw new Error('GitHub Token 未返回有效用户');
    if(expectedLogin&&login.toLowerCase()!==String(expectedLogin).toLowerCase())throw new Error(`Token 属于 ${login}，不能写入 ${expectedLogin} 的账户仓库`);
    return {login,id:payload.id||null};
  }
  async function fetchGithubVault({owner='MLliu6',repo='26-27-path-to-offer',id,token='',ref='main'}){
    const path=vaultPath(id);const q=ref?`?ref=${encodeURIComponent(ref)}`:'';
    const response=await fetch(`https://api.github.com/repos/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/contents/${path}${q}`,{headers:githubHeaders(token),cache:'no-store'});
    if(response.status===404)return null;
    if(!response.ok)throw new Error(`读取 GitHub 加密账户失败：HTTP ${response.status}`);
    const payload=await response.json();
    const decoded=td.decode(base64ToBytes(String(payload.content||'').replace(/\s+/g,'')));
    return {vault:JSON.parse(decoded),sha:payload.sha,path,htmlUrl:payload.html_url||''};
  }
  async function putGithubVault({owner='MLliu6',repo='26-27-path-to-offer',id,token,vault,sha='',branch='main'}){
    if(!token)throw new Error('首次绑定或写入需要 GitHub Fine-grained Token');
    await verifyGithubToken({token,expectedLogin:owner});
    const path=vaultPath(id);const body={message:`vault: update encrypted account ${id.slice(0,8)}`,content:bytesToBase64(te.encode(JSON.stringify(vault))),branch};if(sha)body.sha=sha;
    const response=await fetch(`https://api.github.com/repos/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/contents/${path}`,{method:'PUT',headers:{...githubHeaders(token),'Content-Type':'application/json'},body:JSON.stringify(body)});
    if(!response.ok)throw new Error(`写入 GitHub 加密账户失败：HTTP ${response.status}`);
    const payload=await response.json();return {sha:payload.content?.sha||'',commit:payload.commit?.sha||'',path};
  }
  async function deleteGithubVault({owner='MLliu6',repo='26-27-path-to-offer',id,token,sha,branch='main'}){
    if(!token||!sha)throw new Error('删除远端账户需要有效 Token 和文件 SHA');
    await verifyGithubToken({token,expectedLogin:owner});
    const path=vaultPath(id);const response=await fetch(`https://api.github.com/repos/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/contents/${path}`,{method:'DELETE',headers:{...githubHeaders(token),'Content-Type':'application/json'},body:JSON.stringify({message:`vault: remove encrypted account ${id.slice(0,8)}`,sha,branch})});
    if(!response.ok)throw new Error(`删除 GitHub 加密账户失败：HTTP ${response.status}`);return true;
  }
  return {VERSION,KDF_ITERATIONS,normalizeAccount,accountId,encryptJson,decryptJson,sanitizeState,vaultPath,fetchGithubVault,putGithubVault,deleteGithubVault,verifyGithubToken,bytesToBase64,base64ToBytes,bytesToHex};
});