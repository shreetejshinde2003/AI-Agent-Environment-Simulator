// Local-only follow-up: dependency display must refresh after real admission.
const {chromium}=require(process.env.FM_PLAYWRIGHT_MODULE||'playwright');
const fs=require('fs'),assert=require('assert/strict');const folder=process.argv[2]||'/private/tmp/fm-usability-browser';
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try {
  const context=await browser.newContext();const page=await context.newPage();
  await page.goto('http://127.0.0.1:8031/_sprint/session/recruiter');await page.getByLabel('Workspace',{exact:true}).selectOption({label:'Usability acceptance team'});
  await page.getByRole('button',{name:'Agents',exact:true}).click();await page.getByRole('button',{name:/Usability text assistant/}).click();
  await page.getByText('Archive or permanent removal',{exact:true}).click();await page.getByText(/1 retained run\(s\)/).waitFor();
  await page.getByRole('form',{name:'Run saved agent'}).getByLabel('Input text',{exact:true}).fill('Dependency-refresh acceptance: summarize these notes.');
  await page.getByRole('button',{name:'Run agent',exact:true}).click();await page.getByText(/2 retained run\(s\)/).waitFor();
  assert(await page.getByRole('button',{name:'Delete permanently',exact:true}).isDisabled());
  const result=JSON.parse(fs.readFileSync(folder+'/browser-results.json','utf8'));
  result.checks.push({name:'Agent dependency report refreshes after a newly persisted run without enabling deletion',status:'passed'});
  result.provider=await (await context.request.get('http://127.0.0.1:8031/_sprint/stats')).json();
  fs.writeFileSync(folder+'/browser-results.json',JSON.stringify(result,null,2)+'\n');console.log('Agent dependency refresh passed; total '+result.checks.length);
 } finally {await browser.close();}
})().catch(error=>{console.error('Dependency refresh acceptance failed: '+error.name);process.exitCode=1;});
