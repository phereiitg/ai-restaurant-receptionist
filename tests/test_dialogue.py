import pytest
from datetime import timedelta
from app.storage import now_ist
from app.dialogue import Dialogue
import app.dialogue as module
from app.providers import ParsedIntent

@pytest.mark.asyncio
async def test_live_booking_requires_confirmation(store,monkeypatch):
    day=(now_ist()+timedelta(days=3)).date().isoformat()
    calls=[ParsedIntent(intent='book',party_size=8,date=day,time='20:00',guest_name='Demo Person'),
           ParsedIntent(intent='other',confirmation='yes')]
    async def fake_interpret(*a,**kw):return calls.pop(0),'test_parser'
    monkeypatch.setattr(module,'interpret',fake_interpret)
    a=Dialogue(store)
    p=await a.turn('Book me a table')
    assert p.action=='awaiting_confirmation'
    assert store.list_reservations()==[]
    c=await a.turn('yes',p.session_id)
    assert c.action=='booking_created'
    assert c.data['party_size']==8

@pytest.mark.asyncio
async def test_handoff_creates_real_task(store,monkeypatch):
    async def fake(*a,**kw):return ParsedIntent(intent='handoff',topic='Birthday cake'), 'test_parser'
    monkeypatch.setattr(module,'interpret',fake)
    d=Dialogue(store)
    r=await d.turn('Manager please')
    assert r.action=='manager_task_created'
    assert store.list_tasks()[0]['notes']=='Birthday cake'

@pytest.mark.asyncio
async def test_correct_party_size_before_confirm(store,monkeypatch):
    day=(now_ist()+timedelta(days=3)).date().isoformat()
    calls=[ParsedIntent(intent='book',party_size=4,date=day,time='20:00',guest_name='Demo Person'),
           ParsedIntent(intent='other',party_size=6),ParsedIntent(intent='other',confirmation='yes')]
    async def fake(*a,**kw):return calls.pop(0),'test_parser'
    monkeypatch.setattr(module,'interpret',fake)
    d=Dialogue(store)
    first=await d.turn('Book four people');assert first.action=='awaiting_confirmation'
    update=await d.turn('Actually six people',first.session_id)
    assert update.action=='awaiting_confirmation' and '6 guests' in update.reply
    assert store.list_reservations()==[]
    confirmed=await d.turn('yes',first.session_id)
    assert confirmed.action=='booking_created' and confirmed.data['party_size']==6

@pytest.mark.asyncio
async def test_local_demo_parser_end_to_end_last_table(store):
    from app.providers import local_demo_parser
    from datetime import timedelta
    a=Dialogue(store)
    first=await a.turn('Book 8 people tomorrow at 8 pm. My name is Rahul')
    assert first.parser_mode in {'demo_rules','gemini'}
    assert first.action=='awaiting_confirmation'
    second=await a.turn('yes',first.session_id)
    assert second.action=='booking_created'
    assert second.data['table_id']=='T08'
    third=await a.turn('Book 8 people tomorrow at 8 pm. My name is Priya')
    assert third.action=='not_available'
