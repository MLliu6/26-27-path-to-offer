(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  root.PTO_ACCOUNT_VAULT=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(){
  'use strict';

  const encoder=new TextEncoder();
  const decoder=new TextDecoder();
  const DEFAULT_ITERATIONS=650000;
  const VAULT_VERSION=1;

  function subtle(){
    if(!globalThis.crypto?.subtle)throw new Error('当前浏览器不支持 Web Crypto');
    return globalThis.crypto.subtle;
  }
  function normalizeAccount(value){
    return String(value||'').normalize('NFKC').trim().toLowerCase();
  }
  function bytesToBase64(bytes){
    let binary='';
    const array=bytes instanceof Uint8Array?bytes:new Uint8Array(bytes);
    for(let i=0;i<array.length;i+=0x8000)binary+=String.fromCharCode(...array.subarray(i,i+0x8000));
    if(typeof btoa==='function')return btoa(binary);
    return Buffer.from(array).toString('base64');
  }
  function base64ToBytes(value){
    if(typeof atob==='function'){
      const binary=atob(String(value||''));
      const out=new Uint8Array(binary.length);
      for(let i=0;i<binary.length;i++)out[i]=binary.charCodeAt(i);
      return out;
    }
    return new Uint8Array(Buffer.from(String(value||''),'base64'));
  }
  function bytesToHex(bytes){return [...new Uint8Array(bytes)].map(x=>x.toString(16).padStart(2,'0')).join('');}
  async function sha256(value){return bytesToHex(await subtle().digest('SHA-256',encoder.encode(String(value||''))));}
  async function accountId(username){
    const normalized=normalizeAccount(username);
    if(!normalized)throw new Error('账号不能为空');
    return sha256(`path-to-offer/account/v1/${normalized}`);
  }
  async function importPassword(password){
    if(String(password||'').length<10)throw new Error('密码至少 10 位；跨设备同步建议使用 14 位以上强密码');
    return subtle().importKey('raw',encoder.encode(String(password)),{name:'PBKDF2'},false,['deriveKey']);
  }
  async function deriveKey(password,salt,iterations){
    const material=await importPassword(password);
    return subtle().deriveKey(
      {name:'PBKDF2',salt,iterations,hash:'SHA-256'},
      material,
      {name:'AES-GCM',length:256},
      false,
      ['encrypt','decrypt']
    );
  }
  function randomBytes(length){const out=new Uint8Array(length);globalThis.crypto.getRandomValues(out);return out;}
  async function encryptJson(payload,password,context='default',iterations=DEFAULT_ITERATIONS){
    const salt=randomBytes(16),iv=randomBytes(12),rounds=Math.max(250000,Number(iterations)||DEFAULT_ITERATIONS);
    const key=await deriveKey(password,salt,rounds);
    const aad=encoder.encode(`path-to-offer/vault/v${VAULT_VERSION}/${context}`);
    const plaintext=encoder.encode(JSON.stringify(payload));
    const encrypted=await subtle().encrypt({name:'AES-GCM',iv,additionalData:aad,tagLength:128},key,plaintext);
    return {
      version:VAULT_VERSION,
      cipher:'AES-GCM-256',
      kdf:'PBKDF2-SHA256',
      iterations:rounds,
      context,
      salt:bytesToBase64(salt),
      iv:bytesToBase64(iv),
      ciphertext:bytesToBase64(new Uint8Array(encrypted)),
      updatedAt:new Date().toISOString()
    };
  }
  async function decryptJson(vault,password,expectedContext=''){
    if(!vault||Number(vault.version)!==VAULT_VERSION)throw new Error('不支持的账户数据版本');
    const context=String(vault.context||'default');
    if(expectedContext&&context!==expectedContext)throw new Error('账户数据上下文不匹配');
    const salt=base64ToBytes(vault.salt),iv=base64ToBytes(vault.iv),ciphertext=base64ToBytes(vault.ciphertext);
    const key=await deriveKey(password,salt,Number(vault.iterations)||DEFAULT_ITERATIONS);
    const aad=encoder.encode(`path-to-offer/vault/v${VAULT_VERSION}/${context}`);
    try{
      const plain=await subtle().decrypt({name:'AES-GCM',iv,additionalData:aad,tagLength:128},key,ciphertext);
      return JSON.parse(decoder.decode(plain));
    }catch(_){
      throw new Error('账号或密码错误，或账户数据已损坏');
    }
  }
  function sanitizeState(input,{includeResumeText=false}={}){
    const state=JSON.parse(JSON.stringify(input||{}));
    for(const resume of state.resumes||[]){
      if(!includeResumeText)delete resume.rawText;
      delete resume.originalFile;
      delete resume.fileBytes;
    }
    return state;
  }
  function utf8ToBase64(value){return bytesToBase64(encoder.encode(String(value||'')));}
  function base64ToUtf8(value){return decoder.decode(base64ToBytes(value));}
  function vaultPath(id){return `vaults/v1/${String(id||'').toLowerCase()}.json`;}
  function githubHeaders(token){
    const headers={'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'};
    if(token)headers.Authorization=`Bearer ${token}`;
    return headers;
  }
  async function fetchGithubVault({owner='MLliu6',repo='26-27-path-to-offer',id,token=''}){
    const path=vaultPath(id);
    const url=`https://api.github.com/repos/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/contents/${path}?ref=main`;
    const response=await fetch(url,{headers:githubHeaders(token),cache:'no-store'});
    if(response.status===404)return null;
    if(!response.ok)throw new Error(`GitHub 读取失败：HTTP ${response.status}`);
    const payload=await response.json();
    const content=String(payload.content||'').replace(/\s+/g,'');
    return {path,sha:payload.sha||'',vault:JSON.parse(base64ToUtf8(content)),url:payload.html_url||''};
  }
  async function putGithubVault({owner='MLliu6',repo='26-27-path-to-offer',id,token,vault,sha=''}){
    if(!token)throw new Error('首次绑定或写入需要 GitHub Fine-grained Token');
    const path=vaultPath(id);
    const url=`https://api.github.com/repos/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/contents/${path}`;
    const body={message:`vault: sync ${String(id).slice(0,12)}`,content:utf8ToBase64(JSON.stringify(vault)),branch:'main'};
    if(sha)body.sha=sha;
    const response=await fetch(url,{method:'PUT',headers:{...githubHeaders(token),'Content-Type':'application/json'},body:JSON.stringify(body)});
    if(!response.ok){
      let detail='';try{detail=(await response.json()).message||'';}catch(_){}
      throw new Error(`GitHub 写入失败：HTTP ${response.status}${detail?` · ${detail}`:''}`);
    }
    const payload=await response.json();
    return {path,sha:payload.content?.sha||'',commit:payload.commit?.sha||''};
  }
  async function deleteGithubVault({owner='MLliu6',repo='26-27-path-to-offer',id,token,sha}){
    if(!token||!sha)throw new Error('删除远端账户需要有效 Token 和文件 SHA');
    const path=vaultPath(id);
    const url=`https://api.github.com/repos/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/contents/${path}`;
    const body={message:`vault: retire ${String(id).slice(0,12)}`,sha,branch:'main'};
    const response=await fetch(url,{method:'DELETE',headers:{...githubHeaders(token),'Content-Type':'application/json'},body:JSON.stringify(body)});
    if(!response.ok)throw new Error(`GitHub 删除失败：HTTP ${response.status}`);
    return response.json();
  }

  return {
    DEFAULT_ITERATIONS,VAULT_VERSION,normalizeAccount,sha256,accountId,encryptJson,decryptJson,sanitizeState,
    vaultPath,fetchGithubVault,putGithubVault,deleteGithubVault,bytesToBase64,base64ToBytes
  };
});
