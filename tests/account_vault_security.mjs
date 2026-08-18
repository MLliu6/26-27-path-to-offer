import fs from 'node:fs';
import vm from 'node:vm';
import {webcrypto} from 'node:crypto';

globalThis.window=globalThis;
globalThis.crypto=webcrypto;
vm.runInThisContext(fs.readFileSync('account-vault.js','utf8'),{filename:'account-vault.js'});
const V=globalThis.PTO_ACCOUNT_VAULT;

const source={
  jobs:[{company:'拼多多',role:'AI Infra研发工程师'}],
  resumes:[{name:'AI Infra版',rawText:'PRIVATE RESUME TEXT',file:'binary',bytes:[1,2,3]}],
  reviews:[{title:'一面',file:'raw-file',bytes:[4]}],
};
const safe=V.sanitizeState(source);
if(safe.resumes[0].rawText!==undefined)throw new Error('raw resume text leaked by default');
if(safe.resumes[0].file!==undefined||safe.resumes[0].bytes!==undefined)throw new Error('resume file bytes leaked');
if(safe.reviews[0].file!==undefined||safe.reviews[0].bytes!==undefined)throw new Error('review file bytes leaked');
const opted=V.sanitizeState(source,{includeResumeText:true});
if(opted.resumes[0].rawText!=='PRIVATE RESUME TEXT')throw new Error('explicit resume-text opt-in was ignored');

const password='correct horse battery staple';
const payload={username:'mlliu6',state:safe};
const vault=await V.encryptJson(payload,password,'github:mlliu6/path-to-offer-vault/test');
const roundtrip=await V.decryptJson(vault,password,'github:mlliu6/path-to-offer-vault/test');
if(roundtrip.username!=='mlliu6')throw new Error('vault roundtrip failed');
let wrong=false;
try{await V.decryptJson(vault,'wrong password 123','github:mlliu6/path-to-offer-vault/test');}catch(_){wrong=true;}
if(!wrong)throw new Error('wrong password unexpectedly decrypted vault');

const calls=[];
globalThis.fetch=async(url,init={})=>{
  calls.push({url:String(url),method:init.method||'GET',body:init.body||''});
  if(String(url)==='https://api.github.com/user'){
    return new Response(JSON.stringify({login:'MLliu6',id:192182744}),{status:200,headers:{'Content-Type':'application/json'}});
  }
  if(String(url).includes('/contents/vaults/v1/')){
    return new Response(JSON.stringify({content:{sha:'content-sha'},commit:{sha:'commit-sha'}}),{status:201,headers:{'Content-Type':'application/json'}});
  }
  return new Response('{}',{status:404});
};
const verified=await V.verifyGithubToken({token:'github_pat_test_token_long_enough',expectedLogin:'MLliu6'});
if(verified.login!=='MLliu6')throw new Error('token identity not returned');
let mismatch=false;
try{await V.verifyGithubToken({token:'github_pat_test_token_long_enough',expectedLogin:'someone-else'});}catch(err){mismatch=String(err.message).includes('不能写入');}
if(!mismatch)throw new Error('token/repository owner mismatch was not rejected');
await V.putGithubVault({owner:'MLliu6',repo:'path-to-offer-vault',id:'abc123',token:'github_pat_test_token_long_enough',vault});
if(!calls.some(x=>x.url==='https://api.github.com/user'))throw new Error('write did not verify token owner');
if(!calls.some(x=>x.method==='PUT'&&x.url.includes('/repos/MLliu6/path-to-offer-vault/contents/vaults/v1/abc123.json')))throw new Error('vault write URL incorrect');
console.log('Path to Offer account-vault security: PASS');