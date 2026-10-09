// Loopback-only acceptance proxy; not application/deployment configuration.
// Usage: node backend/scripts/oauth_local_https_proxy.cjs KEY.pem CERT.pem
const fs=require('fs'), http=require('http'), https=require('https');
if(process.argv.length!==4) throw new Error('Supply local fixture TLS key and certificate paths');
https.createServer({key:fs.readFileSync(process.argv[2]),cert:fs.readFileSync(process.argv[3])},(req,res)=>{
  const api=req.url.startsWith('/api/')||req.url.startsWith('/test/')||req.url==='/health';
  const target=http.request({hostname:'127.0.0.1',port:api?8027:5178,path:req.url,method:req.method,
    headers:{...req.headers,host:api?'127.0.0.1:8027':'127.0.0.1:5178'}},up=>{
    // Node preserves separate Set-Cookie headers from the backend response.
    res.writeHead(up.statusCode,up.headers);up.pipe(res);
  });
  target.on('error',()=>{res.writeHead(502,{'Content-Type':'text/html'});res.end('<h1>Local proxy unavailable</h1>');});
  req.pipe(target);
}).listen(8443,'127.0.0.1');
