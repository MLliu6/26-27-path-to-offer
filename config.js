window.PTO_CONFIG = Object.freeze({
  version: '0.7.0',
  jobsFeed: './data/jobs.json',
  sourceStatusFeed: './data/source_status.json',
  interviewAssetsRepo: 'https://github.com/MLliu6/26-27-interview',
  // Optional. A production GitHub login needs a server-side token exchange.
  // Point this to your own OAuth callback/proxy when one is provisioned.
  githubOAuthProxy: '',
  githubClientId: '',
  githubOAuthScopes: 'read:user user:email',
});

// The stable shell calls loadFeeds() as soon as app.js executes. Gate the first
// jobs-feed fetch so enhancement layers can install the indexed/bounded renderer
// before the real catalogue is loaded.
window.PTO_ENHANCEMENTS_READY = false;
const PTO_NATIVE_FETCH = window.fetch.bind(window);
window.fetch = function ptoBootstrapFetch(input, init) {
  const url = typeof input === 'string' ? input : (input && input.url) || '';
  const jobsPath = String(window.PTO_CONFIG.jobsFeed || './data/jobs.json').replace(/^\.\//, '');
  if (!window.PTO_ENHANCEMENTS_READY && jobsPath && String(url).includes(jobsPath)) {
    return Promise.resolve(new Response(JSON.stringify({schema_version:4, generated_at:null, jobs:[]}), {
      status: 200,
      headers: {'Content-Type':'application/json'}
    }));
  }
  return PTO_NATIVE_FETCH(input, init);
};

// Compatibility guard for named-form access across browsers.
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
    resumeSelect.innerHTML = '<option value="">未绑定</option>' + state.resumes.map(r => `<option value="${esc(r.name)}">${esc(r.name)}</option>`).join('');
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
    state.jobs = state.jobs.filter(j => j.id !== id);
    saveState();
    closeDrawer();
    toast('岗位已删除');
  };
});

function loadPtoScript(src) {
  return new Promise((resolve, reject) => {
    const s = document.createElement('script');
    s.src = `${src}?v=${encodeURIComponent(window.PTO_CONFIG.version)}`;
    s.onload = resolve;
    s.onerror = () => reject(new Error(`failed to load ${src}`));
    document.head.appendChild(s);
  });
}

window.addEventListener('load', async () => {
  try {
    await loadPtoScript('matching-core.js');
    await loadPtoScript('profile-core-v05.js');
    await loadPtoScript('enhancements-v04.js');
    await loadPtoScript('ranking-v06.js');
    await loadPtoScript('matching-v07.js');
    await loadPtoScript('market-v06.js');
    await loadPtoScript('enhancements-v05.js');
    await loadPtoScript('enhancements-v06.js');
    // Loaded last because it replaces the cross-cutting user journey: indexed
    // retrieval, China/campus defaults, explicit detail/apply actions and the
    // end-to-end resume → recommendation → official application flow.
    await loadPtoScript('experience-v07.js');
    await loadPtoScript('performance-v07.js');
    window.PTO_ENHANCEMENTS_READY = true;
    if (typeof loadFeeds === 'function') await loadFeeds();
  } catch (err) {
    window.PTO_ENHANCEMENTS_READY = true;
    console.warn('Path to Offer enhancement load failed; base app remains usable.', err);
  }
});
