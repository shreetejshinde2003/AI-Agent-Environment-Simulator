// Disposable production-build acceptance server. Local fixture backend only.
import {createServer, request} from 'node:http';
import {readFile} from 'node:fs/promises';
import {resolve, extname} from 'node:path';
import {rewriteDestination} from './productionRouting.js';
const root=resolve(import.meta.dirname,'../../dist');
const config=JSON.parse(await readFile(resolve(root,'../vercel.json'),'utf8'));
const server=createServer(async(req,res)=>{
  const url=new URL(req.url,'http://127.0.0.1:5179');
  const destination=rewriteDestination(config,url.pathname);
  if (process.env.FM_FIXTURE_WORKSPACE_HTML === '1' && url.pathname === '/api/v1/workspaces') {
    res.writeHead(200, {'Content-Type':'text/html'});res.end('<!doctype html><title>Unexpected SPA fixture</title>');return;
  }
  if(destination?.startsWith('https://')||url.pathname.startsWith('/_local_browser_fixture/')) {
    const upstream=request({hostname:'127.0.0.1',port:8019,path:url.pathname+url.search,method:req.method,headers:req.headers},response=>{
      res.writeHead(response.statusCode,response.headers);response.pipe(res);
    });
    upstream.on('error',()=>{res.writeHead(502,{'Content-Type':'text/plain'});res.end('Local fixture unavailable');});req.pipe(upstream);return;
  }
  const file=resolve(root,'.'+url.pathname);
  if(!file.startsWith(root+'/')&&file!==root){res.writeHead(400);res.end();return;}
  const types={'.js':'text/javascript','.css':'text/css','.html':'text/html','.svg':'image/svg+xml'};
  try{const data=await readFile(file);res.writeHead(200,{'Content-Type':types[extname(file)]||'application/octet-stream'});res.end(data);}
  catch{if(destination==='/index.html'){res.writeHead(200,{'Content-Type':'text/html'});res.end(await readFile(resolve(root,'index.html')));}else{res.writeHead(404);res.end();}}
});
server.listen(5179,'127.0.0.1',()=>process.stdout.write('Local production proxy ready on 5179\n'));
process.on('SIGINT',()=>server.close(()=>process.exit(0)));
