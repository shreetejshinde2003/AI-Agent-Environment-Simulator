import {after, before, test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createServer} from 'vite';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {rewriteDestination} from './fixtures/productionRouting.js';
const config=JSON.parse(await readFile(new URL('../vercel.json',import.meta.url)));
let server, auth, workspaceClient, apiClient, parser, resolveApiBase, Topbar;
before(async()=>{
  server=await createServer({root:new URL('../',import.meta.url).pathname,envDir:false,
    define:{'import.meta.env.DEV':'false','import.meta.env.VITE_API_BASE_URL':JSON.stringify('https://backend.invalid')},
    server:{middlewareMode:true,hmr:false,ws:false,watch:null},logLevel:'error'});
  auth=await server.ssrLoadModule('/src/services/authClient.js');
  ({workspaceClient}=await server.ssrLoadModule('/src/services/workspaceClient.js'));
  ({apiClient}=await server.ssrLoadModule('/src/services/apiClient.js'));
  ({parseApiResponse:parser}=await server.ssrLoadModule('/src/services/apiResponse.js'));
  ({resolveApiBase}=await server.ssrLoadModule('/src/services/apiConfig.js'));
  ({default:Topbar}=await server.ssrLoadModule('/src/layout/Topbar.jsx'));
});
after(async()=>{await server?.close();});
for(const path of ['/api/v1/auth/me','/api/v1/workspaces','/api/v1/workspaces/organizations','/api/v1/simulations','/api/v1/research/example','/api/v1/experiments/research','/api/v1/hiring/requirements','/api/v1/unknown']) {
  test(`${path} reaches backend`,()=>assert.equal(new URL(rewriteDestination(config,path)).pathname,path));
}
for(const path of ['/','/live','/organizations','/research/report']) test(`${path} retains SPA`,()=>assert.equal(rewriteDestination(config,path),'/index.html'));
test('API outside versioned route cannot hit SPA',()=>assert.equal(rewriteDestination(config,'/api/unknown'),null));
test('health reaches backend',()=>assert.equal(new URL(rewriteDestination(config,'/health')).pathname,'/health'));
test('OAuth login and callback retain API proxy and disable caching',()=>{
  for(const path of ['/api/v1/auth/google/login','/api/v1/auth/google/callback']) {
    assert.equal(new URL(rewriteDestination(config,path)).pathname,path);
  }
  const headers=config.headers.find(rule=>rule.source==='/api/v1/auth/:path*').headers;
  assert.ok(headers.some(header=>header.key==='Cache-Control'&&header.value==='no-store, private'));
  assert.ok(headers.some(header=>header.key==='Vercel-CDN-Cache-Control'&&header.value==='no-store'));
});
test('local resolution retains configured and default backend; production ignores override',()=>{
  assert.equal(resolveApiBase({DEV:true}),'http://localhost:8000');
  assert.equal(resolveApiBase({DEV:true,VITE_API_BASE_URL:'http://127.0.0.1:8019/'}),'http://127.0.0.1:8019');
  assert.equal(resolveApiBase({DEV:false,VITE_API_BASE_URL:'https://backend.invalid'}),'');
});
test('production auth, workspace, general, HR and research clients share relative REST with cookies',async()=>{
  const original=globalThis.fetch,calls=[];
  globalThis.fetch=async(url,options)=>{calls.push({url,options});return Response.json({authenticated:true,user:{id:'fixture'}});};
  try {
    await auth.getCurrentUser();await auth.logout();await workspaceClient.list();await apiClient.getTasks('WS-fixture');
    await apiClient.getHiringRecords('requirements','WS-fixture');await apiClient.getResearchExperiments('WS-fixture');
    assert.equal(auth.AUTH_LOGIN_URL,'/api/v1/auth/google/login');assert.equal(calls.length,6);
    assert.ok(calls.every(c=>c.url.startsWith('/api/v1/')&&c.options.credentials==='include'));
  } finally {globalThis.fetch=original;}
});
test('all JSON clients reject HTML success and failure with safe metadata',async()=>{
  const original=globalThis.fetch;
  try {
    for(const status of [200,502]) {
      globalThis.fetch=async()=>new Response('<!doctype html>SECRET',{status,headers:{'Content-Type':'text/html'}});
      for(const call of [auth.getCurrentUser,auth.logout,workspaceClient.list,()=>apiClient.getTasks('WS-fixture')]) {
        await assert.rejects(call,error=>error.message==='API returned an unexpected non-JSON response.'&&error.status===status&&error.contentType==='text/html'&&error.requestPath.startsWith('/api/v1/')&&!JSON.stringify(error).includes('SECRET'));
      }
    }
  } finally {globalThis.fetch=original;}
});
test('legitimate backend JSON errors retain message, status and code',async()=>{
  await assert.rejects(parser(Response.json({detail:{code:'revision_conflict',message:'Reload records'}},{status:409}),'/api/v1/tasks'),error=>error.message==='Reload records'&&error.status===409&&error.code==='revision_conflict');
});
test('invalid JSON, missing type and text become controlled errors without query values',async()=>{
  for(const response of [new Response('{broken',{headers:{'Content-Type':'application/json'}}),new Response('text'),new Response(new Uint8Array([1]))]) {
    await assert.rejects(parser(response,'/api/v1/tasks?secret=redacted'),error=>error.code==='unexpected_api_response'&&error.requestPath==='/api/v1/tasks');
  }
  assert.deepEqual(await parser(new Response('{}',{headers:{'Content-Type':'application/problem+json; charset=utf-8'}}),'/api/v1/tasks'),{});
});
test('anonymous auth and empty logout preserve 401 and 204 behavior',async()=>{
  const original=globalThis.fetch;
  try {
    globalThis.fetch=async()=>Response.json({detail:'Sign in'},{status:401});assert.equal(await auth.getCurrentUser(),null);
    globalThis.fetch=async()=>new Response(null,{status:204});await auth.logout();
  } finally {globalThis.fetch=original;}
});
test('topbar separates backend, workspace and live events on bootstrap failure',()=>{
  const html=renderToStaticMarkup(createElement(Topbar,{backendStatus:'connected',workspaceStatus:'error',socketStatus:'disconnected'}));
  assert.match(html,/Backend reachable/);assert.match(html,/Workspace unavailable/);assert.match(html,/Live events offline/);assert.doesNotMatch(html,/>Connected<|>Live</);
});
test('HTML 401 cannot silently masquerade as an anonymous session',async()=>{
  const original=globalThis.fetch;
  try {
    globalThis.fetch=async()=>new Response('<html>',{status:401,headers:{'Content-Type':'text/html'}});
    await assert.rejects(auth.getCurrentUser,/unexpected non-JSON response/);
  } finally {globalThis.fetch=original;}
});
test('export refuses HTML and preserves legitimate JSON backend errors',async()=>{
  const original=globalThis.fetch;
  try {
    globalThis.fetch=async()=>new Response('<html>',{headers:{'Content-Type':'text/html'}});
    await assert.rejects(apiClient.exportRun('T-fixture','json','WS-fixture'),/unexpected non-JSON response/);
    await assert.rejects(apiClient.exportRun('T-fixture','txt','WS-fixture'),/unexpected response type/);
    globalThis.fetch=async()=>Response.json({detail:'Export is available after the simulation finishes'},{status:409});
    await assert.rejects(apiClient.exportRun('T-fixture','json','WS-fixture'),/after the simulation finishes/);
  } finally {globalThis.fetch=original;}
});

test('unparseable creation acknowledgement preserves unknown outcome for retry safety',async()=>{
  const original=globalThis.fetch;
  try {
    globalThis.fetch=async()=>new Response('<html>',{headers:{'Content-Type':'text/html'}});
    await assert.rejects(apiClient.createTask({directive:'fixture'},'WS-fixture'),error=>error.code==='unexpected_api_response'&&error.outcomeUnknown===true&&error.status===200);
  } finally {globalThis.fetch=original;}
});
