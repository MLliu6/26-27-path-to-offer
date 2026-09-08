"""Run all synthetic legacy browser regressions and report precise failure state."""
import json
import runpy
import sys
import traceback
from pathlib import Path
from playwright.sync_api import Locator
ROOT=Path(__file__).resolve().parents[1]
original=Locator.wait_for

def diagnose_wait(self,*args,**kwargs):
    try:
        return original(self,*args,**kwargs)
    except Exception:
        try:
            snapshot=self.page.evaluate('''() => ({q:document.querySelector('#jobSearch')?.value, loc:document.querySelector('#jobLocationFilter')?.value, type:document.querySelector('#jobTypeFilter')?.value, batch:document.querySelector('#jobBatchFilter')?.value, threshold:document.querySelector('#scoreThreshold')?.value, fresh:document.querySelector('#freshOnly')?.checked, current:window.PTO_WORKSPACE_V15?.version, jobs:typeof marketJobs!=='undefined'?marketJobs.slice(0,8):[], visible:typeof visibleMarketJobs==='function'?visibleMarketJobs().map(j=>({id:j.id,company:j.company,score:j.match?.score})):[], body:document.body.innerText.slice(0,5500)})''')
            print('BROWSER_FAILURE_DIAGNOSTICS '+json.dumps(snapshot,ensure_ascii=False),flush=True)
        except Exception as error:
            print('DIAGNOSTIC_ERROR '+str(error),flush=True)
        raise
Locator.wait_for=diagnose_wait
results=[]
for name in ['browser_smoke.py','theme_smoke.py','large_catalog_smoke.py','v14_source_resilience_smoke.py','v141_feed_recovery_smoke.py','v14_pipeline_timeline_smoke.py','v12_security_browser_smoke.py']:
    print('LEGACY_START '+name,flush=True)
    try:
        runpy.run_path(str(ROOT/'tests'/name),run_name='__main__')
        results.append({'test':name,'passed':True})
    except SystemExit as e:
        results.append({'test':name,'passed':e.code in (None,0),'code':e.code})
    except Exception as e:
        traceback.print_exc()
        results.append({'test':name,'passed':False,'error':str(e)[:1500]})
    print('LEGACY_RESULT '+json.dumps(results[-1]),flush=True)
Path('/tmp/pto-v15-review').mkdir(exist_ok=True)
Path('/tmp/pto-v15-review/legacy-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
sys.exit(0 if all(r['passed'] for r in results) else 1)
