const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../static/true-sleep.js'),'utf8');
const flush=()=>new Promise(resolve=>setImmediate(resolve));
async function harness(){
  const calls=[],messages=[],intervals=new Map();let next=0;
  const ctx={asleep:false,waking:false,sleepRequest:Promise.resolve(),
    SCREEN_SLEEP_KEY:'sleep',AbortController,console,
    api:async(url)=>{calls.push(url);return {mode:'hardware',asleep:url.endsWith('sleep')};},
    setTimeout,clearTimeout,
    setInterval(fn){intervals.set(++next,fn);return next;},
    clearInterval(id){intervals.delete(id);},
    document:{querySelectorAll:()=>[]},sessionStorage:{removeItem(){},setItem(){}},
    window:{addEventListener(){}},fetch:async()=>{},
    setSleepOverlay(active){ctx.asleep=active;},toast(message){messages.push(message);},
    updateClock(){},run(){},getEverything(){},renderWeather(){},
    displayPower(){},sleepDisplay(){},wakeDisplay(){}};
  vm.createContext(ctx);vm.runInContext(source,ctx);await flush();
  return {ctx,calls,messages,intervals};
}
test('startup restores hardware and clears stale overlay',async()=>{
  const {ctx,calls}=await harness();assert.equal(ctx.asleep,false);
  assert.ok(calls.includes('/api/display/wake'));
});
test('hardware sleep and wake restore normal UI',async()=>{
  const {ctx,intervals}=await harness();await ctx.sleepDisplay();
  assert.equal(ctx.asleep,true);assert.equal(intervals.size,1);
  await ctx.wakeDisplay();assert.equal(ctx.asleep,false);assert.equal(intervals.size,0);
});
test('unsupported panel never remains in CSS-only sleep',async()=>{
  const {ctx,messages,intervals}=await harness();
  ctx.api=async()=>({mode:'unavailable',error:'No panel'});
  await ctx.sleepDisplay();assert.equal(ctx.asleep,false);
  assert.equal(intervals.size,0);assert.match(messages.at(-1),/True sleep unavailable/);
});
test('lease failure stops heartbeat and reveals UI',async()=>{
  const {ctx,intervals}=await harness();await ctx.sleepDisplay();
  ctx.api=async()=>{throw Error('offline');};
  await [...intervals.values()][0]();await flush();
  assert.equal(ctx.asleep,false);assert.equal(intervals.size,0);
});
test('wake retries failure and cannot leave waking flag stuck',async()=>{
  const {ctx,messages}=await harness();await ctx.sleepDisplay();let attempts=0;
  ctx.api=async()=>{attempts++;throw Error('offline');};
  await ctx.wakeDisplay();assert.equal(attempts,2);
  assert.equal(ctx.waking,false);assert.equal(ctx.asleep,false);
  assert.match(messages.at(-1),/recovery/);
});
test('wake waits for pending sleep to avoid late blanking',async()=>{
  const {ctx,calls}=await harness();let finish;
  ctx.api=url=>{calls.push(url);return url.endsWith('sleep')?
    new Promise(resolve=>{finish=resolve;}):Promise.resolve({asleep:false});};
  const sleeping=ctx.sleepDisplay();const waking=ctx.wakeDisplay();
  finish({mode:'hardware',asleep:true});await Promise.all([sleeping,waking]);
  assert.equal(ctx.asleep,false);assert.equal(calls.at(-1),'/api/display/wake');
});
