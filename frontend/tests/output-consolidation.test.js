import {before,after,test} from "node:test";
import assert from "node:assert/strict";
import {createElement} from "react";
import {renderToStaticMarkup} from "react-dom/server";
import {createServer} from "vite";
import {fileURLToPath} from "node:url";
import {presentOutput} from "../src/utils/outputPresentation.js";
import {canDeleteItem} from "../src/utils/recycleBin.js";
let server,OutputViewer,MarkdownOutput,Sidebar;
before(async()=>{
  server=await createServer({root:fileURLToPath(new URL("../",import.meta.url)),envDir:false,server:{middlewareMode:true,hmr:false,ws:false,watch:null},logLevel:"error"});
  ({default:OutputViewer,MarkdownOutput}=await server.ssrLoadModule("/src/components/dashboard/OutputViewer.jsx"));
  ({default:Sidebar}=await server.ssrLoadModule("/src/layout/Sidebar.jsx"));
});
after(async()=>{await server?.close();});

for(const [raw,expected] of [['"answer"','answer'],['"\\\"answer\\\""','answer'],['"line one\\nline two"','line one\nline two'],['```text\nanswer\n```','answer'],['"""answer"""','answer']]) {
  test(`normalization preserves raw evidence for ${raw}`,()=>{
    const shown=presentOutput(raw,'Return plain text.');assert.equal(shown.text,expected);assert.ok(shown.issues.length);assert.notEqual(raw,shown.text);
  });
}
test('JSON string envelope becomes structured JSON and remains marked',()=>{
  const shown=presentOutput(JSON.stringify('{"x":1,"y":2}'),'Return JSON with keys x and y.');
  assert.equal(shown.type,'json');assert.equal(shown.text,'{\n  "x": 1,\n  "y": 2\n}');assert.ok(shown.issues.includes('serialized_string'));
});
test('invalid JSON stays visible with a contract problem',()=>{
  const shown=presentOutput('Certainly, {x:1}','Return JSON.');assert.equal(shown.text,'Certainly, {x:1}');assert.ok(shown.issues.includes('invalid_json'));
});
test('meaningful embedded quotes and explicitly requested fences survive',()=>{
  assert.equal(presentOutput('He said "yes".','Return plain text.').text,'He said "yes".');
  assert.equal(presentOutput('```text\nanswer\n```','Return a code fence.').text,'```text\nanswer\n```');
});
test('Markdown uses semantic readable markup and escapes raw HTML',()=>{
  const html=renderToStaticMarkup(createElement(MarkdownOutput,{text:'# Result\n- **one**\n- two\n<script>alert(1)</script>\n[bad](javascript:alert(1))'}));
  assert.match(html,/<h2>Result<\/h2>/);assert.match(html,/<ul>/);assert.match(html,/<strong>one<\/strong>/);assert.doesNotMatch(html,/<script|href="javascript/);assert.match(html,/&lt;script&gt;/);
});
test('Markdown preserves code blocks, tables, inline code and safe links',()=>{
  const html=renderToStaticMarkup(createElement(MarkdownOutput,{text:'```js\na < b\n```\n| Key | Value |\n| --- | --- |\n| x | `1` |\n[Source](https://example.com)'}));
  assert.match(html,/<pre><code>a &lt; b/);assert.match(html,/<table>/);assert.match(html,/<code>1<\/code>/);assert.match(html,/href="https:\/\/example.com"/);
});
test('final answer is primary, complete and has raw/copy/focus controls',()=>{
  const text='A long required report paragraph.\n'.repeat(300);
  const html=renderToStaticMarkup(createElement(OutputViewer,{text,label:'Final answer'}));
  assert.match(html,/class="output-viewer final-output"/);assert.match(html,/Rendered/);assert.match(html,/Raw/);assert.match(html,/Copy output/);assert.match(html,/Focus reading/);
  assert.equal((html.match(/A long required report paragraph/g)??[]).length,300);
});
test('intermediate output defaults to a preview and expandable full output',()=>{
  const html=renderToStaticMarkup(createElement(OutputViewer,{text:'agent text '.repeat(600),label:'Intermediate agent output',intermediate:true}));
  assert.match(html,/intermediate-output/);assert.match(html,/Expand full output/);assert.match(html,/output-preview/);assert.doesNotMatch(html,/agent text agent text agent text[\s\S]{1000}/);
});
test('persisted contract failures are displayed even when normalized content parses',()=>{
  const html=renderToStaticMarkup(createElement(OutputViewer,{text:'{"x":1}',contract:{format:'json',status:'invalid',issues:['json_keys_mismatch']}}));assert.match(html,/Output contract problem/);assert.match(html,/json keys mismatch/);
});
test('navigation consolidates evidence destinations and collapses workspace totals',()=>{
  const html=renderToStaticMarkup(createElement(Sidebar,{stats:{}}));
  for(const label of ['Live Simulation','Simulation History','Research Lab','Agents','HR Hiring','Organizations','Recycle Bin','Settings'])assert.ok(html.includes(label));
  for(const label of ['Messages','Logs','Event History'])assert.ok(!html.includes(`title="${label}"`));
  assert.match(html,/<details class="sidebar-totals"><summary>Workspace totals/);
});
test('permanent deletion is fail-closed unless the server explicitly permits it',()=>{
  for(const item of [null,{}, {permanentDeletionEligible:false}])assert.equal(canDeleteItem(item),false);
  assert.equal(canDeleteItem({permanentDeletionEligible:true}),true);
});


test('valid JSON scalar strings keep their meaningful quotes',()=>{
  const shown=presentOutput('"hello"','Return JSON.');assert.equal(shown.text,'"hello"');assert.deepEqual(shown.issues,[]);
});


test('explicitly requested quotation marks are preserved',()=>{
  const shown=presentOutput('"hello"','Return plain text surrounded by quotes.');assert.equal(shown.text,'"hello"');assert.deepEqual(shown.issues,[]);
});
