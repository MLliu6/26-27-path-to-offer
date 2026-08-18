import {webcrypto} from 'node:crypto';
import assert from 'node:assert/strict';

if(!globalThis.crypto)globalThis.crypto=webcrypto;
await import('../account-vault.js');
const V=globalThis.PTO_ACCOUNT_VAULT;

const id1=await V.accountId('  Candidate-27  ');
const id2=await V.accountId('candidate-27');
assert.equal(id1,id2,'account IDs must be deterministic and normalized');
assert.match(id1,/^[0-9a-f]{64}$/);

const state={
  jobs:[{company:'拼多多',role:'AI Infra研发工程师'}],
  resumes:[{name:'AI Infra版',rawText:'PRIVATE RESUME TEXT',signals:{skills:['vllm','cuda']}}],
  reviews:[]
};
const sanitized=V.sanitizeState(state);
assert.equal(sanitized.resumes[0].rawText,undefined,'raw resume text must be excluded by default');
assert.equal(V.sanitizeState(state,{includeResumeText:true}).resumes[0].rawText,'PRIVATE RESUME TEXT');
assert.equal(state.resumes[0].rawText,'PRIVATE RESUME TEXT','sanitization must not mutate live state');

const context=`github:${id1}`;
const payload={username:'candidate-27',state:sanitized,token:'github_pat_example_restricted_token',revision:3};
const vault=await V.encryptJson(payload,'correct horse battery staple 2027',context,250000);
assert.equal(vault.cipher,'AES-GCM-256');
assert.equal(vault.kdf,'PBKDF2-SHA256');
assert.ok(!JSON.stringify(vault).includes('拼多多'),'ciphertext envelope must not leak job data');
assert.ok(!JSON.stringify(vault).includes('github_pat'),'ciphertext envelope must not leak token');
const restored=await V.decryptJson(vault,'correct horse battery staple 2027',context);
assert.deepEqual(restored,payload);
await assert.rejects(()=>V.decryptJson(vault,'wrong password 123456',context),/账号或密码错误/);
await assert.rejects(()=>V.decryptJson(vault,'correct horse battery staple 2027','github:other'),/上下文不匹配/);
assert.equal(V.vaultPath(id1),`vaults/v1/${id1}.json`);

console.log('Path to Offer account vault crypto/privacy: PASS');
