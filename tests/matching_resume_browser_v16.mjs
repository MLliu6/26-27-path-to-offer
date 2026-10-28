// Synthetic browser regression; never opens an existing browser profile.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const {chromium}=require(process.env.PTO_PLAYWRIGHT_MODULE||'playwright');
const browser=await chromium.launch({headless:true,...(process.env.PTO_BROWSER_EXECUTABLE?{executablePath:process.env.PTO_BROWSER_EXECUTABLE}:{})});
const context=await browser.newContext();
const page=await context.newPage(),errors=[];
page.on('pageerror',e=>errors.push(e.message));
const seed={schemaVersion:2,jobs:[{id:'preserved',company:'合成测试企业',role:'研发',status:'applied',timeline:[{status:'applied',date:'2026-10-01'}],notes:'KEEP THIS EXACTLY'}],reviews:[],resumes:[],activeResumeId:null,assets:[],decisions:{},preferences:{targetLocations:[],targetDirections:[]}};
const job={id:'test-role',company:'回归企业',role:'AI 基础设施研发工程师',jd:'大模型推理框架 CUDA vLLM NCCL RDMA Kubernetes 分布式训练 模型服务',batch:'2027届校招',education:'本科',graduation:'2027届',sourceTier:7,location:'北京',updatedAt:'2026-10-28',applyUrl:'https://example.com/jobs/1'};
await page.addInitScript(value=>{if(!localStorage.getItem('resume-test-seeded')){localStorage.setItem('pathToOffer.v0.2',JSON.stringify(value));localStorage.setItem('resume-test-seeded','1');}},seed);
await page.route('**/*',route=>{
  const url=route.request().url();
  if(url.includes('/data/'))return route.fulfill({contentType:'application/json',body:JSON.stringify(url.includes('status')?{generated_at:'2026-10-28',sources:[]}:{jobs:[job]})});
  if(url.startsWith('https:'))return route.abort();
  return route.continue();
});
const text='教育背景\n计算机科学 硕士 2027届\n专业技能\nC++ Python Linux CUDA vLLM NCCL RDMA Kubernetes\n项目经历\n完成大模型推理框架开发，分布式训练与模型服务平台研发，优化GPU集群调度和KV Cache。';
function pdf(content=''){
  const objects=['<< /Type /Catalog /Pages 2 0 R >>','<< /Type /Pages /Kids [3 0 R] /Count 1 >>','<< /Type /Page /Parent 2 0 R /MediaBox [0 0 600 800] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>','<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',`<< /Length ${Buffer.byteLength(content)} >>\nstream\n${content}\nendstream`];
  let result='%PDF-1.4\n',offsets=[0];
  objects.forEach((o,i)=>{offsets.push(Buffer.byteLength(result));result+=`${i+1} 0 obj\n${o}\nendobj\n`;});
  const xref=Buffer.byteLength(result);result+=`xref\n0 6\n0000000000 65535 f \n${offsets.slice(1).map(n=>`${String(n).padStart(10,'0')} 00000 n \n`).join('')}trailer\n<< /Root 1 0 R /Size 6 >>\nstartxref\n${xref}\n%%EOF`;
  return Buffer.from(result);
}
function docx(){
  // Minimal stored ZIP lets the real bundled DOCX parser run without fixtures.
  const files={'[Content_Types].xml':'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>','_rels/.rels':'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>','word/document.xml':`<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>${text.split('\n').map(line=>`<w:p><w:r><w:t>${line}</w:t></w:r></w:p>`).join('')}</w:body></w:document>`};
  const local=[],central=[];let offset=0;
  for(const [name,value] of Object.entries(files)){
    const n=Buffer.from(name),data=Buffer.from(value);let crc=0xffffffff;
    for(const byte of data){crc^=byte;for(let i=0;i<8;i++)crc=(crc>>>1)^(crc&1?0xedb88320:0);}crc=(crc^0xffffffff)>>>0;
    const h=Buffer.alloc(30);h.writeUInt32LE(0x04034b50);h.writeUInt16LE(20,4);h.writeUInt32LE(crc,14);h.writeUInt32LE(data.length,18);h.writeUInt32LE(data.length,22);h.writeUInt16LE(n.length,26);
    const c=Buffer.alloc(46);c.writeUInt32LE(0x02014b50);c.writeUInt16LE(20,4);c.writeUInt16LE(20,6);c.writeUInt32LE(crc,16);c.writeUInt32LE(data.length,20);c.writeUInt32LE(data.length,24);c.writeUInt16LE(n.length,28);c.writeUInt32LE(offset,42);
    local.push(h,n,data);central.push(c,n);offset+=h.length+n.length+data.length;
  }
  const end=Buffer.alloc(22);end.writeUInt32LE(0x06054b50);end.writeUInt16LE(3,8);end.writeUInt16LE(3,10);end.writeUInt32LE(Buffer.concat(central).length,12);end.writeUInt32LE(offset,16);return Buffer.concat([...local,...central,end]);
}
try{
  await page.goto(process.env.PTO_TEST_URL||'http://127.0.0.1:8765/',{waitUntil:'load'});
  await page.waitForFunction(()=>window.PTO_ENHANCEMENTS_READY,{timeout:45000});
  // Also supports testing this isolated module before the release loader changes.
  if(!await page.evaluate(()=>!!window.PTO_RESUME_V16))await page.addScriptTag({url:'resume-core-v16.js'});
  await page.locator('#resumeImport').setInputFiles({name:'synthetic.txt',mimeType:'text/plain',buffer:Buffer.from(text)});
  await page.locator('#quickModal.show #resumePreviewSave').waitFor({state:'visible'});
  assert.equal(await page.evaluate(()=>state.resumes.length),0,'upload must wait for confirmation');
  assert.equal(await page.locator('#resumePreviewYear').inputValue(),'2027');
  await page.locator('#resumePreviewSave').click();
  await page.waitForFunction(()=>state.resumes.length===1);
  await page.waitForFunction(()=>document.querySelector('#quickModal').getAttribute('aria-hidden')==='true');
  assert.ok(await page.evaluate(j=>scoreJob(j,currentProfile()).score,job)>=90);
  await page.locator('#libraryResumeImport').setInputFiles({name:'synthetic.docx',mimeType:'application/vnd.openxmlformats-officedocument.wordprocessingml.document',buffer:docx()});
  await page.locator('#quickModal.show #resumePreviewSave').waitFor({state:'visible'});
  assert.match(await page.locator('#resumePreviewText').inputValue(),/教育背景\n/);
  await page.locator('#resumePreviewSave').click();
  await page.waitForFunction(()=>state.resumes.length===2);
  await page.waitForFunction(()=>document.querySelector('#quickModal').getAttribute('aria-hidden')==='true');
  const content='BT /F1 12 Tf 60 700 Td (Education) Tj 0 -20 Td (Computer Science Master 2027) Tj 0 -30 Td (Skills) Tj 0 -20 Td (CUDA vLLM NCCL Kubernetes C++ Python Linux) Tj 0 -20 Td (Distributed training and model serving projects) Tj ET';
  await page.locator('#libraryResumeImport').setInputFiles({name:'synthetic.pdf',mimeType:'application/pdf',buffer:pdf(content)});
  await page.locator('#quickModal.show #resumePreviewSave').waitFor({state:'visible'});
  assert.match(await page.locator('#resumePreviewText').inputValue(),/Education\nComputer/);
  await page.locator('#resumePreviewYear').fill('2028');await page.locator('#resumePreviewDegree').selectOption('硕士');
  await page.locator('#resumePreviewSave').click();await page.waitForFunction(()=>state.resumes.length===3);
  await page.waitForFunction(()=>document.querySelector('#quickModal').getAttribute('aria-hidden')==='true');
  await page.reload();await page.waitForFunction(()=>window.PTO_ENHANCEMENTS_READY,{timeout:45000});
  if(!await page.evaluate(()=>!!window.PTO_RESUME_V16))await page.addScriptTag({url:'resume-core-v16.js'});
  assert.equal(await page.evaluate(()=>currentProfile().signals.graduationYear),'2028');
  await page.locator('#libraryResumeImport').setInputFiles({name:'scan.pdf',mimeType:'application/pdf',buffer:pdf()});
  await page.locator('#quickModal.show #resumePreviewSave').waitFor({state:'visible'});
  assert.equal(await page.locator('#resumePreviewSave').isDisabled(),true);
  assert.match(await page.locator('#modalBody').innerText(),/OCR/);
  await page.locator('#resumePreviewCancel').click();
  assert.equal(await page.evaluate(()=>state.resumes.length),3);
  assert.deepEqual(await page.evaluate(()=>state.jobs),seed.jobs,'pipeline records must be byte-equivalent after parsing');
  assert.deepEqual(errors,[]);
  console.log('Resume browser v1.6: TXT, DOCX, PDF, scan guidance, confirmation, override persistence and record preservation PASS');
}finally{await browser.close();}
