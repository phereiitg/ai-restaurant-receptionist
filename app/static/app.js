const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const INDIA = 'Asia/Kolkata';
const today = () => new Intl.DateTimeFormat('en-CA',{timeZone:INDIA,year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
const state = {overview: null, sessionId:null, recorder:null, chunks:[], recording:false, busy:false, calendarDate:today(), calendarView:'day', reservations:[], selectedReservation:null};
function toast(message, error=false) { const t=$('toast');t.textContent=message;t.className='toast show'+(error?' error':'');clearTimeout(toast.timer);toast.timer=setTimeout(()=>t.classList.remove('show'),4500); }
async function api(url, opts={}, admin=true) {
  const headers = {...(opts.headers||{})};
  if (admin) headers['X-Admin-Token']=sessionStorage.getItem('atithi_admin_token')||'';
  const r = await fetch(url,{...opts,headers});
  const ct=r.headers.get('content-type')||'';
  const body=ct.includes('json')?await r.json():{error: await r.text()};
  if(!r.ok)throw new Error(body.error||body.detail||`Request failed (${r.status})`);
  return body;
}
const sendJSON=(url,data,method='POST',admin=true)=>api(url,{method,headers:{'Content-Type':'application/json'},body:JSON.stringify(data)},admin);
function show(section) {
  document.querySelectorAll('.page').forEach(p=>p.classList.toggle('active',p.id==='section-'+section));
  document.querySelectorAll('.nav-item').forEach(b=>b.classList.toggle('active',b.dataset.section===section));
  $('current-section').textContent=({'overview':'Overview','reservations':'Reservations','floor':'Floor & service','calls':'Calls & requests','voice':'Voice studio','menu':'Menu'})[section]||section;
  location.hash=section;
  if(section==='reservations'&&state.overview)loadCalendar();
}
function miniTable(t){return `<div class="table-mini ${esc(t.floor_status)}"><strong>${esc(t.id)}</strong><small>${t.seats} guests</small></div>`;}
function renderOverview(d){
  $('kpi-bookings').textContent=d.reservation_count;
  $('kpi-calls').textContent=d.call_count;
  $('kpi-tasks').textContent=d.open_tasks;
  $('kpi-ready').textContent=d.tables.filter(t=>t.floor_status==='ready').length+'/'+d.tables.length;
  $('overview-map').innerHTML=d.tables.map(miniTable).join('');
  let recent=d.reservations.filter(r=>r.status==='confirmed').slice(0,5);
  $('recent-bookings').innerHTML=recent.length?recent.map(r=>`<div class="compact-item"><div><strong>${esc(r.guest_name)}</strong><small>${esc(r.id)} · ${esc(r.party_size)} guests · ${esc(r.booking_date)}</small></div><span class="time-chip">${esc(r.booking_time)}</span></div>`).join(''):'<div class="empty">No reservations recorded yet.</div>';
}
function renderReservations(d){
  const search=$('booking-search').value.toLowerCase(),filter=$('booking-filter').value;
  const rows=d.reservations.filter(r=>(filter==='all'||r.status===filter)&&`${r.guest_name} ${r.id} ${r.phone}`.toLowerCase().includes(search));
  $('reservation-list').innerHTML=rows.length?rows.map(r=>`<div class="ledger-item"><div class="ledger-main"><strong>${esc(r.guest_name)} <span class="status-chip ${esc(r.status)}">${esc(r.status)}</span></strong><p>${esc(r.id)} · ${esc(r.table_id)} · ${esc(r.party_size)} guests<br>${esc(r.booking_date)} at ${esc(r.booking_time)} · ${esc(r.source)}</p></div><div class="ledger-right">${r.status==='confirmed'?`<button class="text-btn cancel-booking" data-id="${esc(r.id)}">Cancel</button>`:''}</div></div>`).join(''):'<div class="empty">No matching reservations.</div>';
}
const dateObj=(value)=>{const [y,m,d]=value.split('-').map(Number);return new Date(y,m-1,d);};
const dateISO=(date)=>`${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}-${String(date.getDate()).padStart(2,'0')}`;
const addDays=(date,n)=>{const next=new Date(date);next.setDate(next.getDate()+n);return next;};
const dateLabel=(value,options={weekday:'short',month:'short',day:'numeric'})=>dateObj(value).toLocaleDateString('en-IN',options);
function visibleRange(){const current=dateObj(state.calendarDate);if(state.calendarView==='day')return[state.calendarDate,state.calendarDate];if(state.calendarView==='week'){const first=addDays(current,-((current.getDay()+6)%7));return[dateISO(first),dateISO(addDays(first,6))];}const first=addDays(new Date(current.getFullYear(),current.getMonth(),1),-((new Date(current.getFullYear(),current.getMonth(),1).getDay()+6)%7));return[dateISO(first),dateISO(addDays(first,41))];}
function minutesOf(time){const [h,m]=time.split(':').map(Number);return h*60+m;}
function endTime(r){const end=minutesOf(r.booking_time)+Number(r.duration_min||90);return`${String(Math.floor(end/60)%24).padStart(2,'0')}:${String(end%60).padStart(2,'0')}`;}
function eventMarkup(r,extra=''){return`<button type="button" class="calendar-event ${r.status==='cancelled'?'is-cancelled':''} ${extra}" data-reservation-id="${esc(r.id)}" aria-label="${esc(r.guest_name)}, ${esc(r.party_size)} guests, ${esc(r.booking_time)} to ${esc(endTime(r))}, table ${esc(r.table_id)}, ${esc(r.status)}"><strong>${esc(r.booking_time)}–${esc(endTime(r))} · ${esc(r.guest_name)}</strong><span>${esc(r.party_size)} guests · ${esc(r.table_id)} · ${esc(r.source)}${r.status==='cancelled'?' · Cancelled':''}</span></button>`;}
function timeSlots(date,tableId=''){return Array.from({length:11},(_,hour)=>`<button type="button" class="calendar-slot" data-date="${date}" data-time="${String(hour+11).padStart(2,'0')}:00" data-table-id="${esc(tableId)}" aria-label="New reservation ${String(hour+11).padStart(2,'0')}:00 on ${date}${tableId?` at ${tableId}`:''}"></button>`).join('');}
function positionedEvent(r,extra){const top=(minutesOf(r.booking_time)-660)/660*100,height=Math.max(4,Number(r.duration_min||90)/660*100);return eventMarkup(r,extra).replace('class="calendar-event',`style="top:${top}%;height:${height}%;" class="calendar-event`);}
function dayEvent(r){const start=minutesOf(r.booking_time)-660,duration=Number(r.duration_min||90);return eventMarkup(r,'day-event').replace('class="calendar-event',`style="left:${start/660*100}%;width:${duration/660*100}%;top:2px;height:54px;" class="calendar-event`);}
function weekEventsForDay(rows){const sorted=[...rows].sort((a,b)=>a.booking_time.localeCompare(b.booking_time));const ends=[];const assignments=sorted.map(r=>{const start=minutesOf(r.booking_time),end=start+Number(r.duration_min||90);let lane=ends.findIndex(value=>value<=start);if(lane<0)lane=ends.length;ends[lane]=end;return{r,lane,start,end};});const width=100/Math.max(1,ends.length);return assignments.map(({r,lane,start,end})=>eventMarkup(r,'week-event').replace('class="calendar-event',`style="top:${(start-660)/660*100}%;height:${Math.max(4,(end-start)/660*100)}%;left:${lane*width}%;width:${width}%;" class="calendar-event`)).join('');}
function renderDayCalendar(reservations,tables){const date=state.calendarDate,hours=Array.from({length:11},(_,i)=>`<div class="time-label">${String(i+11).padStart(2,'0')}:00</div>`).join('');const lanes=tables.map(t=>{const events=reservations.filter(r=>r.booking_date===date&&r.table_id===t.id).map(dayEvent).join('');return`<div class="day-table-row"><div class="day-table-label"><strong>${esc(t.id)}</strong><small>${t.seats} seats · ${esc(t.floor_status)}</small></div><div class="day-table-lane">${timeSlots(date,t.id)}${events}</div></div>`;}).join('');return`<div class="day-calendar-scroll"><div class="day-calendar"><div class="time-axis">${hours}</div>${lanes||'<div class="empty">No tables are configured.</div>'}</div></div>`;}
function renderWeekCalendar(reservations){const current=dateObj(state.calendarDate),monday=addDays(current,-((current.getDay()+6)%7));const days=Array.from({length:7},(_,i)=>dateISO(addDays(monday,i)));return`<div class="week-calendar"><div class="week-time-axis">${Array.from({length:12},(_,i)=>`<div class="time-label">${String(i+11).padStart(2,'0')}:00</div>`).join('')}</div>${days.map(date=>{const events=weekEventsForDay(reservations.filter(r=>r.booking_date===date));return`<div class="week-day"><button class="week-day-heading" data-date="${date}">${esc(dateLabel(date,{weekday:'short',day:'numeric'}))}</button><div class="week-day-body">${timeSlots(date)}${events}</div></div>`;}).join('')}</div>`;}
function renderMonthCalendar(reservations){const current=dateObj(state.calendarDate),first=new Date(current.getFullYear(),current.getMonth(),1),start=addDays(first,-((first.getDay()+6)%7));return`<div class="month-calendar">${['Mon','Tue','Wed','Thu','Fri','Sat','Sun'].map(d=>`<div class="month-weekday">${d}</div>`).join('')}${Array.from({length:42},(_,i)=>{const date=dateISO(addDays(start,i)),sameMonth=dateObj(date).getMonth()===current.getMonth(),events=reservations.filter(r=>r.booking_date===date);return`<div class="month-day ${sameMonth?'':'outside-month'}"><button class="month-date" data-date="${date}" aria-label="New reservation on ${date}">${dateObj(date).getDate()}</button><div class="month-events">${events.slice(0,4).map(r=>eventMarkup(r,'month-event')).join('')}${events.length>4?`<small>+${events.length-4} more</small>`:''}</div></div>`;}).join('')}</div>`;}
function renderCalendar(){if(!state.overview)return;const[start,end]=visibleRange(),tables=state.overview.tables||[];$('calendar-title').textContent=state.calendarView==='month'?dateObj(state.calendarDate).toLocaleDateString('en-IN',{month:'long',year:'numeric'}):start===end?dateLabel(start,{weekday:'long',month:'long',day:'numeric',year:'numeric'}):`${dateLabel(start)} – ${dateLabel(end)}`;$('calendar-table-legend').innerHTML=tables.map(t=>`<span class="table-capacity-chip"><strong>${esc(t.id)}</strong> ${t.seats} seats</span>`).join('');$('calendar-grid').innerHTML=state.calendarView==='day'?renderDayCalendar(state.reservations,tables):state.calendarView==='week'?renderWeekCalendar(state.reservations):renderMonthCalendar(state.reservations);document.querySelectorAll('.calendar-view').forEach(b=>b.classList.toggle('active',b.dataset.view===state.calendarView));}
async function loadCalendar(){if(!state.overview)return;const[start,end]=visibleRange();try{const data=await api(`/api/admin/reservations/range?start_date=${encodeURIComponent(start)}&end_date=${encodeURIComponent(end)}`);state.reservations=data.reservations;renderCalendar();}catch(e){toast(`Calendar could not be refreshed: ${e.message}`,true);}}
function renderFloor(d){
 $('floor-grid').innerHTML=d.tables.map(t=>`<div class="floor-card ${esc(t.floor_status)}"><div class="table-mark">${esc(t.id)}</div><small>Seats ${t.seats} guests</small><label><small>Current status</small><select class="table-state" data-id="${esc(t.id)}">${['ready','occupied','dirty','blocked'].map(s=>`<option value="${s}" ${s===t.floor_status?'selected':''}>${s==='dirty'?'Needs cleaning':s[0].toUpperCase()+s.slice(1)}</option>`).join('')}</select></label></div>`).join('');
}
function renderCalls(d){
 $('call-list').innerHTML=d.calls.length?d.calls.map(c=>`<div class="ledger-item"><div class="ledger-main"><strong>${esc(c.source)} session</strong><p>${esc(c.id)}<br>${esc(c.created_at.slice(0,16).replace('T',' '))} · ${esc(c.last_intent||'no intent yet')}</p></div><button class="link-button open-call" data-id="${esc(c.id)}">Open ↗</button></div>`).join(''):'<div class="empty">No call activity yet. Open Voice Studio to begin.</div>';
 $('task-list').innerHTML=d.tasks.length?d.tasks.map(t=>`<div class="ledger-item"><div class="ledger-main"><strong>${esc(t.title)} <span class="status-chip ${esc(t.status)}">${esc(t.status)}</span></strong><p>${esc(t.notes)}<br>${esc(t.id)}</p></div>${t.status==='open'?`<button class="link-button complete-task" data-id="${esc(t.id)}">Mark done ↗</button>`:''}</div>`).join(''):'<div class="empty">No manager requests yet.</div>';
}
function renderMenu(d){
 const groups={};d.menu.forEach(m=>(groups[m.category]??=[]).push(m));
 $('menu-groups').innerHTML=Object.entries(groups).map(([category,rows])=>`<article class="panel"><h2 class="menu-heading">${esc(category)}</h2>${rows.map(m=>`<div class="menu-row"><div><strong>${esc(m.name)}${!m.available?' · Unavailable':''}</strong><p>${esc(m.description)}</p></div><span class="menu-price">₹${m.price_inr}</span></div>`).join('')}</article>`).join('');
}
function sourceLabel(r){if(r.source==='manager')return'Manager-created';if(r.source==='voice')return'Voice-created · Browser microphone';if(r.source==='twilio')return'Voice-created · Twilio';if(r.source==='browser')return'Browser conversation';return esc(r.source||'Unknown');}
function tableOptions(selected=''){const select=$('calendar-booking-form').elements.table_id;select.innerHTML='<option value="">Automatic assignment</option>'+((state.overview?.tables)||[]).map(t=>`<option value="${esc(t.id)}">${esc(t.id)} · ${t.seats} seats · ${esc(t.floor_status)}</option>`).join('');select.value=selected;}
function openNewReservation(date=state.calendarDate,time='20:00',tableId=''){const form=$('calendar-booking-form');form.reset();form.elements.reservation_id.value='';form.elements.date.value=date;form.elements.time.value=time;form.elements.party_size.value='2';tableOptions(tableId);$('reservation-detail').hidden=true;$('reservation-actions').hidden=true;form.hidden=false;$('reservation-dialog-title').textContent='New reservation';$('reservation-save').textContent='Create reservation';$('reservation-form-error').hidden=true;$('reservation-dialog').showModal();form.elements.guest_name.focus();}
function showReservationDetails(r){state.selectedReservation=r;const form=$('calendar-booking-form');form.hidden=true;$('reservation-actions').hidden=r.status!=='confirmed';$('reservation-detail').hidden=false;$('reservation-detail').innerHTML=`<div class="detail-id">${esc(r.id)}</div><dl><dt>Guest</dt><dd>${esc(r.guest_name)}</dd><dt>Party size</dt><dd>${esc(r.party_size)} guests</dd><dt>Table</dt><dd>${esc(r.table_id)} · ${esc((state.overview.tables.find(t=>t.id===r.table_id)||{}).seats??'—')} seats</dd><dt>Time</dt><dd>${esc(r.booking_date)} · ${esc(r.booking_time)}–${esc(endTime(r))} IST</dd><dt>Duration</dt><dd>${esc(r.duration_min)} minutes</dd><dt>Source</dt><dd>${sourceLabel(r)}</dd><dt>Notes</dt><dd>${esc(r.notes||'None')}</dd><dt>Status</dt><dd><span class="status-chip ${esc(r.status)}">${esc(r.status)}</span></dd></dl>`;$('reservation-dialog-title').textContent='Reservation';$('reservation-form-error').hidden=true;$('reservation-dialog').showModal();}
function openReservation(id){const r=state.reservations.find(item=>item.id===id);if(r)showReservationDetails(r);}
function editSelectedReservation(){const r=state.selectedReservation;if(!r||r.status!=='confirmed')return;const form=$('calendar-booking-form');form.elements.reservation_id.value=r.id;form.elements.guest_name.value=r.guest_name;form.elements.party_size.value=String(r.party_size);form.elements.date.value=r.booking_date;form.elements.time.value=r.booking_time;form.elements.notes.value=r.notes||'';tableOptions(r.table_id);$('reservation-detail').hidden=true;$('reservation-actions').hidden=true;form.hidden=false;$('reservation-dialog-title').textContent='Modify reservation';$('reservation-save').textContent='Save changes';form.elements.guest_name.focus();}
async function submitCalendarReservation(event){event.preventDefault();const form=event.currentTarget;if(!form.reportValidity())return;const values=Object.fromEntries(new FormData(form));const rid=values.reservation_id;const payload={guest_name:values.guest_name,party_size:Number(values.party_size),date:values.date,time:values.time,phone:values.phone||'',notes:values.notes||'',table_id:values.table_id||null};const button=$('reservation-save');button.disabled=true;$('reservation-form-error').hidden=true;try{const result=rid?await sendJSON(`/api/admin/reservations/${encodeURIComponent(rid)}`,payload,'PATCH'):await sendJSON('/api/admin/reservations',payload);$('reservation-dialog').close();toast(rid?`Reservation ${result.id} updated`:`Reservation ${result.id} confirmed at ${result.table_id}`);await load();}catch(error){$('reservation-form-error').textContent=error.message;$('reservation-form-error').hidden=false;}finally{button.disabled=false;}}
async function cancelSelectedReservation(){const r=state.selectedReservation;if(!r||r.status!=='confirmed'||!confirm(`Cancel reservation ${r.id}?`))return;const button=$('reservation-cancel');button.disabled=true;try{await api(`/api/admin/reservations/${encodeURIComponent(r.id)}/cancel`,{method:'POST'});$('reservation-dialog').close();toast('Reservation cancelled');await load();}catch(error){$('reservation-form-error').textContent=error.message;$('reservation-detail').appendChild($('reservation-form-error'));$('reservation-form-error').hidden=false;}finally{button.disabled=false;}}
async function load(){
 try{const d=await api('/api/admin/overview');state.overview=d;renderOverview(d);renderFloor(d);renderCalls(d);renderMenu(d);$('backend-status').textContent='Backend connected';if($('section-reservations').classList.contains('active'))await loadCalendar();}
 catch(e){if(String(e.message).includes('token')||String(e.message).includes('401'))$('login').classList.remove('hidden');else toast(e.message,true);}
}
function newBooking(){show('reservations');openNewReservation(today(),'20:00');}
function initializeEvents(){
 document.querySelectorAll('.nav-item').forEach(b=>b.addEventListener('click',()=>show(b.dataset.section)));
 document.querySelectorAll('[data-action]').forEach(b=>b.addEventListener('click',()=>{const a=b.dataset.action;if(a==='new-booking')newBooking();if(a==='go-floor')show('floor');if(a==='go-reservations')show('reservations');if(a==='go-voice')show('voice');}));
 $('refresh-btn').addEventListener('click',()=>load());
 $('login-form').addEventListener('submit',async(e)=>{e.preventDefault();sessionStorage.setItem('atithi_admin_token',$('admin-key').value);try{await api('/api/admin/overview');$('login').classList.add('hidden');await load();}catch(error){toast('Manager token rejected',true);}});
 $('calendar-new').addEventListener('click',()=>openNewReservation());
 $('calendar-prev').addEventListener('click',()=>moveCalendar(-1));
 $('calendar-next').addEventListener('click',()=>moveCalendar(1));
 $('calendar-today').addEventListener('click',()=>{state.calendarDate=today();if(state.overview)loadCalendar();});
 document.querySelectorAll('.calendar-view').forEach(button=>button.addEventListener('click',()=>{state.calendarView=button.dataset.view;if(state.overview)loadCalendar();}));
 $('calendar-booking-form').addEventListener('submit',submitCalendarReservation);
 $('dialog-close').addEventListener('click',()=>$('reservation-dialog').close());
 $('reservation-edit').addEventListener('click',editSelectedReservation);
 $('reservation-cancel').addEventListener('click',cancelSelectedReservation);
 document.body.addEventListener('click',async(e)=>{
   const event=e.target.closest('.calendar-event');
   if(event){openReservation(event.dataset.reservationId);return;}
   const slot=e.target.closest('.calendar-slot');
   if(slot){openNewReservation(slot.dataset.date,slot.dataset.time,slot.dataset.tableId);return;}
   const dateButton=e.target.closest('.month-date,.week-day-heading');
   if(dateButton){openNewReservation(dateButton.dataset.date,'20:00');return;}
   const cancel=e.target.closest('.cancel-booking');
   if(cancel){if(!confirm(`Cancel booking ${cancel.dataset.id}?`))return;try{await api(`/api/admin/reservations/${encodeURIComponent(cancel.dataset.id)}/cancel`,{method:'POST'});toast('Reservation cancelled');await load();}catch(err){toast(err.message,true);}}
   const task=e.target.closest('.complete-task');
   if(task){try{await sendJSON(`/api/admin/tasks/${encodeURIComponent(task.dataset.id)}`,{status:'done'},'PATCH');toast('Task marked complete');await load();}catch(err){toast(err.message,true);}}
   const call=e.target.closest('.open-call');
   if(call){try{const d=await api(`/api/admin/calls/${encodeURIComponent(call.dataset.id)}/turns`);$('call-transcript').innerHTML=d.turns.map(t=>`<div class="transcript-row"><strong>${esc(t.role)}</strong>${esc(t.content)}</div>`).join('')||'No transcript available.';}catch(err){toast(err.message,true);}}
 });
 document.body.addEventListener('change',async(e)=>{
   const el=e.target.closest('.table-state');
   if(!el)return;
   try{await sendJSON(`/api/admin/tables/${el.dataset.id}`,{status:el.value},'PATCH');toast(`${el.dataset.id} marked ${el.value}`);await load();}catch(err){toast(err.message,true);}
 });
 $('chat-form').addEventListener('submit',async(e)=>{e.preventDefault();const message=$('chat-input').value.trim();if(!message)return;$('chat-input').value='';await sendText(message);});
 $('record-button').addEventListener('click',recordToggle);
 $('new-session').addEventListener('click',()=>{state.sessionId=null;$('conversation').innerHTML='<div class="intro-message">New conversation. You can now start with a booking or menu question.</div>';$('original-audio').hidden=true;$('reply-audio').hidden=true;toast('Started a new customer session');});
}
function moveCalendar(direction){const current=dateObj(state.calendarDate);if(state.calendarView==='day')current.setDate(current.getDate()+direction);else if(state.calendarView==='week')current.setDate(current.getDate()+7*direction);else{current.setDate(1);current.setMonth(current.getMonth()+direction);}state.calendarDate=dateISO(current);if(state.overview)loadCalendar();}
function setDateDefaults(){$('current-date').textContent=new Intl.DateTimeFormat('en-IN',{timeZone:INDIA,day:'numeric',month:'long',year:'numeric'}).format(new Date());}
function appendChat(role,message,label=''){
 const box=$('conversation');if(box.querySelector('.intro-message'))box.innerHTML='';
 const el=document.createElement('div');el.className='chat-bubble '+role;
 el.innerHTML=esc(message)+(label?`<small>${esc(label)}</small>`:'');box.appendChild(el);box.scrollTop=box.scrollHeight;
}
function processing(busy,text='Processing request…'){
 state.busy=busy;$('record-button').disabled=busy;$('chat-input').disabled=busy;$('turn-state').textContent=busy?text:'Ready for another turn';
}
async function sendText(message){
 if(state.busy)return;appendChat('user',message,'TEXT INPUT');processing(true,'Parsing intent and checking live database…');
 try{const r=await sendJSON('/api/chat/turn',{text:message,session_id:state.sessionId},'POST',false);state.sessionId=r.session_id;appendChat('assistant',r.reply,`${r.parser_mode.toUpperCase()} · ${r.action}`);await load();}
 catch(e){appendChat('assistant','Could not complete the turn: '+e.message,'ERROR');toast(e.message,true);}finally{processing(false);}
}
async function recordToggle(){
 if(state.recording){state.recorder.stop();state.recording=false;$('record-button').classList.remove('recording');$('mic-label').textContent='Transcribing your recording…';return;}
 if(state.busy)return;
 if(!navigator.mediaDevices?.getUserMedia){toast('Microphone requires HTTPS or localhost.',true);return;}
 try{
   const stream=await navigator.mediaDevices.getUserMedia({audio:true});
   const format=MediaRecorder.isTypeSupported('audio/webm')?'audio/webm':(MediaRecorder.isTypeSupported('audio/ogg')?'audio/ogg':'');
   state.chunks=[];state.recorder=new MediaRecorder(stream,format?{mimeType:format}:undefined);
   state.recorder.ondataavailable=e=>{if(e.data.size)state.chunks.push(e.data);};
   state.recorder.onstop=async()=>{stream.getTracks().forEach(t=>t.stop());const blob=new Blob(state.chunks,{type:state.recorder.mimeType});const audio=$('original-audio');audio.src=URL.createObjectURL(blob);audio.hidden=false;await sendVoice(blob);};
   state.recorder.start();state.recording=true;$('record-button').classList.add('recording');$('mic-label').textContent='Recording · tap to stop';
   setTimeout(()=>{if(state.recording)recordToggle();},25000);
 }catch(e){toast('Microphone unavailable: '+e.message,true);}
}
async function sendVoice(blob){
 processing(true,'Gnani Prisma → Gemini → reservations → Gnani Timbre…');
 const ext=(blob.type||'').includes('ogg')?'ogg':'webm';
 const f=new FormData();f.append('audio',blob,'utterance.'+ext);f.append('session_id',state.sessionId||'');
 try{
   const r=await api('/api/voice/turn',{method:'POST',body:f},false);
   state.sessionId=r.session_id;
   appendChat('user',r.user_text,`${r.stt_model} · ACTUAL TRANSCRIPT`);
   appendChat('assistant',r.reply,`${r.parser_mode.toUpperCase()} · ${r.action} · ${r.tts_status}`);
   $('mic-label').textContent='Tap to record another message';
   if(r.audio_url){const player=$('reply-audio');player.src=r.audio_url;player.hidden=false;player.play().catch(()=>{});}
   if(r.tts_error)toast('Text result succeeded, spoken reply unavailable: '+r.tts_error,true);
   await load();
 }catch(e){$('mic-label').textContent='Tap to retry recording';toast(e.message,true);appendChat('assistant','Voice processing failed: '+e.message,'NO FABRICATED TRANSCRIPT');}
 finally{processing(false);}
}
async function capabilities(){
 try{
 const c=await api('/api/capabilities',{},false);
 $('voice-provider').textContent=c.gnani_configured?'Gnani configured':'Gnani key missing';
 $('voice-provider').title=c.gemini_configured?'Gemini configured':'Limited rule-based parser available';
 }catch(e){$('voice-provider').textContent='Provider status unknown';}
}
(async function boot(){
 initializeEvents();setDateDefaults();
 const initial=location.hash.slice(1);if(['overview','reservations','floor','calls','voice','menu'].includes(initial))show(initial);
 await capabilities();if(sessionStorage.getItem('atithi_admin_token')){$('login').classList.add('hidden');await load();}
 setInterval(()=>{if(!$('login').classList.contains('hidden')&&false)return;if(document.visibilityState==='visible'&&$('login').classList.contains('hidden')&&!state.busy)load();},12000);
})();
