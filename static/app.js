/* Family Calendar — entirely local, touch-friendly, no CDN or subscriptions. */
'use strict';

const $ = id => document.getElementById(id);
const state = {anchor:new Date(), selected:new Date(), view:'month', events:[], chores:[], groceries:[], meals:[], photos:[], calendars:[], settings:{}, status:{}, editing:null, photoIndex:0};
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const dateKey = d => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
const parseDay = d => {const [y,m,day]=d.split('-').map(Number);return new Date(y,m-1,day);};
const addDays = (d,n) => {const x=new Date(d.getFullYear(),d.getMonth(),d.getDate());x.setDate(x.getDate()+n);return x;};
const weekStart = d => addDays(d,-d.getDay());
const dayLabel = d => d.toLocaleDateString(undefined,{weekday:'long',month:'long',day:'numeric'});
const timeLabel = d => d.toLocaleTimeString(undefined,{hour:'numeric',minute:'2-digit'});
const localTimeInput = d => `${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;
const validColor = x => /^#[a-f\d]{6}$/i.test(x) ? x : '#79bbef';
let toastTimer;

function toast(message) {
  const node=$('toast'); node.textContent=message; node.classList.add('visible');
  clearTimeout(toastTimer); toastTimer=setTimeout(()=>node.classList.remove('visible'),3500);
}
async function api(url, opts={}) {
  const response=await fetch(url,{...opts,headers:{...(opts.body instanceof FormData ? {} : {'Content-Type':'application/json'}),...(opts.headers||{})}});
  const json=await response.json().catch(()=>({detail:'Unexpected server response'}));
  if(!response.ok) throw Error(typeof json.detail==='string' ? json.detail : JSON.stringify(json.detail||'Request failed'));
  return json;
}
async function run(fn) {try{await fn();}catch(err){toast('⚠ '+err.message);console.error(err);}}
async function getEverything(){
  const start=dateKey(addDays(new Date(state.anchor.getFullYear(),state.anchor.getMonth(),1),-70));
  const end=dateKey(addDays(new Date(state.anchor.getFullYear(),state.anchor.getMonth()+2,1),70));
  const [events,chores,groceries,meals,calendars,settings,status,photos]=await Promise.all([
    api(`/api/events?start=${start}&end=${end}`),api('/api/chores'),api('/api/groceries'),
    api(`/api/meals?start=${start}&end=${end}`),api('/api/calendars'),api('/api/settings'),
    api('/api/status'),api('/api/photos')]);
  Object.assign(state,{events,chores,groceries,meals,calendars,settings,status,photos});
  renderAll();
}
async function loadEvents(){
  const start=dateKey(addDays(new Date(state.anchor.getFullYear(),state.anchor.getMonth(),1),-70));
  const end=dateKey(addDays(new Date(state.anchor.getFullYear(),state.anchor.getMonth()+2,1),70));
  [state.events,state.meals]=await Promise.all([api(`/api/events?start=${start}&end=${end}`),api(`/api/meals?start=${start}&end=${end}`)]);
  renderAll();
}
function eventOnDay(event, day){
  const begin=new Date(day.getFullYear(),day.getMonth(),day.getDate()).getTime();
  const finish=addDays(day,1).getTime();
  if(event.all_day){const key=dateKey(day);return event.start.slice(0,10)<=key && event.end.slice(0,10)>key;}
  return new Date(event.start).getTime()<finish && new Date(event.end).getTime()>begin;
}
function sortEvents(events){return [...events].sort((a,b)=>Number(b.all_day)-Number(a.all_day) || new Date(a.start)-new Date(b.start));}
function eventText(event){return event.all_day ? event.title : `${timeLabel(new Date(event.start))} ${event.title}`;}
function renderCalendar(){
  const anchor=state.anchor, isMonth=state.view==='month';
  const first=isMonth ? new Date(anchor.getFullYear(),anchor.getMonth(),1) : weekStart(anchor);
  const gridStart=isMonth ? weekStart(first) : first;
  const days=isMonth ? 42 : 7;
  const visible=isMonth ? anchor.toLocaleDateString(undefined,{month:'long',year:'numeric'}) :
    `${first.toLocaleDateString(undefined,{month:'short',day:'numeric'})} – ${addDays(first,6).toLocaleDateString(undefined,{month:'short',day:'numeric',year:'numeric'})}`;
  $('month-title').textContent=visible;
  $('view-month').classList.toggle('active',isMonth);$('view-week').classList.toggle('active',!isMonth);
  const today=dateKey(new Date()), selected=dateKey(state.selected);
  let html='';
  for(let i=0;i<days;i++){
    const day=addDays(gridStart,i),key=dateKey(day),onDay=sortEvents(state.events.filter(e=>eventOnDay(e,day)));
    const notMonth=isMonth && day.getMonth()!==anchor.getMonth();
    html+=`<div class="day-cell ${notMonth?'other':''} ${key===today?'today':''} ${key===selected?'selected':''}" data-day="${key}" role="button" tabindex="0" aria-label="${esc(dayLabel(day))}">
      <div class="day-head"><span class="day-number">${day.getDate()}</span>${onDay.length>0?`<span class="dot">${onDay.length} event${onDay.length!==1?'s':''}</span>`:''}</div>
      <div class="day-events">${onDay.slice(0,isMonth?3:12).map(e=>`<button class="event-pill" data-event="${esc(e.id)}" style="border-left-color:${validColor(e.color)}">${esc(eventText(e))}</button>`).join('')}
      ${onDay.length>(isMonth?3:12)?`<span class="more-events">+${onDay.length-(isMonth?3:12)} more</span>`:''}</div></div>`;
  }
  $('calendar-grid').innerHTML=html;
  $('calendar-grid').style.gridTemplateRows=`repeat(${days/7},minmax(0,1fr))`;
}
function renderAgenda(){
  const day=state.selected;$('selected-date-title').textContent=dayLabel(day);
  const items=sortEvents(state.events.filter(e=>eventOnDay(e,day)));
  $('agenda-list').innerHTML=items.length? items.map(e=>`<button class="agenda-event" data-event="${esc(e.id)}"><span class="agenda-stripe" style="border-color:${validColor(e.color)}"></span><span><strong>${esc(e.title)}</strong><small>${e.all_day?'All day':esc(timeLabel(new Date(e.start))+' – '+timeLabel(new Date(e.end)))} · ${esc(e.calendar_name)}</small></span></button>`).join(''):
    '<div class="empty-state">Nothing scheduled. Tap ＋ to add an event.</div>';
}
function choreDone(c){
  if(!c.done_on)return false;
  if(c.repeat==='once')return true;
  if(c.repeat==='daily')return c.done_on===dateKey(new Date());
  if(c.repeat==='weekly')return dateKey(weekStart(parseDay(c.done_on)))===dateKey(weekStart(new Date()));
  return false;
}
function renderChores(){
  $('chore-list').innerHTML=state.chores.length?state.chores.map(c=>{const checked=choreDone(c);return `<div class="task-row"><input type="checkbox" data-chore-check="${esc(c.id)}" ${checked?'checked':''} aria-label="Complete ${esc(c.title)}"><span class="task-copy ${checked?'checked':''}">${esc(c.title)}${c.assignee?` <small>· ${esc(c.assignee)}</small>`:''}${c.repeat!=='once'?` <small>↻ ${esc(c.repeat)}</small>`:''}</span><button class="delete-small" data-chore-delete="${esc(c.id)}" aria-label="Delete chore">×</button></div>`}).join(''):'<div class="empty-state">No chores yet.</div>';
}
function renderGroceries(){
  $('shopping-list').innerHTML=state.groceries.length?state.groceries.map(item=>`<div class="task-row"><input type="checkbox" data-grocery-check="${esc(item.id)}" ${item.checked?'checked':''} aria-label="Purchased ${esc(item.title)}"><span class="task-copy ${item.checked?'checked':''}">${esc(item.title)}</span><button class="delete-small" data-grocery-delete="${esc(item.id)}" aria-label="Delete shopping item">×</button></div>`).join(''):'<div class="empty-state">Your shopping list is empty.</div>';
}
function renderMeals(){
  let html='';for(let i=0;i<5;i++){
    const day=addDays(state.selected,i),key=dateKey(day),item=state.meals.find(m=>m.day===key);
    html+=`<button class="meal-row" data-meal-day="${key}"><span>${day.toLocaleDateString(undefined,{weekday:'short'})}</span><strong>${item?esc(item.label):'＋ Plan meal'}</strong></button>`;
  }$('meal-list').innerHTML=html;
}
function renderPhotos(){
  const el=$('photo-container');
  if(!state.photos.length){el.innerHTML='<div class="photo-empty">📷<br><small>Add photos in Settings</small></div>';return;}
  state.photoIndex%=state.photos.length;
  el.innerHTML=`<img src="${esc(state.photos[state.photoIndex].url)}" alt="Family photo">`;
}
function updateClock(){
  const now=new Date();$('clock').textContent=now.toLocaleTimeString(undefined,{hour:'numeric',minute:'2-digit'});
  $('date-long').textContent=now.toLocaleDateString(undefined,{weekday:'long',month:'long',day:'numeric'});
}
function renderStatus(){
  $('family-name').textContent=state.settings.family_name||'Our Family';
  const s=$('sync-status');s.classList.toggle('error',Boolean(state.status.last_error));
  if(state.status.google_connected && state.status.google_online===false){
    s.classList.remove('error');
    s.textContent='● Offline — saved calendar available; edits queue for sync';
    s.title=state.status.last_sync?'Last Google sync: '+new Date(state.status.last_sync).toLocaleString():'Google has not synced yet';
  }
  else if(state.status.last_error){s.textContent='● Google sync needs attention — saved data available';s.title=state.status.last_error;}
  else if(!state.status.google_connected){s.textContent='● Local mode — Google not connected';}
  else if(state.status.last_sync){s.textContent='● Google synced '+timeLabel(new Date(state.status.last_sync));}
  else{s.textContent='● Google connected — waiting for sync';}
}
const wmoText=code=> code===0?'☀️ Clear':code<=3?'⛅ Partly cloudy':code<=48?'🌫️ Fog':code<=67?'🌧️ Rain':code<=77?'🌨️ Snow':code<=82?'🌦️ Showers':code<=86?'❄️ Snow':code<=99?'⛈️ Storm':'🌤️ Weather';
async function renderWeather(){
  try{
    const w=await api('/api/weather');
    $('weather').innerHTML=w.configured&&!w.error?`<strong>${esc(wmoText(w.code))} · ${w.temperature}°F</strong><small>${esc(w.location)} · Feels like ${w.feels_like}°</small>`:'';
  }catch{ $('weather').innerHTML=''; }
}
function renderAll(){renderCalendar();renderAgenda();renderChores();renderGroceries();renderMeals();renderPhotos();renderStatus();updateClock();}
function show(id){$(id).showModal();}
function hide(id){$(id).close();}
function calendarOptions(selected){
  return state.calendars.filter(c=>c.editable).map(c=>`<option value="${esc(c.id)}" ${c.id===selected?'selected':''}>${esc(c.name)}${c.id==='local'?' (offline)':''}</option>`).join('');
}
function fillEvent(event=null){
  state.editing=event?.id||null;
  $('event-dialog-title').textContent=event?'Edit event':'New event';
  $('delete-event').classList.toggle('hidden',!event);
  $('event-title').value=event?.title||'';
  $('event-description').value=event?.description||'';
  $('event-all-day').checked=Boolean(event?.all_day);
  let defaultCalendar=state.calendars.find(c=>c.id!=='local'&&c.editable&&c.selected)?.id||'local';
  $('event-calendar').innerHTML=calendarOptions(event?.calendar_id||defaultCalendar);
  $('event-calendar').disabled=!!event;
  let start=event?(event.all_day?parseDay(event.start.slice(0,10)):new Date(event.start)):new Date(state.selected);
  let end=event?(event.all_day?addDays(parseDay(event.end.slice(0,10)),-1):new Date(event.end)):new Date(state.selected);
  if(!event){start.setHours(9,0,0,0);end.setHours(10,0,0,0);}
  $('event-start-date').value=dateKey(start);$('event-end-date').value=dateKey(end);
  $('event-start-time').value=localTimeInput(start);$('event-end-time').value=localTimeInput(end);
  changeAllDay();show('event-dialog');$('event-title').focus();
}
function changeAllDay(){const hidden=$('event-all-day').checked;$('start-time-label').classList.toggle('hidden',hidden);$('end-time-label').classList.toggle('hidden',hidden);}
let syncAfterEditTimer;
function syncGoogleAfterEdit(calendarId){
  // Preserve instant offline saves, but push changes as soon as the Pi is online.
  if(calendarId==='local'||!state.status.google_connected||state.status.google_online===false)return;
  clearTimeout(syncAfterEditTimer);
  syncAfterEditTimer=setTimeout(async()=>{
    try{
      const result=await api('/api/sync',{method:'POST'});
      if(result.error)toast('Saved locally; Google sync will retry.');
      state.status=await api('/api/status');renderStatus();
    }catch(err){console.warn('Saved offline; Google sync will retry later.',err);}
  },700);
}
async function saveEvent(e){
  e.preventDefault();
  const allDay=$('event-all-day').checked;
  let start=$('event-start-date').value,end=$('event-end-date').value;
  if(!start||!end)throw Error('Choose a start and end date.');
  if(allDay){end=dateKey(addDays(parseDay(end),1));}
  else{
    start=new Date(start+'T'+$('event-start-time').value).toISOString();
    end=new Date(end+'T'+$('event-end-time').value).toISOString();
  }
  const body={title:$('event-title').value.trim(),description:$('event-description').value,
    calendar_id:$('event-calendar').value,all_day:allDay,start,end};
  if(new Date(body.end)<=new Date(body.start))throw Error('The end must be after the start.');
  await api(state.editing?'/api/events/'+encodeURIComponent(state.editing):'/api/events',{
    method:state.editing?'PUT':'POST',body:JSON.stringify(body)});
  hide('event-dialog');
  toast(body.calendar_id==='local'?'Saved on this Pi only.':'Saved locally; syncing with Google Calendar.');
  await loadEvents();
  syncGoogleAfterEdit(body.calendar_id);
}
function editMeal(day){
  const key=day||dateKey(state.selected);$('meal-date').value=key;
  $('meal-name').value=state.meals.find(m=>m.day===key)?.label||'';show('meal-dialog');
}
function renderSettings(){
  $('settings-family').value=state.settings.family_name||'Our Family';
  $('weather-location').value=state.settings.weather_location||'';
  $('weather-latitude').value=state.settings.weather_latitude||'';
  $('weather-longitude').value=state.settings.weather_longitude||'';
  const st=state.status;
  const ready=st.google_client_configured;
  const account=state.settings.google_account||'';
  $('google-connection').innerHTML=`<strong>${st.google_connected?'✓ Google Calendar connected':'Google Calendar not connected'}</strong>
    ${account&&st.google_connected?`<p class="google-account">${esc(account)}</p>`:''}
    <p>${st.google_connected?'Events sync both ways with Google Calendar when online.':'Connect your Google account to display and edit events. Local calendars work offline.'}</p>
    ${st.last_error?`<p class="google-error">${esc(st.last_error)}</p>`:''}
    ${!ready?'<p class="google-connection-help">Google Sign-In has not been enabled by the PiCalendar publisher. Local calendars still work.</p>':''}
    <div class="google-login-actions">
      <button type="button" class="btn btn-primary" id="settings-google-login" ${!ready?'disabled title="Google sign-in not provisioned"':''}>${st.google_connected?'Reconnect Google account':'Sign in with Google'}</button>
      ${st.google_connected?'<button type="button" class="btn btn-secondary" id="settings-sync">Sync now</button><button type="button" class="btn btn-secondary" id="settings-google-disconnect">Sign out</button>':''}
    </div>`;
  $('calendar-settings').innerHTML=state.calendars.map(c=>`<label class="cal-setting"><input type="checkbox" data-calendar="${esc(c.id)}" ${c.selected?'checked':''} ${c.id==='local'?'disabled':''}><span class="cal-dot" style="background:${validColor(c.color)}"></span>${esc(c.name)}${c.editable?'':' (read only)'}</label>`).join('');
  renderPhotoSettings();
}
function renderPhotoSettings(){
  $('photo-settings').innerHTML=state.photos.map(p=>`<div class="photo-preview"><img src="${esc(p.url)}" alt="Photo"><button type="button" data-photo-delete="${esc(p.filename)}" title="Remove photo">×</button></div>`).join('');
}
let changingPeriod=false;
// Navigation is used by BOTH arrow buttons and finger swipes. Keep the outgoing
// month visible while the next month is fetched from the local SQLite cache.
async function changePeriod(delta){
  if(changingPeriod)return;
  changingPeriod=true;
  const grid=$('calendar-grid'), viewport=$('calendar-viewport');
  const previous=grid.cloneNode(true);
  previous.removeAttribute('id');
  previous.setAttribute('aria-hidden','true');
  previous.classList.add('calendar-slide-ghost');
  previous.style.gridTemplateRows=grid.style.gridTemplateRows;
  viewport.appendChild(previous);
  const priorAnchor=state.anchor;
  try{
    if(state.view==='month')state.anchor=new Date(state.anchor.getFullYear(),state.anchor.getMonth()+delta,1);
    else state.anchor=addDays(state.anchor,delta*7);
    await loadEvents();
    const reduceMotion=window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches;
    if(!reduceMotion && typeof grid.animate==='function'){
      const direction=delta>0?1:-1;
      const timing={duration:730,easing:'cubic-bezier(0.22, 1, 0.36, 1)',fill:'both'};
      const out=previous.animate([{transform:'translateX(0%)'},{transform:`translateX(${-direction*100}%)`}],timing);
      const next=grid.animate([{transform:`translateX(${direction*100}%)`},{transform:'translateX(0%)'}],timing);
      await Promise.all([out.finished,next.finished]);
      out.cancel();next.cancel();
    }
  }catch(err){state.anchor=priorAnchor;await loadEvents().catch(()=>{});throw err;}
  finally{previous.remove();changingPeriod=false;}
}
function goPrevNext(delta){run(()=>changePeriod(delta));}
// The Pi keeps running so the touchscreen can detect wake-up gestures.
// When configured on the Pi, the optional backlight API also turns off the
// panel light. A hardware-off monitor that disconnects its touch USB cannot
// be woken by touch; leave hardware control disabled on those displays.
const SCREEN_SLEEP_KEY='family-calendar-screen-sleeping';
const WAKE_WINDOW_MS=650;
const MAX_TAP_MOVEMENT=40;
const MAX_TAP_SEPARATION=140;
let asleep=false;
let firstTap=null;
let pressedAt=null;
let waking=false;
let sleepRequest=Promise.resolve();

function setSleepOverlay(active){
  asleep=active;
  firstTap=null;
  pressedAt=null;
  $('sleep-overlay').classList.toggle('sleeping',active);
  document.body.classList.toggle('screen-sleeping',active);
  $('sleep-overlay').setAttribute('aria-hidden',active?'false':'true');
  if(active) $('sleep-overlay').focus({preventScroll:true});
}
async function displayPower(action){
  try {return await api(`/api/display/${action}`,{method:'POST'});}
  catch(err){console.warn('Optional physical backlight control unavailable:',err);return null;}
}
async function sleepDisplay(){
  if(asleep)return;
  // Close dialogs so focus cannot become trapped behind the sleep screen.
  document.querySelectorAll('dialog[open]').forEach(dialog=>dialog.close());
  try{sessionStorage.setItem(SCREEN_SLEEP_KEY,'1');}catch{}
  setSleepOverlay(true);
  // This call is a no-op unless a real backlight device is configured.
  sleepRequest=displayPower('sleep');
  await sleepRequest;
}
async function wakeDisplay(){
  if(!asleep||waking)return;
  waking=true;
  // Finish any pending sleep call first so it cannot blank the panel after wake.
  await sleepRequest;
  // Restore the physical backlight first, then reveal the dashboard.
  await displayPower('wake');
  try{sessionStorage.removeItem(SCREEN_SLEEP_KEY);}catch{}
  setSleepOverlay(false);
  waking=false;
  updateClock();
  run(getEverything);
  run(renderWeather);
}
function trackSleepTouchDown(event){
  if(!asleep||event.isPrimary===false)return;
  if(event.pointerType==='mouse'&&event.button!==0)return;
  event.preventDefault();
  pressedAt={time:performance.now(),x:event.clientX,y:event.clientY,id:event.pointerId};
}
function trackSleepTouchUp(event){
  if(!asleep)return;
  event.preventDefault();
  const last=pressedAt;
  pressedAt=null;
  if(!last||last.id!==event.pointerId)return;
  const now=performance.now();
  if(now-last.time>400||Math.hypot(event.clientX-last.x,event.clientY-last.y)>MAX_TAP_MOVEMENT){firstTap=null;return;}
  if(firstTap && now-firstTap.time<WAKE_WINDOW_MS && Math.hypot(event.clientX-firstTap.x,event.clientY-firstTap.y)<MAX_TAP_SEPARATION){
    firstTap=null;
    void wakeDisplay();
  }else{
    firstTap={time:now,x:event.clientX,y:event.clientY};
  }
}
function initializeSleep(){
  $('sleep-button').addEventListener('click',()=>void sleepDisplay());
  const overlay=$('sleep-overlay');
  overlay.addEventListener('pointerdown',trackSleepTouchDown);
  overlay.addEventListener('pointerup',trackSleepTouchUp);
  overlay.addEventListener('pointercancel',()=>{pressedAt=null;firstTap=null;});
  // Disable synthetic clicks or long-press context menus on the dark display.
  overlay.addEventListener('click',event=>event.preventDefault());
  overlay.addEventListener('contextmenu',event=>event.preventDefault());
  // Escape/Enter provide a fallback when testing without a touchscreen.
  overlay.addEventListener('keydown',event=>{if(asleep&&['Enter','Escape',' '].includes(event.key)){event.preventDefault();void wakeDisplay();}});
  try{if(sessionStorage.getItem(SCREEN_SLEEP_KEY)==='1')setSleepOverlay(true);}catch{}
}

function eventListeners(){
  $('prev').addEventListener('click',()=>goPrevNext(-1));$('next').addEventListener('click',()=>goPrevNext(1));
  $('today').addEventListener('click',()=>{state.anchor=new Date();state.selected=new Date();run(loadEvents);});
  $('view-month').addEventListener('click',()=>{state.view='month';renderCalendar();});
  $('view-week').addEventListener('click',()=>{state.view='week';renderCalendar();});
  $('add-event-button').addEventListener('click',()=>fillEvent());$('add-day-event').addEventListener('click',()=>fillEvent());
  $('settings-button').addEventListener('click',()=>{renderSettings();show('settings-dialog');});
  $('add-chore').addEventListener('click',()=>{$('chore-form').reset();show('chore-dialog');});
  $('add-grocery').addEventListener('click',()=>{$('grocery-form').reset();show('grocery-dialog');});
  $('edit-meal').addEventListener('click',()=>editMeal());
  $('event-all-day').addEventListener('change',changeAllDay);
  document.querySelectorAll('[data-close]').forEach(button=>button.addEventListener('click',()=>hide(button.dataset.close)));
  $('calendar-grid').addEventListener('click',e=>{
    const event=e.target.closest('[data-event]');if(event){const item=state.events.find(x=>x.id===event.dataset.event);if(item)fillEvent(item);return;}
    const cell=e.target.closest('[data-day]');if(cell){state.selected=parseDay(cell.dataset.day);renderCalendar();renderAgenda();renderMeals();}
  });
  $('agenda-list').addEventListener('click',e=>{const item=state.events.find(x=>x.id===e.target.closest('[data-event]')?.dataset.event);if(item)fillEvent(item);});
  $('calendar-grid').addEventListener('keydown',e=>{if(e.key==='Enter'&&e.target.matches('[data-day]')){state.selected=parseDay(e.target.dataset.day);renderAll();}});
  $('event-form').addEventListener('submit',e=>run(()=>saveEvent(e)));
  $('delete-event').addEventListener('click',()=>run(async()=>{
    if(!state.editing||!confirm('Delete this event? It will also be deleted from Google Calendar after sync.'))return;
    const deleting=state.events.find(x=>x.id===state.editing);
    await api('/api/events/'+encodeURIComponent(state.editing),{method:'DELETE'});
    hide('event-dialog');toast('Event deleted.');await loadEvents();
    syncGoogleAfterEdit(deleting?.calendar_id);
  }));
  $('chore-form').addEventListener('submit',e=>run(async()=>{e.preventDefault();await api('/api/chores',{method:'POST',body:JSON.stringify({title:$('chore-title').value,assignee:$('chore-assignee').value,repeat:$('chore-repeat').value})});hide('chore-dialog');state.chores=await api('/api/chores');renderChores();}));
  $('grocery-form').addEventListener('submit',e=>run(async()=>{e.preventDefault();await api('/api/groceries',{method:'POST',body:JSON.stringify({title:$('grocery-title').value})});hide('grocery-dialog');state.groceries=await api('/api/groceries');renderGroceries();}));
  $('meal-form').addEventListener('submit',e=>run(async()=>{e.preventDefault();await api('/api/meals',{method:'PUT',body:JSON.stringify({day:$('meal-date').value,label:$('meal-name').value})});hide('meal-dialog');await loadEvents();}));
  $('meal-list').addEventListener('click',e=>{const button=e.target.closest('[data-meal-day]');if(button)editMeal(button.dataset.mealDay);});
  $('chore-list').addEventListener('change',e=>run(async()=>{const id=e.target.dataset.choreCheck;if(!id)return;await api(`/api/chores/${encodeURIComponent(id)}?done=${e.target.checked}`,{method:'PATCH'});state.chores=await api('/api/chores');renderChores();}));
  $('chore-list').addEventListener('click',e=>run(async()=>{const id=e.target.closest('[data-chore-delete]')?.dataset.choreDelete;if(!id)return;await api('/api/chores/'+encodeURIComponent(id),{method:'DELETE'});state.chores=await api('/api/chores');renderChores();}));
  $('shopping-list').addEventListener('change',e=>run(async()=>{const id=e.target.dataset.groceryCheck;if(!id)return;await api(`/api/groceries/${encodeURIComponent(id)}?checked=${e.target.checked}`,{method:'PATCH'});state.groceries=await api('/api/groceries');renderGroceries();}));
  $('shopping-list').addEventListener('click',e=>run(async()=>{const id=e.target.closest('[data-grocery-delete]')?.dataset.groceryDelete;if(!id)return;await api('/api/groceries/'+encodeURIComponent(id),{method:'DELETE'});state.groceries=await api('/api/groceries');renderGroceries();}));
  $('sync-button').addEventListener('click',sync);
  $('settings-dialog').addEventListener('click',e=>{
    if(e.target.id==='settings-sync')run(async()=>{await sync();renderSettings();});
    if(e.target.id==='settings-google-login')run(async()=>{
      const result=await api('/api/google/start',{method:'POST'});
      // OAuth must use the top-level browser, not a Google login embedded in an iframe.
      if(window.parent!==window){
        window.parent.postMessage({source:'picalendar',event:'google-authorize',url:result.authorization_url},'http://127.0.0.1:8081');
      }else{
        window.location.assign(result.authorization_url);
      }
    });
  });
  $('google-connection').addEventListener('click',e=>{
    if(e.target.id!=='settings-google-disconnect')return;
    if(!window.confirm('Disconnect Google Calendar from this device? Local entries will remain.'))return;
    run(async()=>{
      await api('/api/google/disconnect',{method:'POST'});
      await getEverything();renderSettings();toast('Google Calendar disconnected.');
    });
  });
  $('calendar-settings').addEventListener('change',e=>run(async()=>{
    if(!e.target.dataset.calendar)return;
    await api(`/api/calendars/${encodeURIComponent(e.target.dataset.calendar)}?selected=${e.target.checked}`,{method:'PATCH'});
    await getEverything();renderSettings();
  }));
  $('settings-form').addEventListener('submit',e=>run(async()=>{
    e.preventDefault();const body={family_name:$('settings-family').value,weather_location:$('weather-location').value,
      weather_latitude:$('weather-latitude').value,weather_longitude:$('weather-longitude').value};
    state.settings=await api('/api/settings',{method:'PUT',body:JSON.stringify(body)});
    hide('settings-dialog');renderStatus();renderWeather();toast('Settings saved.');
  }));
  $('photo-upload').addEventListener('change',e=>run(async()=>{
    const files=[...e.target.files];if(!files.length)return;
    for(const file of files){const form=new FormData();form.append('file',file);await api('/api/photos',{method:'POST',body:form});}
    e.target.value='';state.photos=await api('/api/photos');renderPhotos();renderPhotoSettings();toast(`${files.length} photo${files.length>1?'s':''} added.`);
  }));
  $('photo-settings').addEventListener('click',e=>run(async()=>{
    const name=e.target.closest('[data-photo-delete]')?.dataset.photoDelete;if(!name)return;
    await api('/api/photos/'+encodeURIComponent(name),{method:'DELETE'});
    state.photos=await api('/api/photos');state.photoIndex=0;renderPhotos();renderPhotoSettings();
  }));
}
async function sync(){
  $('sync-button').disabled=true;
  try{
    const result=await api('/api/sync',{method:'POST'});
    if(result.error)throw new Error(result.error);
    await getEverything();
    toast(result.message||'Calendar synced.');
  }catch(err){toast('Sync: '+err.message);state.status=await api('/api/status');renderStatus();}
  finally{$('sync-button').disabled=false;}
}
async function start(){
  eventListeners();initializeSleep();updateClock();setInterval(()=>{if(!asleep)updateClock();},15000);
  setInterval(()=>{if(!asleep&&state.photos.length){state.photoIndex=(state.photoIndex+1)%state.photos.length;renderPhotos();}},12000);
  setInterval(()=>{if(!asleep&&!document.querySelector('dialog[open]'))run(getEverything);},60000);
  setInterval(()=>{if(!asleep)renderWeather();},900000);
  try{
    await getEverything();
    const outcome=new URLSearchParams(location.search).get('google');
    if(outcome==='connected'){
      toast('Google account connected. Syncing calendars…');
      run(async()=>{await sync();renderSettings();});
      history.replaceState(null,'',location.pathname);
    }else if(outcome==='error'){
      toast('Google sign-in failed. Try again in Settings.');
      history.replaceState(null,'',location.pathname);
    }
    renderWeather();
    // The splash stays visible until the calendar actually has data and has rendered.
    if(window.parent!==window && document.referrer){
      try{window.parent.postMessage({source:'picalendar',event:'interface-ready'},new URL(document.referrer).origin);}catch{}
    }
  }catch(err){toast('Unable to connect to the local calendar: '+err.message);}
}
document.addEventListener('DOMContentLoaded',start);
