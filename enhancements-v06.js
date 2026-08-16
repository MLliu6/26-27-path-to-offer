(function(){
  'use strict';
  if(typeof palettes==='undefined')return;

  const APPEARANCE_KEY='pathToOffer.appearance';
  const media=window.matchMedia('(prefers-color-scheme: dark)');
  let chosenAppearance=localStorage.getItem(APPEARANCE_KEY)||'light';
  const baseApplyTheme=applyTheme;

  function hexToRgba(hex,a){
    const m=String(hex||'').replace('#','');
    if(!/^[0-9a-f]{6}$/i.test(m))return `rgba(151,180,167,${a})`;
    const n=parseInt(m,16);return `rgba(${(n>>16)&255},${(n>>8)&255},${n&255},${a})`;
  }
  function activePalette(){
    const i=Number(localStorage.getItem(THEME_KEY)||0);
    return palettes[Number.isFinite(i)&&palettes[i]?i:0];
  }
  function actualAppearance(mode=chosenAppearance){return mode==='system'?(media.matches?'dark':'light'):mode;}

  function applyAppearance(mode,save=true){
    if(!['light','dark','system'].includes(mode))mode='light';
    chosenAppearance=mode;
    if(save)localStorage.setItem(APPEARANCE_KEY,mode);
    const actual=actualAppearance(mode);const root=document.documentElement;
    root.dataset.appearance=actual;root.dataset.appearanceChoice=mode;
    root.style.colorScheme=actual;
    const meta=document.querySelector('meta[name="theme-color"]');
    if(meta)meta.content=actual==='dark'?'#101512':'#f7f7f3';
    applyTheme(Number(localStorage.getItem(THEME_KEY)||0));
    document.querySelectorAll('[data-appearance-choice]').forEach(b=>b.classList.toggle('active',b.dataset.appearanceChoice===mode));
  }

  applyTheme=function(i){
    baseApplyTheme(i);
    const p=palettes[i]||palettes[0];const root=document.documentElement;
    root.style.setProperty('--accent-base',p[1]);
    if(actualAppearance()==='dark'){
      // Dark mode is not a literal inverse: the accent becomes a luminous
      // structural color while backgrounds remain quiet neutral-charcoal.
      root.style.setProperty('--accent',p[1]);
      root.style.setProperty('--accent-strong',p[1]);
      root.style.setProperty('--accent-soft',hexToRgba(p[1],.15));
      root.style.setProperty('--accent-wash',hexToRgba(p[1],.075));
    }else{
      root.style.setProperty('--accent-wash',hexToRgba(p[1],.055));
    }
    repairSwatches(i);
  };

  function injectStyles(){
    if(document.querySelector('#ptoV06ThemeStyle'))return;
    const style=document.createElement('style');style.id='ptoV06ThemeStyle';style.textContent=`
      .appearance-control{display:grid;grid-template-columns:repeat(3,1fr);gap:3px;background:var(--surface-2);border:1px solid var(--line);border-radius:10px;padding:3px;margin:2px 0 12px}
      .appearance-control button{border:0;border-radius:7px;background:transparent;color:var(--muted);font-size:10px;padding:6px 3px}.appearance-control button.active{background:var(--surface);color:var(--text);box-shadow:0 1px 4px rgba(0,0,0,.08)}
      .swatches{grid-template-columns:repeat(5,30px)!important;justify-content:start}.swatch{position:relative;width:30px!important;height:30px!important;border:2px solid var(--surface)!important;box-shadow:0 0 0 1px var(--line),inset 0 0 0 1px rgba(255,255,255,.16)!important;transition:transform .16s ease,box-shadow .16s ease!important}.swatch:hover{transform:translateY(-2px) scale(1.05)}.swatch.selected:after{content:'✓';position:absolute;inset:0;display:grid;place-items:center;color:white;font-size:13px;font-weight:800;text-shadow:0 1px 3px rgba(0,0,0,.45)}
      .theme-popover{width:220px!important}.theme-caption{display:flex;justify-content:space-between;gap:8px;align-items:center;margin-top:9px!important}.theme-caption b{color:var(--text);font-weight:600}
      html[data-appearance="dark"]{--bg:#101512;--surface:#171d1a;--surface-2:#202823;--text:#edf2ee;--muted:#99a69e;--line:#2c3630;--danger:#df9999;--shadow:0 18px 46px rgba(0,0,0,.32)}
      html[data-appearance="dark"] body{background:radial-gradient(900px 480px at 12% -5%,var(--accent-wash),transparent 62%),var(--bg);color:var(--text)}
      html[data-appearance="dark"] .topbar{background:color-mix(in srgb,var(--bg) 86%,var(--accent) 14%);border-bottom-color:var(--line)}
      html[data-appearance="dark"] .main-nav,html[data-appearance="dark"] .view-switch,html[data-appearance="dark"] .segmented{background:#202722}
      html[data-appearance="dark"] .nav-item.active,html[data-appearance="dark"] .seg.active{background:color-mix(in srgb,var(--surface) 78%,var(--accent) 22%);color:var(--text);box-shadow:none}
      html[data-appearance="dark"] .btn,html[data-appearance="dark"] .icon-btn,html[data-appearance="dark"] .view-icon,html[data-appearance="dark"] .panel,html[data-appearance="dark"] .market-card,html[data-appearance="dark"] .metric,html[data-appearance="dark"] .profile-strip,html[data-appearance="dark"] .intel-card,html[data-appearance="dark"] .review-card,html[data-appearance="dark"] .theme-popover,html[data-appearance="dark"] .modal,html[data-appearance="dark"] .drawer,html[data-appearance="dark"] .table-wrap{background:var(--surface);border-color:var(--line)}
      html[data-appearance="dark"] .btn.ghost{background:#1b221e}html[data-appearance="dark"] .btn.primary{background:var(--accent);border-color:var(--accent);color:#0d1410;font-weight:700}
      html[data-appearance="dark"] .resume-onboarding{background:linear-gradient(130deg,color-mix(in srgb,var(--surface) 88%,var(--accent) 12%),var(--surface));border-color:#34423a}
      html[data-appearance="dark"] .privacy-note,html[data-appearance="dark"] .match-rail{background:color-mix(in srgb,var(--surface) 90%,var(--accent) 10%);border-color:var(--line)}
      html[data-appearance="dark"] .search-wrap,html[data-appearance="dark"] .search,html[data-appearance="dark"] select,html[data-appearance="dark"] input,html[data-appearance="dark"] textarea{background:#141a17!important;color:var(--text);border-color:var(--line)!important}
      html[data-appearance="dark"] input::placeholder,html[data-appearance="dark"] textarea::placeholder{color:#718078}
      html[data-appearance="dark"] .kanban-col{background:#141a17;border-color:var(--line)}html[data-appearance="dark"] .job-card{background:#1a211d;border-color:var(--line)}
      html[data-appearance="dark"] .job-table th{background:#1d2520;color:var(--muted)}html[data-appearance="dark"] .job-table tbody tr:hover{background:var(--accent-wash)}
      html[data-appearance="dark"] .job-facts span,html[data-appearance="dark"] .source-tag,html[data-appearance="dark"] .role-cloud span,html[data-appearance="dark"] .skill-cloud-v4 span,html[data-appearance="dark"] .section-chip{background:#1c241f!important;border-color:#344038!important;color:var(--muted)!important}
      html[data-appearance="dark"] .signal-chip,html[data-appearance="dark"] .match-reasons span,html[data-appearance="dark"] .signal-cloud span,html[data-appearance="dark"] .reason-grid span,html[data-appearance="dark"] .priority,html[data-appearance="dark"] .quality-badge{background:var(--accent-soft);color:var(--accent)}
      html[data-appearance="dark"] .market-card:hover{border-color:color-mix(in srgb,var(--accent) 55%,var(--line));box-shadow:0 18px 44px rgba(0,0,0,.28),0 0 0 1px var(--accent-wash)}
      html[data-appearance="dark"] .match-score{background:#121815;border-color:var(--line)}html[data-appearance="dark"] .match-score.high{background:var(--accent-soft);color:var(--accent)}
      html[data-appearance="dark"] .drawer-head{background:rgba(23,29,26,.94);border-color:var(--line)}html[data-appearance="dark"] .timeline-box,html[data-appearance="dark"] .detail-facts div,html[data-appearance="dark"] .profile-summary,html[data-appearance="dark"] .profile-inspector .section-audit{background:var(--surface-2)}
      html[data-appearance="dark"] .modal-backdrop,html[data-appearance="dark"] .drawer-backdrop{background:rgba(3,7,5,.64)}
      html[data-appearance="dark"] .market-empty,html[data-appearance="dark"] .large-empty{background:#121815;border-color:#344038}html[data-appearance="dark"] .funnel-track{background:#263029}
      html[data-appearance="dark"] .company-logo,html[data-appearance="dark"] .detail-score{background:var(--accent-soft);color:var(--accent)}
      html[data-appearance="dark"] .eyebrow,html[data-appearance="dark"] .text-btn,html[data-appearance="dark"] .market-table td:nth-child(1) strong{color:var(--accent)!important}
      html[data-appearance="dark"] ::selection{background:var(--accent);color:#0e1511}
      @media(max-width:760px){html[data-appearance="dark"] .main-nav{background:rgba(25,32,28,.95)}}
    `;document.head.appendChild(style);
  }

  function repairSwatches(selectedIndex){
    const wrap=document.querySelector('#swatches');if(!wrap)return;
    const saved=Number.isFinite(selectedIndex)?selectedIndex:Number(localStorage.getItem(THEME_KEY)||0);
    [...wrap.querySelectorAll('.swatch')].forEach((b,i)=>{
      const p=palettes[i]||palettes[0];
      // v0.2 accidentally set --sw to the palette *name* ("Sage") instead of
      // its color value.  Set both a real background and the variable so the
      // color is visible even if one path is overridden by browser CSS.
      b.style.setProperty('--sw',p[1]);b.style.backgroundColor=p[1];
      b.classList.toggle('selected',i===saved);b.setAttribute('aria-label',`主题色 ${p[0]}`);b.title=p[0];
      b.onclick=()=>{applyTheme(i);localStorage.setItem(THEME_KEY,String(i));repairSwatches(i);const cap=document.querySelector('#activeThemeName');if(cap)cap.textContent=p[0];};
    });
    const cap=document.querySelector('#activeThemeName');if(cap)cap.textContent=(palettes[saved]||palettes[0])[0];
  }

  function enhancePopover(){
    const pop=document.querySelector('#themePopover');const sw=document.querySelector('#swatches');if(!pop||!sw)return;
    if(!pop.querySelector('.appearance-control')){
      const control=document.createElement('div');control.className='appearance-control';
      control.innerHTML='<button data-appearance-choice="light">浅色</button><button data-appearance-choice="dark">深色</button><button data-appearance-choice="system">跟随系统</button>';
      sw.insertAdjacentElement('beforebegin',control);
      control.querySelectorAll('button').forEach(b=>b.onclick=e=>{e.stopPropagation();applyAppearance(b.dataset.appearanceChoice,true);});
    }
    let small=pop.querySelector('small');if(small){small.className='theme-caption';small.innerHTML='Accent <b id="activeThemeName"></b> · 自动保存';}
    repairSwatches();
  }

  function enhanceCoverage(){
    const chip=document.querySelector('#coverageChip');if(!chip)return;
    const count=Number(sourceStatus?.catalog_count||marketJobs.length||0);const target=Number(sourceStatus?.catalog_target||10000);
    chip.textContent=count>=target?`岗位池 ${count.toLocaleString()} · federated`:`岗位池 ${count.toLocaleString()} / 目标 ${target.toLocaleString()}`;
    chip.title='这里只显示真实抓取到并归一化后的岗位数量；不会用虚构记录填充。';
  }

  const oldRenderDiscovery=typeof renderDiscovery==='function'?renderDiscovery:null;
  if(oldRenderDiscovery){renderDiscovery=function(){oldRenderDiscovery();enhanceCoverage();};}

  injectStyles();enhancePopover();applyAppearance(chosenAppearance,false);enhanceCoverage();
  media.addEventListener?.('change',()=>{if(chosenAppearance==='system')applyAppearance('system',false);});
})();
