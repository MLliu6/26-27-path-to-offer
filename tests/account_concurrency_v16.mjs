import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const {chromium}=require(process.env.PTO_PLAYWRIGHT_MODULE||'playwright');
const browser=await chromium.launch({headless:true,...(process.env.PTO_BROWSER_EXECUTABLE?{executablePath:process.env.PTO_BROWSER_EXECUTABLE}:{})});
try{
  const context=await browser.newContext();
  await context.route('**/data/**',r=>r.fulfill({contentType:'application/json',body:JSON.stringify({jobs:[],sources:[]})}));
  const pages=await Promise.all([context.newPage(),context.newPage()]);
  await Promise.all(pages.map(async(page,i)=>{
    await page.goto(process.env.PTO_TEST_URL||'http://127.0.0.1:8765/');
    await page.waitForFunction(()=>window.PTO_ENHANCEMENTS_READY);
    await page.evaluate(i=>{state.jobs=[{id:'synthetic-'+i,company:'Synthetic '+i,role:'Test',status:'applied',timeline:[]}];},i);
    await page.locator('#githubLoginBtn').click();
    await page.locator('#secureLocalUser').fill('concurrent-test');
    await page.locator('#secureLocalPass').fill('synthetic-password-'+i);
  }));
  await Promise.all(pages.map(p=>p.locator('#secureLocalCreate').click()));
  await Promise.all(pages.map(p=>p.waitForFunction(()=>!!window.PTO_ACCOUNT_SESSION||document.querySelector('#secureAccountError')?.textContent)));
  const states=await Promise.all(pages.map(p=>p.evaluate(()=>({active:!!window.PTO_ACCOUNT_SESSION,error:document.querySelector('#secureAccountError')?.textContent}))));
  assert.equal(states.filter(s=>s.active).length,1);
  assert.ok(states.find(s=>!s.active).error.includes('已有'));
  const winner=states.findIndex(s=>s.active),page=pages[winner];
  const saved=await page.evaluate(async()=>{
    const session=window.PTO_ACCOUNT_SESSION;
    const raw=localStorage.getItem('pto.secure.local.v2.'+session.id);
    return (await PTO_ACCOUNT_VAULT.decryptJson(JSON.parse(raw),session.password)).state.jobs;
  });
  assert.equal(saved[0].id,'synthetic-'+winner);
  // The second tab cannot silently overwrite newer changes after both unlock.
  const loser=pages[1-winner];
  await loser.locator('#secureLocalPass').fill('synthetic-password-'+winner);
  await loser.locator('#secureLocalUnlock').click();await loser.waitForFunction(()=>!!window.PTO_ACCOUNT_SESSION);
  await page.evaluate(async()=>{state.jobs[0].notes='first writer';await PTO_SECURE_ACCOUNT_V2.flushLocal();});
  const conflict=await loser.evaluate(async()=>{state.jobs[0].notes='second writer';try{await PTO_SECURE_ACCOUNT_V2.flushLocal();return '';}catch(e){return e.message;}});
  assert.ok(conflict.includes('另一标签页'));
  console.log('v1.6 concurrent account creation and cross-tab write protection: PASS');
  await context.close();
}finally{await browser.close();}
