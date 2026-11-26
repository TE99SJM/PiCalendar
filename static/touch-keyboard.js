(() => {
  'use strict';
  // The regular browser on another device can use its own keyboard.
  if(window.parent===window && location.hostname!=='127.0.0.1')return;

  const editable='dialog[open] :is(input:not([type]),input[type="text"],input[type="number"],textarea):not([readonly]):not(:disabled)';
  const letters=['1234567890','qwertyuiop','asdfghjkl','zxcvbnm'];
  const symbols=['1234567890','@#$%&*()-_','+!?:";\'/=','[],.<>'];
  const numbers=['789','456','123','-0.'];
  const keyboard=document.createElement('div');
  keyboard.className='touch-keyboard';
  keyboard.setAttribute('role','group');
  keyboard.setAttribute('aria-label','On-screen keyboard');
  let field=null;
  let shifted=false;
  let showSymbols=false;

  function addKey(row,label,action='type'){
    const key=document.createElement('button');
    key.type='button';
    key.tabIndex=-1;
    key.textContent=label;
    key.dataset.action=action;
    row.append(key);
    return key;
  }

  function render(){
    keyboard.replaceChildren();
    const numeric=field.type==='number';
    keyboard.classList.toggle('touch-keyboard-numeric',numeric);
    const rows=numeric?numbers:showSymbols?symbols:letters;
    for(const characters of rows){
      const row=document.createElement('div');
      row.className='touch-keyboard-row';
      for(const char of characters)addKey(row,shifted?char.toUpperCase():char);
      keyboard.append(row);
    }
    const controls=document.createElement('div');
    controls.className='touch-keyboard-row touch-keyboard-controls';
    if(!numeric){
      const shift=addKey(controls,'Shift','shift');
      shift.disabled=showSymbols;
      shift.setAttribute('aria-pressed',String(shifted));
      addKey(controls,showSymbols?'ABC':'Symbols','symbols');
      addKey(controls,'Space','space');
      if(field.tagName==='TEXTAREA')addKey(controls,'Return','return');
    }
    addKey(controls,'Backspace','delete');
    addKey(controls,'Done','done');
    keyboard.append(controls);
  }

  function dismiss(){
    keyboard.remove();
    field=null;
  }

  function open(target){
    if(!target.matches(editable)||target===field)return;
    field=target;
    shifted=false;
    showSymbols=false;
    render();
    field.closest('dialog').append(keyboard);
    target.scrollIntoView({block:'nearest'});
  }

  // Keep the input focused so Chromium edits the actual caret or selection.
  keyboard.addEventListener('pointerdown',event=>event.preventDefault());
  keyboard.addEventListener('click',event=>{
    const key=event.target.closest('button');
    if(!key||!field?.matches(editable))return;
    field.focus({preventScroll:true});
    switch(key.dataset.action){
      case 'done': field.blur(); dismiss(); return;
      case 'shift': shifted=!shifted; render(); return;
      case 'symbols': showSymbols=!showSymbols; shifted=false; render(); return;
      case 'delete': document.execCommand('delete'); return;
      case 'space': document.execCommand('insertText',false,' '); return;
      case 'return': document.execCommand('insertText',false,'\n'); return;
      default:
        document.execCommand('insertText',false,key.textContent);
        if(shifted){shifted=false;render();}
    }
  });

  document.addEventListener('click',event=>{
    const target=event.target.closest('label')?.control||event.target;
    if(target.matches(editable))open(target);
    // Keep the dialog in place until a tap on Close, Save, or a picker lands.
    else if(!event.composedPath().includes(keyboard))dismiss();
  },true);
  document.addEventListener('close',event=>{
    if(event.target===keyboard.parentElement&&!event.target.open)dismiss();
  },true);
})();
