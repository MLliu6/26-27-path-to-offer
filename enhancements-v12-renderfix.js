(function(){
  'use strict';
  if(!window.PTO_SECURE_ACCOUNT_V2)return;

  // v1.2 overrides pipelineCard after the base app has already rendered once.
  // Re-render immediately so existing saved jobs use company initials instead
  // of the stale priority-letter chip from the pre-v1.2 DOM.
  if(typeof renderAll==='function')renderAll();

  const sourceButton=document.querySelector('#openSourcePanel');
  if(sourceButton&&typeof window.PTO_SECURE_ACCOUNT_V2.showSources==='function'){
    sourceButton.onclick=window.PTO_SECURE_ACCOUNT_V2.showSources;
  }

  window.PTO_V12_RENDERFIX_READY=true;
})();
