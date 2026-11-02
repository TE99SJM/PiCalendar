/* Smoke tests for touch scrolling, emulated-mouse scrolling, and calendar swipes.
   Run: node tests/touch-gestures.test.cjs */
const fs=require('fs');
const vm=require('vm');
const assert=require('assert/strict');
class Elem {
  constructor(name){this.name=name;this.listeners={};this.scrollTop=0;this.scrollHeight=2400;this.clientHeight=400;this.presses=0}
  addEventListener(name,fn){(this.listeners[name]??=[]).push(fn)}
  dispatch(type,props={}){const e={type,target:this, cancelable:true,prevented:false,
    preventDefault(){this.prevented=true},stopImmediatePropagation(){},
    ...props};for(const fn of this.listeners[type]||[])fn(e);return e}
  closest(sel){return null}
  click(){this.presses++}
}
const sidebar=new Elem('sidebar'),form=new Elem('form'),calendar=new Elem('grid'),next=new Elem('next'),prev=new Elem('prev'),doc=new Elem('document');
const sandbox={document:doc,performance:{now:()=>Date.now()},console};
doc.querySelectorAll=sel=>sel==='.sidebar,.dialog-form'?[sidebar,form]:[];
doc.getElementById=id=>({next,prev,'calendar-grid':calendar})[id];
vm.runInNewContext(fs.readFileSync(require('path').join(__dirname,'../static/touch-gestures.js'),'utf8'),sandbox);
function touch(x,y,id=1){return {clientX:x,clientY:y,identifier:id}}
sidebar.dispatch('touchstart',{touches:[touch(50,300)]});
sidebar.dispatch('touchmove',{touches:[touch(50,140)]});
assert.equal(sidebar.scrollTop,160,'touch should move sidebar up');
sidebar.dispatch('touchend',{changedTouches:[touch(50,140)],touches:[]});
// HID device emulating a mouse, dispatched to document while dragging.
sidebar.dispatch('pointerdown',{pointerType:'mouse',isPrimary:true,button:0,pointerId:4,clientX:40,clientY:280});
doc.dispatch('pointermove',{pointerType:'mouse',buttons:1,pointerId:4,clientX:40,clientY:190});
doc.dispatch('pointerup',{pointerType:'mouse',pointerId:4,clientX:40,clientY:190});
assert.equal(sidebar.scrollTop,250,'mouse-emulated touchscreen should scroll');
calendar.dispatch('touchstart',{touches:[touch(300,170,7)]});
calendar.dispatch('touchmove',{touches:[touch(110,170,7)]});
calendar.dispatch('touchend',{changedTouches:[touch(110,170,7)],touches:[]});
assert.equal(next.presses,1,'swipe left should move forward');
calendar.dispatch('pointerdown',{pointerType:'mouse',isPrimary:true,button:0,pointerId:8,clientX:130,clientY:200});
doc.dispatch('pointerup',{pointerType:'mouse',pointerId:8,clientX:340,clientY:200});
assert.equal(prev.presses,1,'mouse swipe right should move backward');
console.log('4 gesture smoke tests passed');
