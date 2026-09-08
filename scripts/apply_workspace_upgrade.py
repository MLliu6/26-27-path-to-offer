"""One-off PR assembly. Removed before release; never touches user vaults."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'config.js';s=p.read_text()
if "version: '1.5.0'" in s:raise SystemExit(0)
assert "version: '1.4.2'" in s
s=s.replace("version: '1.4.2'","version: '1.5.0'").replace("buildVersion: '1.4.2-target-coverage'","buildVersion: '1.5.0-neutral-workspace'")
s=s.replace("await loadPtoScript('score-explain-v14.js');", "await loadPtoScript('score-explain-v14.js');\n    await loadPtoScript('workspace-core-v15.js');\n    await loadPtoScript('workspace-v15.js');")
s=s.replace("s.onload = resolve;\n    s.onerror = () => reject(new Error(`failed to load ${src}`));", "const timer = setTimeout(() => { s.remove(); reject(new Error(`script timeout: ${src}`)); }, 15000);\n    s.onload = () => { clearTimeout(timer); resolve(); };\n    s.onerror = () => { clearTimeout(timer); reject(new Error(`failed to load ${src}`)); };")
s=s.replace("console.warn('Path to Offer enhancement load failed; base app remains usable.', err);", "console.warn('Path to Offer enhancement load failed; base app remains usable.', err);\n    const health = document.querySelector('#feedHealth');\n    if (health) health.textContent = '部分组件加载失败，请刷新重试。不要清除站点数据；原账户密文仍保留。';")
p.write_text(s)
p=ROOT/'index.html';s=p.read_text().replace('?v=1.4.1','?v=1.5.0').replace('<title>Path to Offer</title>','<title>Path to Offer · 求职工作台</title>');s=s.replace('</head>','  <link rel="stylesheet" href="workspace-v15.css?v=1.5.0">\n</head>');p.write_text(s)
p=ROOT/'scripts/recruit_domain_sweep.py';s=p.read_text().replace('int(time.time() // 3600)','int(time.time() // 7200)').replace('"clock-hour"','"clock-two-hour"');p.write_text(s)
p=ROOT/'enhancements-v12-security.js';s=p.read_text();s=s.replace('let saveTimer=null;','let saveTimer=null;\n  let persistChain=Promise.resolve(), pendingWrites=0;')
a=s.index('  async function persistEncryptedLocal(){');b=s.index('  function queuePersist()',a)
s=s[:a]+'''  function persistEncryptedLocal(){
    // Capture identity before asynchronous encryption and serialize writes.
    const active=session;
    if(!active)return Promise.resolve();
    const payload={
      username:active.username,owner:active.owner||'',repo:active.repo||'',mode:active.mode,
      includeResumeText:!!active.includeResumeText,portableWrite:!!active.portableWrite,
      writeToken:active.portableWrite?(active.token||''):'',revision:Number(active.revision||0),
      updatedAt:new Date().toISOString(),state:VAULT.sanitizeState(state,{includeResumeText:!!active.includeResumeText})
    };
    pendingWrites++;
    const task=persistChain.catch(()=>{}).then(async()=>{
      const vault=await VAULT.encryptJson(payload,active.password,`local:${active.id}`);
      localStorage.setItem(localKey(active.id),JSON.stringify(vault));
      active.localUpdatedAt=payload.updatedAt;
    });
    persistChain=task;
    return task.finally(()=>{pendingWrites--;});
  }
  async function flushLocal(){clearTimeout(saveTimer);saveTimer=null;await persistEncryptedLocal();}
''' +s[b:]
s=s.replace("saveTimer=setTimeout(()=>persistEncryptedLocal().catch(err=>console.warn('local vault save failed',err)),180);", "saveTimer=setTimeout(()=>{saveTimer=null;persistEncryptedLocal().catch(err=>{console.warn('local vault save failed',err);toast('加密保存失败，请勿关闭页面；请导出备份或释放浏览器空间。');});},180);")
s=s.replace("function logout(){\n    session=null;", "async function logout(){\n    await flushLocal();\n    session=null;")
s=s.replace("addEventListener('click',logout)", "addEventListener('click',()=>logout().catch(err=>toast('退出前保存失败：'+err.message)))")
s=s.replace("window.PTO_SECURE_ACCOUNT_V2={openAccount:openSecureAccountModal,showSources:showAdminSources,companyInitial};", "window.PTO_SECURE_ACCOUNT_V2={openAccount:openSecureAccountModal,showSources:showAdminSources,companyInitial,flushLocal,pending:()=>!!saveTimer||pendingWrites>0};\n  document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='hidden'&&session&&(saveTimer||pendingWrites))flushLocal().catch(err=>console.warn('vault flush failed',err));});")
p.write_text(s)
p=ROOT/'scripts/user_target_overlay.py';s=p.read_text();s=s.replace('"千寻智能spiritai": "千寻智能spiritai",','"千寻智能spiritai": "千寻智能",\n        "英伟达": "nvidia",\n        "新浪微博": "新浪",')
s=s.replace('    for row in live_rows:\n        if row_company(row) != cn:\n            continue\n        if pid and pid.lower() in row_pid_blob(row).lower():\n            return row','    live_rows = [r for r in live_rows if not str(r.get("s") or r.get("source") or "").startswith("curated-target:")]\n    for row in live_rows:\n        if row_company(row) != cn:\n            continue\n        blob = row_pid_blob(row) + " " + row_role(row)\n        if pid and re.search(r"(?<![0-9a-zA-Z])" + re.escape(pid) + r"(?![0-9a-zA-Z])", blob, re.I):\n            return row\n    if pid:\n        return None')
s=s.replace('    if tier:\n        note +=', '    if tier and tier != "applied":\n        note +=')
s=s.replace('live_rows = [*base_priority, *rows(DOMESTIC)]','live_rows = [*base_priority, *rows(DOMESTIC), *rows(DATA / "jobs_supplemental.json")]');p.write_text(s)
p=ROOT/'scripts/official_source_graph.py';s=p.read_text().replace('REGISTRIES = [\n    BROWSER_REGISTRY,','WORKSPACE_REGISTRY = ROOT / "sources" / "workspace_sources_v15.json"\nREGISTRIES = [\n    BROWSER_REGISTRY,\n    WORKSPACE_REGISTRY,');s=s.replace('authoritative_browser = path == BROWSER_REGISTRY','authoritative_browser = path in (BROWSER_REGISTRY, WORKSPACE_REGISTRY)');p.write_text(s)
p=ROOT/'scripts/recruit_domain_expander.py';s=p.read_text().replace('    GRAPH,\n]','    SOURCES / "workspace_sources_v15.json",\n    GRAPH,\n]');s=s.replace('        entry["handled_by"] = "dedicated-or-priority-adapter"','        entry["handled_by"] = "dedicated-or-priority-adapter"\n    if origin == "registry:workspace_sources_v15.json":\n        entry["sweep_enabled"] = False\n        entry["handled_by"] = "workspace-source-refresh"');p.write_text(s)
p=ROOT/'sources/user_target_positions_20260903.json';s=p.read_text().replace(',"tier":"applied"','');p.write_text(s)
p=ROOT/'tests/theme_smoke.py';s=p.read_text().replace('assert bg.lower()=="#101512"','assert bg.lower()=="#111113"').replace('assert surface.lower()=="#171d1a"','assert surface.lower()=="#19191c"').replace('page.wait_for_selector(".appearance-control",timeout=12000)','page.wait_for_function("window.PTO_WORKSPACE_V15",timeout=20000)');p.write_text(s)
p=ROOT/'workspace-core-v15.js';s=p.read_text().replace('return all.filter(j=>!isLead(j)||!keys.has(','return all.filter(j=>!isLead(j)||positionId(j)||!keys.has(');p.write_text(s)
p=ROOT/'workspace-v15.js';s=p.read_text().replace('})().finally(()=>{flight=null;if(button)','})().finally(()=>{flight=null;renderFeedHealth();if(button)');p.write_text(s)
print('Applied compatible v1.5 code updates. No user vault or storage key changes.')
