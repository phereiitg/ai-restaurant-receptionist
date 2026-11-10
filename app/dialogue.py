"""Bounded conversation coordinator. All state changes occur in Storage transactions."""
from __future__ import annotations
import json
import uuid
from dataclasses import dataclass
from .providers import interpret,ProviderFailure
from .storage import Storage,DomainError

@dataclass
class TurnResult:
    session_id: str
    user_text: str
    reply: str
    parser_mode: str
    action: str
    data: dict|None=None

class Dialogue:
    def __init__(self, store:Storage):self.store=store

    async def turn(self,text:str,session_id:str|None=None,source:str='browser',caller:str='')->TurnResult:
        text=text.strip()
        if not text or len(text)>2000:raise DomainError('Say a short restaurant request.')
        sid=session_id or 'CALL-'+uuid.uuid4().hex[:14].upper()
        call=self.store.create_call(sid,source=source,caller=caller)
        self.store.add_turn(sid,'user',text)
        history=self.store.turns(sid)
        pending=json.loads(call['pending_json']) if call['pending_json'] else None
        parsed,mode=await interpret(text,history,pending)
        self.store.update_call(sid,intent=parsed.intent)
        reply='';action='none';data=None
        try:
            if pending:
                kind=pending.get('kind')
                # Collect a missing name without committing any booking.
                if kind=='needs_name':
                    if parsed.confirmation=='no' and not parsed.party_size:
                        self.store.update_call(sid,pending={})
                        reply='No booking was made. What else can I help with?'
                        action='proposal_rejected'
                    elif parsed.party_size or parsed.date or parsed.time:
                        updated={**pending,'party_size':parsed.party_size or pending['party_size'],
                                 'date':parsed.date or pending['date'],'time':parsed.time or pending['time']}
                        self.store.update_call(sid,pending=updated)
                        reply=f"I noted the updated details for {updated['party_size']} guests. What guest name should I use?"
                        action='needs_name'
                    else:
                        candidate=(parsed.guest_name or text).strip()
                        if parsed.confirmation=='yes' or len(candidate)<2 or len(candidate)>60:
                            reply='Please tell me the guest name for the booking.'
                            action='needs_name'
                        else:
                            updated={**pending,'kind':'book','guest_name':candidate}
                            self.store.update_call(sid,pending=updated)
                            reply=f"Shall I reserve a table for {candidate}, {updated['party_size']} guests on {updated['date']} at {updated['time']}? Say yes to confirm."
                            action='awaiting_confirmation'
                # Corrections are processed BEFORE a generic yes/no and cannot silently commit.
                elif kind=='book' and any([parsed.party_size,parsed.date,parsed.time,parsed.guest_name]):
                    updated={**pending,
                        'party_size':parsed.party_size or pending['party_size'],
                        'date':parsed.date or pending['date'],
                        'time':parsed.time or pending['time'],
                        'guest_name':parsed.guest_name or pending['guest_name']}
                    if not self.store.availability(updated['date'],updated['time'],updated['party_size']):
                        reply='That correction has no available table. Your earlier proposal is not booked. Please choose another slot.'
                        action='not_available'
                        self.store.update_call(sid,pending={})
                    else:
                        self.store.update_call(sid,pending=updated)
                        reply=f"Updated: {updated['guest_name']}, {updated['party_size']} guests on {updated['date']} at {updated['time']}. Say yes to confirm."
                        action='awaiting_confirmation'
                elif parsed.confirmation=='no':
                    self.store.update_call(sid,pending={})
                    reply='Understood. No booking was changed. What else can I help with?'
                    action='proposal_rejected'
                elif parsed.confirmation=='yes':
                    if kind=='book':
                        data=self.store.create_reservation(
                            guest_name=pending['guest_name'],party_size=pending['party_size'],
                            date=pending['date'],time=pending['time'],phone=pending.get('phone',''),source=source)
                        reply=f"Reservation confirmed. Reference {data['id']}, {data['party_size']} guests on {data['booking_date']} at {data['booking_time']}."
                        action='booking_created'
                    elif kind=='cancel':
                        data=self.store.cancel_reservation(pending['reservation_id'])
                        reply=f"Reservation {data['id']} has been cancelled."
                        action='booking_cancelled'
                    elif kind=='modify':
                        data=self.store.modify_reservation(pending['reservation_id'],pending['date'],pending['time'],pending['party_size'])
                        reply=f"Reservation {data['id']} was updated to {data['booking_date']} at {data['booking_time']} for {data['party_size']} guests."
                        action='booking_modified'
                    else:
                        reply='That action is not available. No changes were made.'
                    self.store.update_call(sid,pending={})
                else:
                    reply='Please say yes to confirm or no to cancel. You can also correct the date, time or guest count.'
                    action='awaiting_confirmation'
            if not reply:
                if parsed.intent=='menu':
                    menu=self.store.menu();q=(parsed.topic or '').lower()
                    matched=[m for m in menu if m['name'].lower() in q or any(w in q for w in m['name'].lower().split() if len(w)>4)]
                    items=matched[:4] if matched else [m for m in menu if m['available']][:5]
                    reply='Our menu includes '+', '.join(f"{x['name']} at ₹{x['price_inr']}" for x in items)+'.';action='menu_lookup'
                elif parsed.intent=='handoff':
                    data=self.store.create_task(sid,'Manager follow-up',parsed.topic or text)
                    reply='I have sent your request to the restaurant manager for review. They will need to follow up with you directly.'
                    action='manager_task_created'
                elif parsed.intent in ('availability','book','modify'):
                    rid=parsed.reservation_id
                    if parsed.intent=='modify' and not rid:
                        reply='Please provide your reservation reference, beginning with RES-.'
                    elif not (parsed.date and parsed.time and parsed.party_size):
                        reply='Please tell me the date, time and number of guests. For example: book 4 people tomorrow at 8 pm.'
                    else:
                        free=self.store.availability(parsed.date,parsed.time,parsed.party_size)
                        if not free:
                            reply='There is no suitable table at that time. Please try a different time or party size.'
                            action='not_available'
                        elif parsed.intent=='availability':
                            reply=f"I found {len(free)} suitable table(s) for {parsed.party_size} guests at {parsed.time} on {parsed.date}. Availability may change before confirmation."
                            action='availability_checked'
                        elif parsed.intent=='modify':
                            self.store.update_call(sid,pending={'kind':'modify','reservation_id':rid,
                                'date':parsed.date,'time':parsed.time,'party_size':parsed.party_size})
                            reply=f"Change {rid} to {parsed.date}, {parsed.time}, for {parsed.party_size} guests? Say yes to confirm."
                            action='awaiting_confirmation'
                        elif not parsed.guest_name:
                            # Do not invent a name; user can put it into the structured form.
                            reply=f"A table is currently available for {parsed.party_size} guests on {parsed.date} at {parsed.time}. What name should I book it under?"
                            self.store.update_call(sid,pending={'kind':'needs_name','date':parsed.date,'time':parsed.time,
                                'party_size':parsed.party_size,'phone':parsed.phone or ''})
                            action='needs_name'
                        else:
                            self.store.update_call(sid,pending={'kind':'book','date':parsed.date,'time':parsed.time,
                                'party_size':parsed.party_size,'guest_name':parsed.guest_name,'phone':parsed.phone or ''})
                            reply=f"Shall I reserve a table for {parsed.guest_name}, {parsed.party_size} guests, on {parsed.date} at {parsed.time}? Say yes to confirm."
                            action='awaiting_confirmation'
                elif parsed.intent=='cancel':
                    if not parsed.reservation_id:
                        reply='Please tell me the reservation reference beginning with RES-.'
                    else:
                        self.store.update_call(sid,pending={'kind':'cancel','reservation_id':parsed.reservation_id})
                        reply=f"Are you sure you want to cancel {parsed.reservation_id}? Say yes to confirm."
                        action='awaiting_confirmation'
                else:
                    reply='Welcome to Atithi. I can check table availability, make reservations, answer menu questions, or contact the manager. What can I help with?'
        except DomainError as exc:
            self.store.update_call(sid,pending={})
            reply=f"I couldn't complete that action: {exc}. Your existing reservations were not changed."
            action='validation_rejected'
        # Spoken Hindi replies for Hindi/Hinglish input. Results are generated from the
        # actual DB action, never inferred from the model's imagined tool outputs.
        if parsed.language == 'hi':
            if action == 'booking_created' and data:
                reply=f"आपकी बुकिंग पक्की हो गई है। बुकिंग नंबर {data['id']}। {data['party_size']} लोग, तारीख {data['booking_date']}, समय {data['booking_time']}।"
            elif action == 'booking_cancelled' and data:
                reply=f"बुकिंग {data['id']} रद्द कर दी गई है।"
            elif action == 'booking_modified' and data:
                reply=f"बुकिंग {data['id']} बदल दी गई है। नई तारीख {data['booking_date']}, समय {data['booking_time']}।"
            elif action == 'manager_task_created':
                reply='आपकी बात मैनेजर तक पहुँचा दी गई है। हमारी टीम इस अनुरोध को देखेगी।'
            elif action == 'availability_checked':
                reply=f"{parsed.party_size} लोगों के लिए {parsed.date} को {parsed.time} बजे टेबल उपलब्ध है। बुकिंग की पुष्टि बाकी है।"
            elif action == 'not_available':
                reply='माफ़ कीजिए, इस समय उपयुक्त टेबल उपलब्ध नहीं है। कृपया कोई और समय बताइए।'
            elif action == 'awaiting_confirmation' and pending is None:
                # Pending may be freshly created on this turn.
                current=self.store.get_call(sid)
                current_pending=json.loads(current['pending_json']) if current and current.get('pending_json') else {}
                if current_pending.get('kind')=='book':
                    reply=f"क्या मैं {current_pending['guest_name']} के नाम से {current_pending['party_size']} लोगों की बुकिंग {current_pending['date']} को {current_pending['time']} बजे कर दूँ? हाँ या नहीं कहिए।"
            elif action == 'needs_name':
                reply='बुकिंग के लिए अपना नाम बताइए।'
            elif action == 'menu_lookup':
                reply='हमारे मेन्यू में ' + ', '.join(f"{m['name']}" for m in self.store.menu()[:5]) + ' जैसी डिशें उपलब्ध हैं।'
        self.store.add_turn(sid,'assistant',reply)
        return TurnResult(sid,text,reply,mode,action,data)
