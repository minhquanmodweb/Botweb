// Exercise the actual picker functions with a small DOM adapter.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync(require('node:path').join(__dirname,'../web_notice_admin.html'),'utf8');
class Node {constructor(){this.children=[];this.value='';this.type='submit';}replaceChildren(){this.children=[]}append(...nodes){this.children.push(...nodes)}setAttribute(){}insertAdjacentHTML(){}close(){this.closed=true}}
const nodes=Object.fromEntries(['fixedPackage','packageKind','hotCount','hotList','saveHot','addHot','packageHint','hotSearch','hotResults','hotDialog'].map(id=>[id,new Node()]));nodes.packageKind.value='fixed';
const opened=[];const context={document:{createElement:()=>new Node()},$:id=>nodes[id],esc:String,icon:()=>'',empty:()=>'',dirty:()=>{},toast:()=>{},openHot:i=>opened.push(i),hotPicks:[{tuong:'Toro',skin:'Cũ',id:'10501'}],catalog:[{tuong:'Toro',skin:'Mới',id:'10502'},{tuong:'Krixi',skin:'Mới',id:'10601'}],hotReplace:0,packageCount:1};vm.createContext(context);
for(const name of ['renderHot','renderHotResults']){const start=html.indexOf('function '+name+'(');const end=html.indexOf('\n',start);vm.runInContext(html.slice(start,end),context)}
context.renderHot();const row=nodes.hotList.children[0];assert.equal(row.children[0].type,'button');assert.equal(row.children[1].type,'button');row.children[0].onclick();assert.deepEqual(opened,[0]);
context.renderHotResults();assert.equal(nodes.hotResults.children.length,1);assert.equal(nodes.hotResults.children[0].type,'button');nodes.hotResults.children[0].onclick();assert.equal(context.hotPicks[0].id,'10502');assert.equal(nodes.hotDialog.closed,true);assert.equal(nodes.saveHot.disabled,false);
nodes.hotList.children[0].children[1].onclick();assert.equal(context.hotPicks.length,0);assert.equal(nodes.saveHot.disabled,true);assert(nodes.packageHint.textContent.includes('1'));
context.hotReplace=-1;context.renderHotResults();nodes.hotResults.children[0].onclick();assert.equal(context.hotPicks.length,1);assert.equal(nodes.saveHot.disabled,false);console.log('PASS pack picker: button types, replace, selection, removal, required count, add');
