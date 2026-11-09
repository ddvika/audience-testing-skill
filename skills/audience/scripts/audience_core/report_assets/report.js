(()=>{
'use strict';
let DATA;try{DATA=JSON.parse(document.getElementById('report-data').textContent)}catch{return}
const reduced=matchMedia('(prefers-reduced-motion: reduce)');
const motion=(el,frames,options={})=>{if(!reduced.matches&&el?.animate)return el.animate(frames,{duration:420,easing:'cubic-bezier(.2,.65,.2,1)',...options})};
reduced.addEventListener?.('change',()=>{if(reduced.matches)document.getAnimations?.().forEach(a=>a.cancel())});
const number=v=>typeof v==='number'&&Number.isFinite(v)?new Intl.NumberFormat('ru-RU',{maximumFractionDigits:1}).format(v):'—';
const text=(tag,cls,value)=>{const el=document.createElement(tag);if(cls)el.className=cls;el.textContent=value??'';return el};
document.getElementById('print-report')?.addEventListener('click',()=>print());
document.querySelectorAll('[data-download-dialogues]').forEach(button=>{
 if(!DATA.dialogues?.length)return;
 button.hidden=false;
 button.addEventListener('click',()=>{
  const kind=button.dataset.downloadDialogues,items=DATA.dialogues;
  const contents=kind==='json'?JSON.stringify({schema_version:'1.0',description:'Сохранённые сообщения AI-агентов и продукта',dialogues:items},null,2):items.map(d=>[
   d.name+' · '+d.group,'Сессия: '+d.id,'Задача: '+d.goal,'Модель: '+d.model,'Статус: '+d.status,
   d.conversation_url?'Исходный чат: '+d.conversation_url:'',d.capture_note,'',
   ...d.messages.map(m=>(m.role==='user'?'ЗАПРОС AI-АГЕНТА':'ОТВЕТ ПРОДУКТА')+'\n'+m.text+'\n')
  ].filter(v=>v!==null&&v!==undefined).join('\n')).join('\n\n────────────\n\n');
  const blob=new Blob([contents],{type:kind==='json'?'application/json;charset=utf-8':'text/plain;charset=utf-8'}),url=URL.createObjectURL(blob),link=document.createElement('a');
  link.href=url;link.download='Audience-dialogues.'+kind;document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
 });
});
document.querySelectorAll('[data-board]').forEach(button=>button.addEventListener('click',()=>{
 document.querySelectorAll('[data-board]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));
 document.querySelectorAll('[data-agent-group]').forEach(p=>{p.classList.toggle('selected',p.dataset.agentGroup===button.dataset.board)});
 document.getElementById('board-caption').textContent=button.dataset.caption;
}));
const titles={first_use:'Решили первую задачу',repeat:'Решили задачу при повторном визите',choose_again:'Выбрали бы продукт снова'};
const notes={first_use:'Первый визит каждой персоны. Технические ошибки, блокировки, незавершённые запуски и лимит бюджета показаны отдельно; это не отказ пользователя.',repeat:'Модельные повторные визиты с сохранённым контекстом. Это выполнение следующей задачи, а не D7 или D30 retention.',choose_again:'Последний допустимый ответ каждого AI-агента. Намерение вернуться не является реальным удержанием пользователей.'};
document.querySelectorAll('[data-measure]').forEach(button=>button.addEventListener('click',()=>{
 const key=button.dataset.measure;
 document.querySelectorAll('[data-measure]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));
 document.getElementById('audience-chart-title').textContent=titles[key];
 document.getElementById('audience-chart-note').textContent=notes[key];
 document.querySelectorAll('[data-chart-group]').forEach(row=>{
  const m=DATA.audience[Number(row.dataset.chartGroup)]?.[key]||{}, n=m.n||0, value=key==='choose_again'?m.yes:m.success;
  row.querySelector('[data-chart-count]').textContent=n?number(value):'—';
  row.querySelector('[data-chart-denominator]').textContent=n?' / '+number(n):'нет оценки';
  row.querySelector('[data-chart-unknown]').textContent='Без оценки: '+number(m.unknown||0);
  const bar=row.querySelector('.bar-track i');bar.getAnimations?.().forEach(a=>a.cancel());bar.style.transform='scaleX('+(n?Math.max(0,Math.min(1,value/n)):0)+')';
 });
}));
const rateKeys=new Set(['return_rate','activation','activation_rate','d7_retention','d30_retention','stickiness']);
const forecastValue=(key,v)=>typeof v==='number'&&Number.isFinite(v)?(rateKeys.has(key)?number(v*100)+'%':number(v)):'—';
document.querySelectorAll('[data-forecast]').forEach(button=>button.addEventListener('click',()=>{
 const scenario=DATA.forecast?.named_scenarios?.[Number(button.dataset.forecast)];if(!scenario)return;
 document.querySelectorAll('[data-forecast]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));
 const metrics=scenario.metrics||{},baseline=DATA.forecast?.baseline?.metrics||{};
 document.querySelectorAll('[data-forecast-metric]').forEach(row=>{const key=row.dataset.forecastMetric;row.querySelector('[data-forecast-after]').textContent=forecastValue(key,metrics[key]?.value);const unit=row.querySelector('[data-forecast-unit]');if(unit)unit.textContent=metrics[key]?.unit||''});
 const bar=document.getElementById('forecast-bar'),percent=document.getElementById('forecast-percent'),delta=document.getElementById('forecast-delta');
 if(bar){const rate=metrics.activation_rate?.value;bar.getAnimations?.().forEach(a=>a.cancel());bar.style.transform='scaleX('+(Number.isFinite(rate)?Math.max(0,Math.min(1,rate)):0)+')';percent.textContent=forecastValue('activation_rate',rate)}
 if(delta){const before=baseline.activated_users?.value,after=metrics.activated_users?.value;delta.textContent=Number.isFinite(before)&&Number.isFinite(after)?((after-before>0?'+':'')+number(after-before)):'—'}
}));
const dialog=document.getElementById('person-dialog');let previousFocus=null;
function showPerson(index){
 const person=DATA.people[index];if(!person||!dialog)return;
 previousFocus=document.activeElement;
 document.getElementById('person-title').textContent=person.name||person.id;
 document.getElementById('person-goal').textContent=person.goal||'Задача не сохранена.';
 document.getElementById('person-meta').textContent=[person.group_label,person.device==='mobile'?'Телефон':person.device==='desktop'?'Компьютер':'',person.model].filter(Boolean).join(' · ');
 const target=document.getElementById('person-sessions');target.replaceChildren();
 for(const session of person.sessions||[]){const section=text('section','dialog-session','');section.append(text('h3','',session.mode+' · '+session.status),text('p','',session.summary||'Отзыв не записан.'));if(session.dialogue_anchor){const link=text('a','','Читать запрос и ответ ↘');link.href='#'+session.dialogue_anchor;link.addEventListener('click',()=>{dialog.close();const record=document.getElementById(session.dialogue_anchor);if(record)record.open=true});section.append(link)}target.append(section)}
 if(!person.sessions?.length)target.append(text('p','caption','Сессии ещё не запускались.'));
 if(typeof dialog.showModal==='function')dialog.showModal();else dialog.setAttribute('open','');
}
document.querySelectorAll('[data-person]').forEach(button=>button.addEventListener('click',()=>showPerson(Number(button.dataset.person))));
dialog?.querySelector('.dialog-close')?.addEventListener('click',()=>dialog.close());
dialog?.addEventListener('close',()=>previousFocus?.focus());
dialog?.addEventListener('click',e=>{const b=dialog.getBoundingClientRect();if(e.target===dialog&&(e.clientX<b.left||e.clientX>b.right||e.clientY<b.top||e.clientY>b.bottom))dialog.close()});
const search=document.getElementById('person-search');
search?.addEventListener('input',()=>{
 const term=search.value.trim().toLocaleLowerCase('ru'), target=document.getElementById('person-list');target.replaceChildren();let count=0,total=0;
 DATA.people.forEach((person,index)=>{
  if(term&&![person.name,person.id,person.goal,person.group_label].join(' ').toLocaleLowerCase('ru').includes(term))return;
  total++;if(count++>=60)return;
  const record=text('details','person-record',''), summary=text('summary','',person.name||person.id), body=text('div','details-body','');
  summary.append(text('span','',person.group_label));body.append(text('p','',person.goal||'Задача не сохранена.'),text('p','caption',person.model||''));
  const button=text('button','button secondary','Открыть все визиты');button.type='button';button.addEventListener('click',()=>showPerson(index));body.append(button);record.append(summary,body);target.append(record);
 });
 if(!total)target.append(text('p','caption','Агенты с таким именем или задачей не найдены.'));
 else if(total>60)target.append(text('p','caption','Найдено '+number(total)+'. Показаны первые 60 — уточните запрос.'));
});
function revealAncestors(target){let p=target;while(p){if(p.tagName==='DETAILS')p.open=true;p=p.parentElement}}
function openHash(){if(!location.hash)return;let id;try{id=decodeURIComponent(location.hash.slice(1))}catch{return}const target=document.getElementById(id);if(!target)return;revealAncestors(target);if(target.classList.contains('event-record'))target.scrollIntoView({behavior:reduced.matches?'auto':'smooth',block:'start'})}
document.querySelectorAll('[data-evidence-link]').forEach(link=>link.addEventListener('click',()=>{const target=document.getElementById(link.getAttribute('href').slice(1));if(target)revealAncestors(target)}));
addEventListener('hashchange',openHash);openHash();
let currentStep=0;
function setStory(index){index=Number(index);if(!Number.isInteger(index)||index<0||index>=DATA.story_count)return;const changed=index!==currentStep;currentStep=index;document.querySelectorAll('[data-scene]').forEach(scene=>{scene.hidden=Number(scene.dataset.scene)!==index;if(!scene.hidden&&changed)motion(scene,[{opacity:.4,transform:'translateY(8px)'},{opacity:1,transform:'translateY(0)'}],{duration:300})});const title=document.getElementById('story-index');if(title)title.textContent=String(index+1).padStart(2,'0')+' / '+String(DATA.story_count).padStart(2,'0');document.querySelectorAll('[data-story-jump]').forEach(a=>{if(Number(a.dataset.storyJump)===index)a.setAttribute('aria-current','step');else a.removeAttribute('aria-current')})}
document.querySelectorAll('[data-story-jump]').forEach(link=>link.addEventListener('click',()=>setStory(link.dataset.storyJump)));
if('IntersectionObserver' in window){
 const reveals=new IntersectionObserver(entries=>entries.forEach(e=>{if(!e.isIntersecting)return;motion(e.target,[{opacity:.5,transform:'translateY(16px)'},{opacity:1,transform:'translateY(0)'}]);reveals.unobserve(e.target)}),{threshold:.08});document.querySelectorAll('.reveal,.story-step').forEach(e=>reveals.observe(e));
 const bars=new IntersectionObserver(entries=>entries.forEach(e=>{if(!e.isIntersecting)return;e.target.querySelectorAll('.bar-track>i').forEach((bar,i)=>motion(bar,[{transform:'scaleX(0)'},{transform:bar.style.transform||'scaleX(1)'}],{duration:480,delay:Math.min(i*45,180)}));bars.unobserve(e.target)}),{threshold:.1});document.querySelectorAll('.audience-chart,.clarity-chart').forEach(e=>bars.observe(e));
 const story=new IntersectionObserver(entries=>{entries.filter(e=>e.isIntersecting).forEach(e=>setStory(e.target.dataset.step))},{rootMargin:'-30% 0px -42% 0px',threshold:0});document.querySelectorAll('[data-step]').forEach(e=>story.observe(e));
 const chapters=new IntersectionObserver(entries=>{const visible=entries.filter(e=>e.isIntersecting);if(!visible.length)return;const id=visible.at(-1).target.id;document.querySelectorAll('.nav-links a').forEach(a=>{if(a.hash==='#'+id)a.setAttribute('aria-current','location');else a.removeAttribute('aria-current')})},{rootMargin:'-18% 0px -65% 0px'});document.querySelectorAll('main>section[id]').forEach(e=>chapters.observe(e));
}
let scheduled=false,maxScroll=1;const progress=document.querySelector('.reading-progress i');
function drawProgress(){scheduled=false;if(progress)progress.style.transform='scaleX('+Math.max(0,Math.min(1,scrollY/maxScroll))+')'}
function onScroll(){if(!scheduled){scheduled=true;requestAnimationFrame(drawProgress)}}
function measurePage(){maxScroll=Math.max(1,document.documentElement.scrollHeight-innerHeight);onScroll()}
addEventListener('scroll',onScroll,{passive:true});addEventListener('resize',measurePage,{passive:true});if('ResizeObserver' in window)new ResizeObserver(measurePage).observe(document.body);measurePage();
document.documentElement.dataset.audienceReport='ready';
})();
