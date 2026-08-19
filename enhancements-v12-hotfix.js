(function(){
  'use strict';
  const source=document.querySelector('#openSourcePanel');
  if(source&&typeof showSources==='function')source.onclick=event=>{event.preventDefault();showSources();};
  const inspect=document.querySelector('#inspectProfileBtn');
  if(inspect&&typeof inspectProfile==='function')inspect.onclick=inspectProfile;
  const account=document.querySelector('#githubLoginBtn');
  if(account&&window.PTO_ACCOUNT_UI?.open)account.onclick=window.PTO_ACCOUNT_UI.open;
})();
