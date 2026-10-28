// Isolated synthetic accounts only. No real browser profiles or user records.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const {chromium}=require(process.env.PTO_PLAYWRIGHT_MODULE||'playwright');
const browser=await chromium.launch({headless:true,...(process.env.PTO_BROWSER_EXECUTABLE?{executablePath:process.env.PTO_BROWSER_EXECUTABLE}:{})});
const errors=[];
const jobs=[
  {i:'one',c:'回归企业',r:'软件工程师',l:'北京',b:'2027届校园招聘',s:'direct-official:test',u:'https://example.com/job/one',d:'Python Java 软件开发',observed_at:'2026-10-28'},
  {i:'two',c:'回归银行',r:'风险分析师',l:'上海',b:'2027届校园招聘',s:'direct-official:test',u:'https://example.com/job/two'},
  {i:'old',c:'历史企业',r:'软件工程师',l:'北京',b:'2026届校园招聘',s:'direct-official:test',u:'https://example.com/job/old',status:'closed'}
];
const seed={schemaVersion:2,jobs:[{id:'kept',company:'合成测试企业',role:'研发工程师',status:'applied',statusDate:'2026-10-01',priority:'B',notes:'PRESERVE ALL NOTES',timeline:[{status:'applied',date:'2026-10-01'}],resumeVersion:'原始版本'}],resumes:[{id:'cv',name:'原始版本',rawText:'PRIVATE SYNTHETIC RESUME ONLY',uploadedAt:'2026-10-01',signals:{skills:[],directions:[]}}],activeResumeId:'cv',reviews:[],assets:[],decisions:{},preferences:{targetLocations:[],targetDirections:[]}};
async function context(withSeed=false){
  const ctx=await browser.newContext({viewport:{width:1440,height:1000},acceptDownloads:true});
  if(withSeed)await ctx.addInitScript(value=>{if(!sessionStorage.getItem('seeded')){localStorage.setItem('pathToOffer.v0.2',JSON.stringify(value));sessionStorage.setItem('seeded','1');}},seed);
  await ctx.route('**/*',route=>{
    const url=route.request().url();
    if(url.includes('/data/'))return route.fulfill({contentType:'application/json',body:JSON.stringify(url.includes('status')?{generated_at:'2026-10-28',sources:[]}:{jobs})});
    if(url.startsWith('https:'))return route.abort();
    return route.continue();
  });
  const page=await ctx.newPage();page.on('pageerror',e=>errors.push(e.message));
  page.on('dialog',d=>d.accept());
  await page.goto(process.env.PTO_TEST_URL||'http://127.0.0.1:8765/',{waitUntil:'load'});
  await page.waitForFunction(()=>window.PTO_ENHANCEMENTS_READY&&marketJobs.length>0,{timeout:45000});
  return {ctx,page};
}
async function login(page,password='synthetic-password-2027'){
  await page.locator('#githubLoginBtn').click();
  await page.locator('#secureLocalUser').fill('test-candidate');
  await page.locator('#secureLocalPass').fill(password);
  await page.locator('#secureLocalUnlock').click();
  await page.waitForFunction(()=>window.PTO_ACCOUNT_SESSION?.username==='test-candidate');
}
try{
  const {ctx,page}=await context(true);
  await page.locator('#githubLoginBtn').click();
  await page.locator('#secureLocalUser').fill('test-candidate');
  await page.locator('#secureLocalPass').fill('synthetic-password-2027');
  await page.locator('#secureLocalCreate').click();
  await page.waitForFunction(()=>window.PTO_ACCOUNT_SESSION?.username==='test-candidate');
  assert.deepEqual(await page.evaluate(()=>state.jobs),seed.jobs);
  const key=await page.evaluate(()=>Object.keys(localStorage).find(k=>k.startsWith('pto.secure.local.v2.')));
  const stored=await page.evaluate(k=>localStorage.getItem(k),key);
  assert.ok(!stored.includes('PRESERVE ALL NOTES'));
  await page.reload();await page.waitForFunction(()=>window.PTO_ENHANCEMENTS_READY&&marketJobs.length>0);
  await login(page);
  assert.equal(await page.evaluate(k=>localStorage.getItem(k),key),stored,'login must not rewrite the vault');
  assert.deepEqual(await page.evaluate(()=>state.jobs),seed.jobs);
  assert.equal(await page.evaluate(()=>state.resumes[0].rawText),seed.resumes[0].rawText);
  await page.locator('[data-view="pipeline"]').click();
  await page.locator('[data-quick-update="kept"]').first().click();
  await page.locator('#v15Update [name="status"]').selectOption('interview1');
  await page.locator('#v15Update [name="note"]').fill('准备一面');
  await page.locator('#v15Update button[type="submit"],#v15Update .btn.primary').click();
  assert.equal(await page.evaluate(()=>state.jobs[0].status),'interview1');
  await page.locator('#v15Undo button').click();
  assert.deepEqual(await page.evaluate(()=>state.jobs),seed.jobs);
  const download=page.waitForEvent('download');await page.locator('#v15Backup').click();
  const stream=await (await download).createReadStream();const chunks=[];for await(const chunk of stream)chunks.push(chunk);
  const backup=Buffer.concat(chunks);
  const other=await context();
  assert.equal(await other.page.evaluate(()=>state.jobs.length),0);
  await other.page.locator('#v15Restore').setInputFiles({name:'synthetic-encrypted.json',mimeType:'application/json',buffer:backup});
  await other.page.waitForFunction(()=>localStorage.getItem('pto.secure.device-account.v1'));
  await login(other.page);
  assert.deepEqual(await other.page.evaluate(()=>state.jobs),seed.jobs);
  assert.equal(await other.page.evaluate(()=>state.resumes[0].rawText),seed.resumes[0].rawText);
  await page.locator('#githubLoginBtn').click();await page.locator('#secureLogout').click();
  await page.waitForFunction(()=>!window.PTO_ACCOUNT_SESSION);
  await page.locator('#githubLoginBtn').click();
  await page.locator('#secureLocalPass').fill('wrong-password-2027');await page.locator('#secureLocalUnlock').click();
  await page.locator('#secureAccountError').filter({hasText:'密码'}).waitFor();
  const before=await page.evaluate(k=>localStorage.getItem(k),key);
  await page.locator('#secureLocalCreate').click();await page.locator('#secureAccountError').filter({hasText:'已有'}).waitFor();
  assert.equal(await page.evaluate(k=>localStorage.getItem(k),key),before,'existing account creation must never overwrite');
  await page.locator('#closeModal').click();
  await page.locator('[data-view="discover"]').click();
  await page.locator('#jobSearch').fill('回归银行');
  await page.waitForFunction(()=>document.querySelectorAll('#jobMarketCards .market-card').length===1);
  await page.locator('#v16Cohort').selectOption('2027');
  assert.equal(await page.locator('#jobMarketCards .market-card').count(),1);
  await page.locator('#v15SourceButton').click();
  await page.locator('#v16SourceSearch').waitFor();
  await page.locator('#v16SourceSearch').fill('金融');
  assert.ok(await page.locator('#v16SourceDirectory .v15-source-row').count()>0);
  await page.locator('#closeModal').click();
  await page.locator('#themeBtn').click();await page.locator('[data-v151-appearance="dark"]').click();
  assert.equal(await page.evaluate(()=>document.documentElement.dataset.appearance),'dark');
  await page.locator('[data-v151-appearance="light"]').click();
  await page.locator('#themeBtn').click();
  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'mobile page must not overflow');
  assert.deepEqual(errors,[]);
  await other.ctx.close();await ctx.close();
  console.log('v1.6 account, recovery, pipeline, search, sources, theme and mobile: PASS');
}finally{await browser.close();}
