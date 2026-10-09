// Manual local acceptance only. Requires the disposable fixture and HTTPS proxy
// documented in docs/OAUTH_RELIABILITY_AUDIT.md. Never targets production.
const {chromium} = require(process.env.FM_PLAYWRIGHT_MODULE || 'playwright');
const fs = require('fs'), assert = require('assert/strict');
const origin = 'https://127.0.0.1:8443';
const output = process.argv[2] || '/private/tmp/fm-oauth-browser-results.json';
let browser;
(async()=>{
  browser = await chromium.launch({headless:true, channel:'chrome'});
  const context = await browser.newContext({ignoreHTTPSErrors:true});
  const results=[], blockedReasons=[];
  const record=(name)=>{results.push({name,status:'passed'});console.log('PASS '+name);};
  const page=await context.newPage();
  const cdp=await context.newCDPSession(page); await cdp.send('Network.enable');
  cdp.on('Network.responseReceivedExtraInfo', e=>{
    for(const c of e.blockedCookies||[]) blockedReasons.push(...c.blockedReasons);
  });
  const anonymous=async p=>{await p.getByRole('link',{name:'Continue with Google'}).waitFor();};
  const authenticated=async(p,id)=>{await p.getByText(id+'@example.com',{exact:true}).waitFor();};
  const begin=async p=>{
    await p.goto(origin+'/api/v1/auth/google/login');
    await p.getByRole('heading',{name:'Mock Google — local fixture'}).waitFor();
  };
  const finish=async(p,id)=>{
    await p.getByRole('link',{name:'Sign in as '+id,exact:true}).click();
    await authenticated(p,id);
  };
  await page.goto(origin); await anonymous(page); await begin(page);
  const cookies=await context.cookies(origin+'/api/v1/auth/google/callback');
  const tx=cookies.find(c=>c.name.startsWith('oauth_tx_'));
  assert(tx && tx.secure && tx.httpOnly && tx.sameSite==='Lax' && tx.path==='/api/v1/auth/google/callback');
  record('Secure HttpOnly Lax transaction accepted over local HTTPS');
  await finish(page,'alpha'); record('Fresh login and workspace bootstrap across cross-site mock Google');
  assert(!(await context.cookies(origin+'/api/v1/auth/google/callback')).some(c=>c.name.startsWith('oauth_tx_')));
  record('Successful callback clears its transaction cookie');
  await page.getByRole('button',{name:'Sign out',exact:true}).click(); await anonymous(page);
  await begin(page); await finish(page,'alpha'); record('Login logout login');
  const prior=await context.newPage(); await prior.goto(origin); await authenticated(prior,'alpha');
  const first=await context.newPage(), second=await context.newPage();
  await begin(first); await begin(second);
  assert.equal((await context.cookies(origin+'/api/v1/auth/google/callback')).filter(c=>c.name.startsWith('oauth_tx_')).length,2);
  record('Two simultaneous login tabs retain separate cookies');
  await finish(second,'beta'); await authenticated(prior,'beta');
  record('Account switch reconciles previously authenticated tab through broadcast');
  await finish(first,'gamma'); await authenticated(second,'gamma'); await authenticated(prior,'gamma');
  record('Reverse callback completion changes shared identity to last success');
  await prior.screenshot({path:'/private/tmp/fm-oauth-account-switch.png'});
  const independent=await browser.newContext({ignoreHTTPSErrors:true});
  const other=await independent.newPage(); await begin(other); await finish(other,'alpha');
  await authenticated(prior,'gamma'); record('Independent browser contexts retain independent identities');
  for(const id of ['alpha','beta','gamma']) {await begin(page); await finish(page,id);}
  record('Three consecutive fresh logins');
  await begin(page);
  const callback=await page.getByRole('link',{name:'Sign in as alpha',exact:true}).getAttribute('href');
  await context.clearCookies({name:/^oauth_tx_/});
  await page.goto(callback); await page.getByText('Sign-in could not finish',{exact:true}).waitFor();
  assert(!page.url().includes('code=') && !page.url().includes('state='));
  record('Missing cookie fails closed and recovers to login without callback secrets');
  await page.screenshot({path:'/private/tmp/fm-oauth-callback-recovery.png'});
  await begin(page);
  const replay=await page.getByRole('link',{name:'Sign in as beta',exact:true}).getAttribute('href');
  await finish(page,'beta'); await page.goto(replay);
  await page.getByText('Sign-in could not finish',{exact:true}).waitFor();
  record('Callback replay fails closed');
  await page.goto(origin); await authenticated(page,'beta');
  await begin(first);
  await prior.getByRole('button',{name:'Sign out',exact:true}).click(); await anonymous(prior); await anonymous(second);
  record('Logout reconciles other open tabs');
  await finish(first,'alpha'); await authenticated(prior,'alpha');
  record('Logout preserves another pending OAuth transaction');
  await context.request.post(origin+'/test/expire-session');
  await prior.evaluate(()=>window.dispatchEvent(new Event('focus')));
  await prior.getByText('Session expired',{exact:true}).waitFor(); record('Expired session clears authenticated view on focus');
  await begin(prior); await finish(prior,'gamma'); record('Fresh login after expiry');
  const restricted=await browser.newContext({ignoreHTTPSErrors:true});
  await restricted.addInitScript(()=>{
    Object.defineProperty(window,'localStorage',{get(){throw new Error('blocked');}});
    Object.defineProperty(window,'BroadcastChannel',{value:class{constructor(){throw new Error('blocked');}}});
  });
  const restrictedPage=await restricted.newPage(), restrictedOther=await restricted.newPage();
  await begin(restrictedPage); await finish(restrictedPage,'alpha');
  await restrictedOther.goto(origin); await authenticated(restrictedOther,'alpha');
  await begin(restrictedPage); await finish(restrictedPage,'beta');
  await restrictedOther.evaluate(()=>window.dispatchEvent(new Event('focus'))); await authenticated(restrictedOther,'beta');
  record('Storage and BroadcastChannel restrictions retain cookie authority and focus fallback');
  await begin(restrictedPage); await finish(restrictedPage,'gamma');
  await authenticated(restrictedOther,'gamma');
  record('Periodic fallback detects account switch without storage or broadcast');
  // Simulate network loss before callback reaches backend; cookie stays pending.
  await begin(other); const interrupted=await other.getByRole('link',{name:'Sign in as beta',exact:true}).getAttribute('href');
  await other.route('**/api/v1/auth/google/callback?**', route=>route.abort('internetdisconnected'));
  try{await other.goto(interrupted);}catch{}
  await other.unroute('**/api/v1/auth/google/callback?**');
  await begin(other); await finish(other,'alpha'); record('Lost callback network allows a fresh login without replay');
  await begin(other); await finish(other,'slow'); record('Delayed mock provider callback completes within transaction TTL');
  const htmlContext=await browser.newContext({ignoreHTTPSErrors:true}); const htmlPage=await htmlContext.newPage();
  await htmlPage.route('**/api/v1/auth/me',route=>route.fulfill({status:502,contentType:'text/html',body:'<h1>private proxy payload</h1>'}));
  await htmlPage.goto(origin); await htmlPage.getByText('Server unavailable',{exact:true}).waitFor();
  assert(!(await htmlPage.locator('body').innerText()).includes('private proxy payload'));
  record('HTML proxy failure presents safe connection recovery');
  await htmlPage.screenshot({path:'/private/tmp/fm-oauth-proxy-recovery.png'});
  const payload={browser:'Playwright isolated Google Chrome contexts',topology:'local HTTPS same-origin proxy; cross-site localhost mock Google; disposable SQLite',results,blockedCookieReasons:blockedReasons,transactionCookieMetadata:{secure:tx.secure,httpOnly:tx.httpOnly,sameSite:tx.sameSite,path:tx.path},liveGoogle:false,production:false};
  fs.writeFileSync(output,JSON.stringify(payload,null,2)+'\n');
  await browser.close();console.log(results.length+' local browser checks passed; blocked cookie reasons: '+blockedReasons.length);
})().catch(async e=>{console.error('Local browser acceptance failed: '+e.name);await browser?.close();process.exitCode=1;});
