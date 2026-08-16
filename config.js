window.PTO_CONFIG = Object.freeze({
  version: '0.5.0',
  jobsFeed: './data/jobs.json',
  sourceStatusFeed: './data/source_status.json',
  interviewAssetsRepo: 'https://github.com/MLliu6/26-27-interview',
  // Optional. A production GitHub login needs a server-side token exchange.
  // Point this to your own OAuth callback/proxy when one is provisioned.
  githubOAuthProxy: '',
  githubClientId: '',
  githubOAuthScopes: 'read:user user:email',
});

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

// Matching/profile logic is layered over the stable application shell so the
// tracker remains usable even if an enhancement bundle fails to load.
window.addEventListener('load', async () => {
  try {
    await loadPtoScript('matching-core.js');
    await loadPtoScript('profile-core-v05.js');
    await loadPtoScript('enhancements-v04.js');
    await loadPtoScript('enhancements-v05.js');
  } catch (err) {
    console.warn('Path to Offer enhancement load failed; base app remains usable.', err);
  }
});
