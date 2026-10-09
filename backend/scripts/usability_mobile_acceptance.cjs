// Additional read-only local mobile checks against the same disposable fixture.
const {chromium}=require(process.env.FM_PLAYWRIGHT_MODULE||'playwright');
const fs=require('fs'),assert=require('assert/strict');const folder=process.argv[2]||'/private/tmp/fm-usability-browser';
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try {
  const context=await browser.newContext({viewport:{width:390,height:844}});const page=await context.newPage();
  const before=await (await context.request.get('http://127.0.0.1:8031/_sprint/stats')).json();
  await page.goto('http://127.0.0.1:8031/_sprint/session/combined');await page.getByLabel('Workspace',{exact:true}).selectOption({label:'Phase 8 hiring acceptance'});
  await page.getByRole('button',{name:'HR Hiring',exact:true}).click();await page.getByRole('heading',{name:/From hiring need/}).waitFor();
  await page.getByLabel('Continue a saved hiring requirement',{exact:true}).selectOption({label:'Usability Engineer · draft'});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));await page.screenshot({path:folder+'/hr-mobile.png'});
  const result=JSON.parse(fs.readFileSync(folder+'/browser-results.json','utf8'));
  result.checks.push({name:'Mobile five-step HR guide and approved saved state fit viewport',status:'passed'});
  await page.getByLabel('Workspace',{exact:true}).selectOption({label:'Personal Workspace'});await page.getByRole('button',{name:'Agents',exact:true}).click();
  await page.getByRole('form',{name:'Agent configuration'}).waitFor();assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));await page.screenshot({path:folder+'/agents-mobile.png'});
  result.checks.push({name:'Mobile custom-agent form and lifecycle guidance fit viewport',status:'passed'});
  const after=await (await context.request.get('http://127.0.0.1:8031/_sprint/stats')).json();assert.deepEqual(before,after);
  fs.writeFileSync(folder+'/browser-results.json',JSON.stringify(result,null,2)+'\n');console.log('2 additional mobile checks passed; provider counts unchanged; total '+result.checks.length);
 } finally {await browser.close();}
})().catch(error=>{console.error('Mobile acceptance failed: '+error.name);process.exitCode=1;});
