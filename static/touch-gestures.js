/* PiCalendar v1.2.1 touchscreen gestures.
   TouchEvents: direct touch scroll; PointerEvents: fallback for HID touchscreens
   that emulate a mouse. No text selection and no visible scrollbars. */
(() => {
 'use strict';
 const MIN_SCROLL=7, MIN_SWIPE=60, CLICK_GUARD=420;
 const interactive = node => !!node?.closest?.('input:not([type="checkbox"]),textarea,select,[contenteditable="true"]');
 const clock = () => performance.now();
 let blockClicksUntil=0;
 document.addEventListener('click', e=>{
   if(clock()<blockClicksUntil && (e.target.closest('.sidebar,.dialog-form,#calendar-grid'))){
     e.preventDefault(); e.stopImmediatePropagation();
   }
 },true);
 const inhibitClick = () => {blockClicksUntil=clock()+CLICK_GUARD;};
 const scrollTargets = [...document.querySelectorAll('.sidebar,.dialog-form')];
 const scrollState = new WeakMap();
 const scrollHandler = {
   start(el, x, y, id, source) {
     scrollState.set(el,{startX:x,startY:y,lastY:y,startScroll:el.scrollTop,
                        moved:false,id,source,lastAt:clock()});
   },
   move(el,x,y,id,source,ev) {
     const g=scrollState.get(el); if(!g||g.id!==id||g.source!==source)return;
     if(!g.moved && Math.abs(y-g.startY)<MIN_SCROLL)return;
     // A finger's vertical displacement moves the panel in the opposite direction.
     if(!g.moved && Math.abs(y-g.startY)<Math.abs(x-g.startX)*1.1)return;
     g.moved=true;
     el.scrollTop=g.startScroll+(g.startY-y);
     g.lastY=y;
     if(ev?.cancelable)ev.preventDefault();
     inhibitClick();
   },
   end(el,id,source){const g=scrollState.get(el);if(g&&g.id===id&&g.source===source){
     if(g.moved)inhibitClick();scrollState.delete(el);
   }}
 };
 let nativeTouchInProgress=false;
 const mouseScroll=new Map();
 for(const el of scrollTargets){
   // Native touch controllers: this branch is the source of truth.
   el.addEventListener('touchstart',e=>{
      if(e.touches.length!==1 || interactive(e.target))return;
      const t=e.touches[0];nativeTouchInProgress=true;mouseScroll.clear();scrollHandler.start(el,t.clientX,t.clientY,t.identifier,'touch');
   },{passive:true});
   el.addEventListener('touchmove',e=>{
      if(e.touches.length!==1)return;
      const t=e.touches[0];scrollHandler.move(el,t.clientX,t.clientY,t.identifier,'touch',e);
   },{passive:false});
   for(const type of ['touchend','touchcancel'])el.addEventListener(type,e=>{
      for(const t of e.changedTouches)scrollHandler.end(el,t.identifier,'touch');nativeTouchInProgress=false;
   },{passive:true});
   // USB touchscreens may report mouse or pen pointer events rather than touch.
   el.addEventListener('pointerdown',e=>{
      if(interactive(e.target)||e.isPrimary===false|| (e.pointerType==='mouse'&&e.button!==0))return;
      scrollHandler.start(el,e.clientX,e.clientY,e.pointerId,'pointer');
      mouseScroll.set(e.pointerId,el);
   });
 }
 // Attach pointer movement to the document: it still works when the finger
 // moves over cards, buttons or exits the right-hand sidebar.
 document.addEventListener('pointermove',e=>{
    const el=mouseScroll.get(e.pointerId);if(!el||nativeTouchInProgress)return;
    if(e.pointerType==='mouse' && !(e.buttons&1))return;
    scrollHandler.move(el,e.clientX,e.clientY,e.pointerId,'pointer',e);
 },{passive:false});
 for(const type of ['pointerup','pointercancel'])document.addEventListener(type,e=>{
    const el=mouseScroll.get(e.pointerId);if(el){scrollHandler.end(el,e.pointerId,'pointer');mouseScroll.delete(e.pointerId);}
 });
 // Calendar swipes: left for next month, right for previous; works in week view.
 const calendar=document.getElementById('calendar-grid');
 if(!calendar)return;
 let swipe=null;
 const begin=(x,y,id,source)=>{swipe={x,y,id,source,at:clock()}};
 const finish=(x,y,id,source,e)=>{
   const g=swipe;if(!g||g.id!==id||g.source!==source)return;
   swipe=null;
   const dx=x-g.x,dy=y-g.y;
   if(Math.abs(dx)<MIN_SWIPE||Math.abs(dx)<Math.abs(dy)*1.35||clock()-g.at>2000)return;
   if(e?.cancelable)e.preventDefault();inhibitClick();
   const button=document.getElementById(dx<0?'next':'prev');
   if(button)button.click();
 };
 calendar.addEventListener('touchstart',e=>{
    if(e.touches.length===1&&!interactive(e.target)){
      const t=e.touches[0];begin(t.clientX,t.clientY,t.identifier,'touch');
    }
 },{passive:true});
 calendar.addEventListener('touchmove',e=>{
    if(!swipe||swipe.source!=='touch'||e.touches.length!==1)return;
    const t=e.touches[0];
    if(Math.abs(t.clientX-swipe.x)>MIN_SCROLL && Math.abs(t.clientX-swipe.x)>Math.abs(t.clientY-swipe.y)*1.2){
      if(e.cancelable)e.preventDefault();
    }
 },{passive:false});
 calendar.addEventListener('touchend',e=>{
   for(const t of e.changedTouches)finish(t.clientX,t.clientY,t.identifier,'touch',e);
 },{passive:false});
 calendar.addEventListener('touchcancel',()=>{swipe=null});
 calendar.addEventListener('pointerdown',e=>{
   if(e.isPrimary===false||(e.pointerType==='mouse'&&e.button!==0))return;
   begin(e.clientX,e.clientY,e.pointerId,'pointer');
 });
 document.addEventListener('pointerup',e=>{
    if(swipe?.source==='pointer')finish(e.clientX,e.clientY,e.pointerId,'pointer',e);
 });
 document.addEventListener('pointercancel',e=>{if(swipe?.source==='pointer'&&swipe.id===e.pointerId)swipe=null});
})();
