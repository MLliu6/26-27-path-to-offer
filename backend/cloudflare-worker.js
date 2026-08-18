// Path to Offer encrypted-vault sync endpoint for Cloudflare Workers + KV.
//
// The browser performs PBKDF2 + AES-GCM encryption. This worker stores only the
// opaque envelope and a high-entropy bearer derived client-side from the account
// password. It never receives plaintext resumes, job records or interview notes.
//
// Required binding: PTO_VAULTS (KV namespace)
// Optional variable: PTO_ALLOWED_ORIGINS, comma-separated origins.

const MAX_BYTES = 2_500_000;
const ID_RE = /^[a-f0-9]{32}$/;

function cors(request, env) {
  const origin = request.headers.get('Origin') || '';
  const configured = String(env.PTO_ALLOWED_ORIGINS || '').split(',').map(x => x.trim()).filter(Boolean);
  const allowed = configured.length ? configured.includes(origin) : true;
  return {
    'Access-Control-Allow-Origin': allowed ? (origin || '*') : 'null',
    'Access-Control-Allow-Methods': 'GET,PUT,OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type,X-PTO-Auth',
    'Access-Control-Max-Age': '86400',
    'Vary': 'Origin',
  };
}
function json(request, env, body, status = 200) {
  return new Response(JSON.stringify(body), {status, headers:{'Content-Type':'application/json; charset=utf-8',...cors(request,env)}});
}
async function tokenHash(token) {
  const bytes = new TextEncoder().encode(String(token || ''));
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  return [...new Uint8Array(digest)].map(x => x.toString(16).padStart(2,'0')).join('');
}
function constantTimeEqual(a,b) {
  const left=String(a||''),right=String(b||'');let diff=left.length^right.length;
  for(let i=0;i<Math.max(left.length,right.length);i++)diff|=(left.charCodeAt(i)||0)^(right.charCodeAt(i)||0);
  return diff===0;
}
function validEnvelope(value,id) {
  return value&&typeof value==='object'&&value.version===1&&value.accountId===id&&
    typeof value.salt==='string'&&value.salt.length>=16&&value.verifier&&value.state&&
    typeof value.verifier.iv==='string'&&typeof value.verifier.cipher==='string'&&
    typeof value.state.iv==='string'&&typeof value.state.cipher==='string';
}

export default {
  async fetch(request, env) {
    if (request.method === 'OPTIONS') return new Response(null,{status:204,headers:cors(request,env)});
    const url = new URL(request.url);
    const match = url.pathname.match(/^\/v1\/vault\/([a-f0-9]{32})$/);
    if (!match) return json(request,env,{error:'not_found'},404);
    const id = match[1];
    if (!ID_RE.test(id)) return json(request,env,{error:'invalid_account_id'},400);
    const token = request.headers.get('X-PTO-Auth') || '';
    if (token.length < 32 || token.length > 256) return json(request,env,{error:'unauthorized'},401);
    const hash = await tokenHash(token);
    const key = `vault:${id}`;
    const current = await env.PTO_VAULTS.get(key,{type:'json'});

    if (request.method === 'GET') {
      if (!current) return json(request,env,{error:'not_found'},404);
      if (!constantTimeEqual(current.authHash,hash)) return json(request,env,{error:'unauthorized'},401);
      return json(request,env,current.envelope);
    }
    if (request.method === 'PUT') {
      const length = Number(request.headers.get('Content-Length') || 0);
      if (length > MAX_BYTES) return json(request,env,{error:'payload_too_large'},413);
      let envelope;
      try { envelope = await request.json(); } catch (_) { return json(request,env,{error:'invalid_json'},400); }
      if (!validEnvelope(envelope,id)) return json(request,env,{error:'invalid_envelope'},400);
      const encoded = JSON.stringify(envelope);
      if (new TextEncoder().encode(encoded).length > MAX_BYTES) return json(request,env,{error:'payload_too_large'},413);
      if (current && !constantTimeEqual(current.authHash,hash)) return json(request,env,{error:'unauthorized'},401);
      await env.PTO_VAULTS.put(key,JSON.stringify({authHash:hash,envelope,updatedAt:new Date().toISOString()}));
      return json(request,env,{ok:true,updatedAt:envelope.updatedAt||null});
    }
    return json(request,env,{error:'method_not_allowed'},405);
  }
};
