// Uses an isolated browser context and synthetic data only.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const {chromium}=require(process.env.PTO_PLAYWRIGHT_MODULE||'playwright');
const browser=await chromium.launch({headless:true,...(process.env.PTO_BROWSER_EXECUTABLE?{executablePath:process.env.PTO_BROWSER_EXECUTABLE}:{})});
const context=await browser.newContext(),page=await context.newPage(),errors=[];
page.on('pageerror',e=>errors.push(e.message));
const base=process.env.PTO_TEST_URL||'http://127.0.0.1:8765/';
const fixture={id:'synthetic-search',company:'合成搜索企业',role:'软件开发工程师',location:'北京',batch:'2027届校招',graduation:'2027',education:'本科',jd:'Python Linux 软件开发',updated_at:'2026-10-28',apply_url:'https://example.com/jobs/1'};
await context.route('**/*',route=>{
  const url=route.request().url();
  if(url.includes('/data/'))return route.fulfill({contentType:'application/json',body:JSON.stringify(url.includes('status')?{generated_at:'2026-10-28',sources:[]}:{jobs:[fixture]})});
  if(url.startsWith('https:'))return route.abort();
  return route.continue();
});
try{
  await page.goto(base);await page.waitForFunction(()=>window.PTO_ENHANCEMENTS_READY&&window.PTO_RESUME_V16);
  await page.locator('[data-view=reviews]').click();await page.locator('#githubLoginBtn').click();
  assert.equal(await page.evaluate(()=>document.querySelector('.app-shell').inert),true);
  await page.locator('#closeModal').click();
  for(let i=0;i<8;i++){await page.keyboard.press('Tab');assert.equal(await page.evaluate(()=>!!document.activeElement.closest('#quickModal')),false);}
  await page.locator('#addJobBtn').click();
  assert.deepEqual(await page.evaluate(()=>({inside:!!document.activeElement.closest('#jobDrawer'),inert:document.querySelector('.app-shell').inert})),{inside:true,inert:true});
  await page.keyboard.press('Shift+Tab');assert.equal(await page.evaluate(()=>document.activeElement.type),'submit');
  await page.evaluate(()=>openModal('合成嵌套对话框','<button id="syntheticModalButton">确认</button>'));
  await page.keyboard.press('Escape');
  assert.deepEqual(await page.evaluate(()=>({drawer:document.querySelector('#jobDrawer').classList.contains('open'),inert:document.querySelector('.app-shell').inert,focus:!!document.activeElement.closest('#jobDrawer')})),{drawer:true,inert:true,focus:true});
  await page.keyboard.press('Escape');assert.equal(await page.evaluate(()=>document.activeElement.id),'addJobBtn');
  const chooser=page.waitForEvent('filechooser');await page.locator('label:has(#reviewImport)').focus();await page.keyboard.press('Enter');
  await (await chooser).setFiles({name:'synthetic-review.txt',mimeType:'text/plain',buffer:Buffer.from('合成面经记录')});
  await page.waitForFunction(()=>state.reviews.length===1);
  await page.evaluate(()=>{state.reviews.push({id:'second-review',title:'第二份合成面经',content:'合成内容',date:'2026-10-28'});renderReviews();});
  await page.locator('[data-review-id=second-review]').focus();await page.keyboard.press('Enter');
  assert.equal(await page.evaluate(()=>selectedReviewId),'second-review');
  await page.locator('[data-view=library]').click();await page.locator('#addAssetBtn').click();
  await page.locator('#assetName').fill('合成资料');await page.locator('#assetUrl').fill('javascript:alert(1)');await page.locator('#saveAsset').click();
  assert.equal(await page.evaluate(()=>state.assets.length),0);assert.equal(await page.locator('#quickModal').isVisible(),true);
  await page.locator('#assetUrl').fill('https://example.com/prep');await page.locator('#saveAsset').click();
  assert.equal(await page.evaluate(()=>state.assets.length),1);
  await page.evaluate(()=>{state.assets.push({name:'旧记录',url:'javascript:alert(1)'});renderLibrary();});
  assert.equal(await page.locator('#assetList a[href^="javascript:"]').count(),0);
  assert.deepEqual(await page.evaluate(()=>['javascript:alert(1)','data:text/html,test','file:///C:/test','https://example.com/x'].map(safeExternalUrl)),['','','','https://example.com/x']);
  await page.locator('[data-view=discover]').click();await page.locator('#jobSearch').fill('合成搜索企业');
  await page.waitForTimeout(500);await page.locator('[data-open-detail]').first().click();
  assert.equal(await page.locator('#jobDrawer').getAttribute('aria-hidden'),'false');await page.keyboard.press('Escape');
  assert.equal(await page.locator('.brand-mark svg').count(),1);
  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  assert.deepEqual(errors,[]);
  console.log('PASS: modal/drawer focus, keyboard imports/reviews, URL validation, first search click, mobile layout');
}finally{await browser.close();}
