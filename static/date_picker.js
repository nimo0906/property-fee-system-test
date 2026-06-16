(function(){
  var activeInput=null,panel=null,viewDate=new Date(),mode='day';
  function pad(n){return String(n).padStart(2,'0')}
  function iso(d){return d.getFullYear()+'-'+pad(d.getMonth()+1)+'-'+pad(d.getDate())}
  function parse(v){var m=/^(\d{4})-(\d{2})-(\d{2})$/.exec(v||'');return m?new Date(+m[1],+m[2]-1,+m[3]):new Date()}
  function same(a,b){return a&&b&&a.getFullYear()==b.getFullYear()&&a.getMonth()==b.getMonth()&&a.getDate()==b.getDate()}
  function fire(el){el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}))}
  function enhance(input){
    if(input.dataset.pmDateReady)return; input.dataset.pmDateReady='1';
    var wrap=document.createElement('span');wrap.className='date-field-wrap';
    input.parentNode.insertBefore(wrap,input);wrap.appendChild(input);
    input.classList.add('pm-date-input');input.dataset.pmType='date';
    try{input.type='text'}catch(e){}
    input.placeholder=input.placeholder||'YYYY-MM-DD';input.inputMode='numeric';
    var btn=document.createElement('button');btn.type='button';btn.className='pm-date-trigger';btn.innerHTML='<i class="bi bi-calendar3"></i>';
    wrap.appendChild(btn);
    btn.addEventListener('click',function(e){e.preventDefault();open(input)});
    input.addEventListener('focus',function(){open(input)});
    input.addEventListener('keydown',function(e){if(e.key==='ArrowDown'){e.preventDefault();open(input)}if(e.key==='Escape')close()});
  }
  function ensurePanel(){if(panel)return panel;panel=document.createElement('div');panel.className='pm-date-panel';document.body.appendChild(panel);return panel}
  function open(input){activeInput=input;viewDate=parse(input.value);mode='day';render();place(input)}
  function close(){if(panel)panel.remove();panel=null;activeInput=null}
  function place(input){var r=input.getBoundingClientRect(),p=ensurePanel(),top=r.bottom+8,left=r.left;if(left+312>innerWidth)left=innerWidth-324;if(left<12)left=12;if(top+360>innerHeight)top=Math.max(12,r.top-360);p.style.left=left+'px';p.style.top=top+'px'}
  function setValue(d){if(!activeInput)return;activeInput.value=iso(d);fire(activeInput);close()}
  function render(){var p=ensurePanel();p.innerHTML=head()+body()+actions();bind(p);place(activeInput)}
  function head(){var y=viewDate.getFullYear(),m=viewDate.getMonth()+1;return '<div class="pm-date-head"><button class="pm-date-nav" data-act="prev">‹</button><button class="pm-date-mode" data-act="mode"><div class="pm-date-title">'+y+'年 '+m+'月</div><div class="pm-date-subtitle">点击切换年月</div></button><button class="pm-date-nav" data-act="next">›</button></div>'}
  function body(){return mode==='month'?months():mode==='year'?years():days()}
  function days(){var y=viewDate.getFullYear(),m=viewDate.getMonth(),first=new Date(y,m,1),start=new Date(y,m,1-first.getDay()),sel=parse(activeInput.value),today=new Date(),html='<div class="pm-date-week"><span>日</span><span>一</span><span>二</span><span>三</span><span>四</span><span>五</span><span>六</span></div><div class="pm-date-grid">';for(var i=0;i<42;i++){var d=new Date(start);d.setDate(start.getDate()+i);var cls='pm-date-day'+(d.getMonth()!=m?' muted':'')+(same(d,today)?' today':'')+(same(d,sel)?' selected':'');html+='<button class="'+cls+'" data-date="'+iso(d)+'">'+d.getDate()+'</button>'}return html+'</div>'}
  function months(){var sel=parse(activeInput.value),html='<div class="pm-date-months">';for(var i=0;i<12;i++){html+='<button class="pm-date-month '+(i===sel.getMonth()&&viewDate.getFullYear()===sel.getFullYear()?'selected':'')+'" data-month="'+i+'">'+(i+1)+'月</button>'}return html+'</div>'}
  function years(){var y=viewDate.getFullYear(),start=y-5,sel=parse(activeInput.value),html='<div class="pm-date-years">';for(var i=0;i<12;i++){var yy=start+i;html+='<button class="pm-date-year '+(yy===sel.getFullYear()?'selected':'')+'" data-year="'+yy+'">'+yy+'</button>'}return html+'</div>'}
  function actions(){return '<div class="pm-date-actions"><button data-quick="today">今天</button><button data-quick="start">本月初</button><button data-quick="end">本月末</button><button class="danger" data-quick="clear">清空</button></div>'}
  function bind(p){p.querySelectorAll('[data-act]').forEach(function(b){b.onclick=function(){var a=b.dataset.act;if(a==='mode'){mode=mode==='day'?'month':mode==='month'?'year':'day'}else{var n=a==='prev'?-1:1;if(mode==='year')viewDate.setFullYear(viewDate.getFullYear()+n*12);else if(mode==='month')viewDate.setFullYear(viewDate.getFullYear()+n);else viewDate.setMonth(viewDate.getMonth()+n)}render()}});p.querySelectorAll('[data-date]').forEach(function(b){b.onclick=function(){setValue(parse(b.dataset.date))}});p.querySelectorAll('[data-month]').forEach(function(b){b.onclick=function(){viewDate.setMonth(+b.dataset.month);mode='day';render()}});p.querySelectorAll('[data-year]').forEach(function(b){b.onclick=function(){viewDate.setFullYear(+b.dataset.year);mode='month';render()}});p.querySelectorAll('[data-quick]').forEach(function(b){b.onclick=function(){var d=new Date(),q=b.dataset.quick;if(q==='clear'){activeInput.value='';fire(activeInput);close();return}if(q==='start')d=new Date(d.getFullYear(),d.getMonth(),1);if(q==='end')d=new Date(d.getFullYear(),d.getMonth()+1,0);setValue(d)}})}
  document.addEventListener('DOMContentLoaded',function(){document.querySelectorAll('input[type="date"]').forEach(enhance)});
  document.addEventListener('mousedown',function(e){if(panel&&!panel.contains(e.target)&&!(e.target.closest&&e.target.closest('.date-field-wrap')))close()});
  window.addEventListener('resize',function(){if(activeInput)place(activeInput)});document.addEventListener('scroll',function(){if(activeInput)place(activeInput)},true);
})();
