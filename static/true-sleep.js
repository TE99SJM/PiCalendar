/* PiCalendar 0.5.4: hardware sleep policy layered over the existing gestures.
   app.js owns calendar features and the full-screen touch target. No CSS-only sleep. */
'use strict';
let sleepHeartbeat=null;
let sleepBusy=false;
let sleepGeneration=0;

// app.js uses these function bindings from its existing event listeners.
displayPower=async function(action){
  const controller=new AbortController();
  const timer=setTimeout(()=>controller.abort(),5000);
  try{
    return await api(`/api/display/${action}`,{method:'POST',signal:controller.signal});
  }catch(error){return {mode:'unavailable',error:error.message};}
  finally{clearTimeout(timer);}
};
function stopSleepHeartbeat(){clearInterval(sleepHeartbeat);sleepHeartbeat=null;}
function revealAfterSleep(message){
  stopSleepHeartbeat();
  try{sessionStorage.removeItem(SCREEN_SLEEP_KEY);}catch{}
  setSleepOverlay(false);
  if(message)toast(message);
}
async function renewSleepLease(){
  if(!asleep||waking||sleepBusy)return;
  sleepBusy=true;
  const generation=sleepGeneration;
  try{
    sleepRequest=displayPower('sleep');
    const result=await sleepRequest;
    if(generation!==sleepGeneration)return;
    if(result.mode!=='hardware'||!result.asleep){
      await displayPower('wake');
      revealAfterSleep('Display control lost. Recovery will restore the backlight within 30 seconds.');
    }
  }finally{sleepBusy=false;}
}
sleepDisplay=async function(){
  if(asleep||sleepBusy||waking)return;
  sleepBusy=true;
  const generation=++sleepGeneration;
  document.querySelectorAll('dialog[open]').forEach(dialog=>dialog.close());
  // The overlay is only a touch target during a real hardware sleep transaction.
  setSleepOverlay(true);
  try{
    sleepRequest=displayPower('sleep');
    const result=await sleepRequest;
    if(generation!==sleepGeneration)return;
    if(result.mode!=='hardware'||!result.asleep){
      await displayPower('wake');
      revealAfterSleep('True sleep unavailable: '+(result.error||'no supported backlight control'));
      return;
    }
    try{sessionStorage.setItem(SCREEN_SLEEP_KEY,'1');}catch{}
    stopSleepHeartbeat();
    sleepHeartbeat=setInterval(()=>void renewSleepLease(),8000);
  }finally{sleepBusy=false;}
};
wakeDisplay=async function(){
  if(waking)return;
  waking=true;
  ++sleepGeneration;
  stopSleepHeartbeat();
  try{
    await sleepRequest;
    let result=await displayPower('wake');
    if(result.error)result=await displayPower('wake');
    revealAfterSleep(result.error?'Wake failed; recovery will retry automatically.':null);
    updateClock();
    run(getEverything);
    run(renderWeather);
  }finally{waking=false;}
};
// Reload/navigation must not leave an old session-storage overlay trapping users.
void wakeDisplay();
// A tab closing releases its lease; the independent guardian also handles crashes.
window.addEventListener('pagehide',()=>{
  stopSleepHeartbeat();
  if(asleep)fetch('/api/display/wake',{method:'POST',keepalive:true}).catch(()=>{});
});
