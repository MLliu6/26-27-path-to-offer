window.PTO_CONFIG = Object.freeze({
  version: '1.4.0',
  buildVersion: '1.4.0-product-hardening-fit-search-sources',
  jobsFeed: './data/jobs.json',
  domesticJobsFeed: './data/jobs_cn.json',
  globalJobsFeed: './data/jobs.json',
  priorityJobsFeed: './data/jobs_priority.json',
  sourceStatusFeed: './data/source_status.json',
  prioritySourceStatusFeed: './data/priority_source_status.json',
  fullScoreLimit: 5600,
  interviewAssetsRepo: 'https://github.com/MLliu6/26-27-interview',
  githubOAuthProxy: '',
  githubClientId: '',
  githubOAuthScopes: 'read:user user:email',
  vaultRepositoryOwner: 'MLliu6',
  vaultRepositoryName: '26-27-path-to-offer',
  adminAccount: 'MLliu6',
});

window.PTO_ENHANCEMENTS_READY = false;
const PTO_NATIVE_FETCH = window.fetch.bind(window);

function ptoCanonicalText(value) {
  return String(value || '').trim().replace(/\s+/g, ' ').toLowerCase();
}

function ptoCanonicalUrl(value) {
  const raw = String(value || '').trim();
  if (!raw) return '';
  try {
    const url = new URL(raw, window.location.href);
    url.hash = '';
    const removable = ['utm_source','utm_medium','utm_campaign','utm_content','utm_term'];
    removable.forEach(key => url.searchParams.delete(key));
    return `${url.origin}${url.pathname.replace(/\/+$/, '') || '/'}${url.search}`.toLowerCase();
  } catch (_) {
    return raw.replace(/#.*$/, '').replace(/\/+$/, '').toLowerCase();
  }
}

function ptoJobKeys(job) {
  if (!job || typeof job !== 'object') return [];
  const company = ptoCanonicalText(job.c || job.company);
  const role = ptoCanonicalText(job.r || job.role || job.position);
  const location = ptoCanonicalText(job.l || job.location);
  const positionId = ptoCanonicalText(job.z || job.position_id);
  const applyUrl = ptoCanonicalUrl(job.u || job.apply_url || job.url);
  const noticeUrl = ptoCanonicalUrl(job.n || job.notice_url);
  const rawId = ptoCanonicalText(job.i || job.id);
  const keys = [];
  if (applyUrl && company && role) keys.push(`url:${applyUrl}|${company}|${role}`);
  if (noticeUrl && company && role) keys.push(`url:${noticeUrl}|${company}|${role}`);
  if (positionId && company) keys.push(`position:${company}|${positionId}`);
  // Product identity is intentionally simple: one company + one role + one city
  // is one visible opportunity. The priority feed is merged first, so when
  // several public sources describe that opportunity we keep one directly
  // clickable source instead of showing duplicate cards.
  if (company && role && location) keys.push(`fallback:${company}|${role}|${location}`);
  if (!keys.length && company && role) keys.push(`role:${company}|${role}`);
  if (!keys.length && rawId) keys.push(`id:${rawId}`);
  return [...new Set(keys)];
}

function ptoJobKey(job) {
  return ptoJobKeys(job)[0] || '';
}

function ptoMergeJobs(priorityJobs, domesticJobs) {
  const merged = [];
  const seen = new Set();
  for (const job of [...(Array.isArray(priorityJobs) ? priorityJobs : []), ...(Array.isArray(domesticJobs) ? domesticJobs : [])]) {
    const keys = ptoJobKeys(job);
    if (!keys.length || keys.some(key => seen.has(key))) continue;
    keys.forEach(key => seen.add(key));
    merged.push(job);
  }
  return merged;
}

function ptoMergeSources(priorityStatus, domesticStatus) {
  const merged = [];
  const seen = new Set();
  for (const source of [...(priorityStatus?.sources || []), ...(domesticStatus?.sources || [])]) {
    if (!source || typeof source !== 'object') continue;
    const key = String(source.name || source.label || source.url || '').trim().toLowerCase();
    if (key && seen.has(key)) continue;
    if (key) seen.add(key);
    merged.push(source);
  }
  return merged;
}

window.fetch = function ptoBootstrapFetch(input, init) {
  const url = typeof input === 'string' ? input : (input && input.url) || '';
  const globalPath = String(window.PTO_CONFIG.jobsFeed || './data/jobs.json').replace(/^\.\//, '');
  const statusPath = String(window.PTO_CONFIG.sourceStatusFeed || './data/source_status.json').replace(/^\.\//, '');
  if (!window.PTO_ENHANCEMENTS_READY && globalPath && String(url).includes(globalPath)) {
    return Promise.resolve(new Response(JSON.stringify({schema_version:4, generated_at:null, jobs:[]}), {
      status: 200,
      headers: {'Content-Type':'application/json'}
    }));
  }
  if (window.PTO_ENHANCEMENTS_READY && globalPath && String(url).includes(globalPath)) {
    const domestic = String(window.PTO_CONFIG.domesticJobsFeed || './data/jobs_cn.json');
    const priority = String(window.PTO_CONFIG.priorityJobsFeed || './data/jobs_priority.json');
    const suffix = String(url).includes('?') ? String(url).slice(String(url).indexOf('?')) : '';
    return PTO_NATIVE_FETCH(`${domestic}${suffix}`, {...(init || {}), cache:'no-store'}).then(async domesticResponse => {
      if (!domesticResponse.ok) return PTO_NATIVE_FETCH(input, init);
      const domesticPayload = await domesticResponse.json();
      let priorityPayload = {jobs:[]};
      try {
        const priorityResponse = await PTO_NATIVE_FETCH(`${priority}${suffix}`, {...(init || {}), cache:'no-store'});
        if (priorityResponse.ok) priorityPayload = await priorityResponse.json();
      } catch (err) {
        console.warn('Priority job feed unavailable; continuing with domestic feed.', err);
      }
      const payload = {
        ...domesticPayload,
        jobs: ptoMergeJobs(priorityPayload?.jobs, domesticPayload?.jobs),
        priority_generated_at: priorityPayload?.generated_at || null,
      };
      return new Response(JSON.stringify(payload), {
        status: 200,
        headers: {'Content-Type':'application/json', 'Cache-Control':'no-store'}
      });
    }).catch(() => PTO_NATIVE_FETCH(input, init));
  }
  if (window.PTO_ENHANCEMENTS_READY && statusPath && String(url).includes(statusPath)) {
    const base = String(window.PTO_CONFIG.sourceStatusFeed || './data/source_status.json');
    const priority = String(window.PTO_CONFIG.prioritySourceStatusFeed || './data/priority_source_status.json');
    const suffix = String(url).includes('?') ? String(url).slice(String(url).indexOf('?')) : '';
    return PTO_NATIVE_FETCH(`${base}${suffix}`, {...(init || {}), cache:'no-store'}).then(async domesticResponse => {
      if (!domesticResponse.ok) return domesticResponse;
      const domesticStatus = await domesticResponse.json();
      let priorityStatus = {sources:[]};
      try {
        const priorityResponse = await PTO_NATIVE_FETCH(`${priority}${suffix}`, {...(init || {}), cache:'no-store'});
        if (priorityResponse.ok) priorityStatus = await priorityResponse.json();
      } catch (err) {
        console.warn('Priority source status unavailable; continuing with primary source status.', err);
      }
      return new Response(JSON.stringify({
        ...domesticStatus,
        sources: ptoMergeSources(priorityStatus, domesticStatus),
        priority_generated_at: priorityStatus?.generated_at || null,
        priority_catalog_count: priorityStatus?.catalog_count || 0,
      }), {
        status: 200,
        headers: {'Content-Type':'application/json', 'Cache-Control':'no-store'}
      });
    }).catch(() => PTO_NATIVE_FETCH(input, init));
  }
  return PTO_NATIVE_FETCH(input, init);
};

window.addEventListener('load', () => {
  if (typeof openJob !== 'function') return;
  openJob = function fixedOpenJob(id = null) {
    const form = document.querySelector('#jobForm');
    document.querySelector('#marketJobDetail').classList.add('hidden');
    form.classList.remove('hidden');
    document.querySelector('#drawerEyebrow').textContent = 'JOB RECORD';
    document.querySelector('#drawerTitle').textContent = id ? '岗位详情' : '记录岗位';
    form.reset();
    form.elements.id.value = id || '';
    document.querySelector('#statusSelect').innerHTML = stages.map(([v,n]) => `<option value="${v}">${n}</option>`).join('');
    const resumeSelect = document.querySelector('#jobResumeSelect');
    resumeSelect.innerHTML = '<option value="">未绑定</option>' + state.resumes.map(r=>`<option value="${esc(r.name)}">${esc(r.name)}</option>`).join('');
    const job = state.jobs.find(j => j.id === id);
    if (job) {
      Object.entries(job).forEach(([k,v]) => {
        if (form.elements[k] && typeof v !== 'object') form.elements[k].value = v ?? '';
      });
    } else {
      form.status.value = 'discovered';
      form.statusDate.value = today();
      form.priority.value = 'B';
      if (currentProfile()) form.resumeVersion.value = currentProfile().name;
    }
    renderTimeline(job);
    document.querySelector('#deleteJobBtn').classList.toggle('hidden', !job);
    openDrawer();
  };

  const add = document.querySelector('#addJobBtn');
  if (add) add.onclick = () => openJob();
  const del = document.querySelector('#deleteJobBtn');
  if (del) del.onclick = () => {
    const id = document.querySelector('#jobForm').elements.id.value;
    if (!id) return;
    state.jobs = state.jobs.filter(j=>j.id !== id);
    saveState();
    closeDrawer();
    toast('岗位已删除');
  };
});

function loadPtoScript(src) {
  return new Promise((resolve, reject) => {
    const s = document.createElement('script');
    s.src = `${src}?v=${encodeURIComponent(window.PTO_CONFIG.buildVersion || window.PTO_CONFIG.version)}`;
    s.onload = resolve;
    s.onerror = () => reject(new Error(`failed to load ${src}`));
    document.head.appendChild(s);
  });
}

window.addEventListener('load', async () => {
  try {
    await loadPtoScript('matching-core.js');
    await loadPtoScript('career-taxonomy-v13.js');
    await loadPtoScript('profile-core-v05.js');
    await loadPtoScript('enhancements-v04.js');
    await loadPtoScript('ranking-v06.js');
    await loadPtoScript('ranking-v07.js');
    await loadPtoScript('ranking-v09.js');
    await loadPtoScript('ranking-v13.js');
    await loadPtoScript('ranking-v14.js');
    await loadPtoScript('market-v06.js');
    await loadPtoScript('enhancements-v05.js');
    await loadPtoScript('enhancements-v06.js');
    await loadPtoScript('enhancements-v07.js');
    await loadPtoScript('enhancements-v09.js');
    await loadPtoScript('enhancements-v11.js');
    await loadPtoScript('account-vault.js');
    await loadPtoScript('enhancements-v12.js');
    await loadPtoScript('enhancements-v12-hotfix.js');
    await loadPtoScript('enhancements-v12-security.js');
    await loadPtoScript('enhancements-v12-renderfix.js');
    await loadPtoScript('enhancements-v12-adminfix.js');
    await loadPtoScript('enhancements-v13.js');
    await loadPtoScript('enhancements-v14.js');
    window.PTO_ENHANCEMENTS_READY = true;
    if (typeof loadFeeds === 'function') await loadFeeds();
  } catch (err) {
    window.PTO_ENHANCEMENTS_READY = true;
    console.warn('Path to Offer enhancement load failed; base app remains usable.', err);
  }
});