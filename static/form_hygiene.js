(function(){
  function hardenInput(input, idx){
    if(input.type==='hidden'||input.type==='checkbox'||input.type==='radio')return;
    input.setAttribute('autocomplete','off');
    if(input.name==='keyword'||input.name==='name'||input.placeholder){
      input.setAttribute('autocorrect','off');
      input.setAttribute('autocapitalize','off');
      input.setAttribute('spellcheck','false');
      input.setAttribute('data-lpignore','true');
      input.setAttribute('data-form-type','other');
      if(input.name==='keyword')input.setAttribute('name','keyword');
    }
    if(input.name==='name'){
      input.setAttribute('autocomplete','new-password');
    }
    if((input.name==='name'||input.name==='keyword')&&!input.id){
      input.id='pm_nohist_'+idx;
    }
  }
  function apply(){
    document.querySelectorAll('form').forEach(function(form){
      form.setAttribute('autocomplete','off');
    });
    document.querySelectorAll('input, textarea').forEach(hardenInput);
  }
  document.addEventListener('DOMContentLoaded',apply);
})();
