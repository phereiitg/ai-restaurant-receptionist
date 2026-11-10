from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import pytest
from app.storage import DomainError,now_ist


def future():
    dt=(now_ist()+timedelta(days=3)).replace(hour=20,minute=0,second=0,microsecond=0)
    return dt.strftime('%Y-%m-%d'),dt.strftime('%H:%M')

def test_seeded_data(store):
    assert len(store.list_tables())==8
    assert len(store.menu())>=6
    assert store.dashboard()['reservation_count']==0

def test_create_cancel_then_rebook(store):
    day,t=future()
    first=store.create_reservation(guest_name='Test Guest',party_size=8,date=day,time=t)
    assert first['table_id']=='T08'
    with pytest.raises(DomainError,match='No suitable'):
        store.create_reservation(guest_name='Other Guest',party_size=8,date=day,time=t)
    store.cancel_reservation(first['id'])
    nextone=store.create_reservation(guest_name='Other Guest',party_size=8,date=day,time=t)
    assert nextone['table_id']=='T08'

def test_specific_table_booking_checks_capacity_and_conflicts(store):
    day,t=future()
    selected=store.create_reservation(guest_name='Window Guest',party_size=2,date=day,time=t,table_id='T02')
    assert selected['table_id']=='T02'
    with pytest.raises(DomainError,match='cannot seat'):
        store.create_reservation(guest_name='Too Many Guests',party_size=4,date=day,time=t,table_id='T01')
    with pytest.raises(DomainError,match='not available'):
        store.create_reservation(guest_name='Table Conflict',party_size=2,date=day,time=t,table_id='T02')
    with pytest.raises(DomainError,match='not found'):
        store.create_reservation(guest_name='Unknown Table Guest',party_size=2,date=day,time=t,table_id='T99')
    automatic=store.create_reservation(guest_name='Automatic Guest',party_size=2,date=day,time=t)
    assert automatic['table_id']=='T01'

def test_specific_table_modify_and_date_range(store):
    day,t=future()
    first=store.create_reservation(guest_name='First Guest',party_size=2,date=day,time=t,table_id='T01')
    second=store.create_reservation(guest_name='Second Guest',party_size=2,date=day,time='22:00',table_id='T02')
    moved=store.modify_reservation(second['id'],day,'20:00',2,table_id='T03')
    assert moved['table_id']=='T03'
    with pytest.raises(DomainError,match='not available'):
        store.modify_reservation(second['id'],day,'20:00',2,table_id='T01')
    assert store.list_reservations_range(day,day)==[first,moved]
    assert store.list_reservations_range((now_ist()+timedelta(days=4)).date().isoformat(),
                                         (now_ist()+timedelta(days=5)).date().isoformat())==[]
    with pytest.raises(DomainError):store.list_reservations_range(day,'invalid')

def test_date_range_includes_cancelled_reservations(store):
    day,t=future()
    booking=store.create_reservation(guest_name='Cancelled Guest',party_size=2,date=day,time=t)
    store.cancel_reservation(booking['id'])
    rows=store.list_reservations_range(day,day)
    assert len(rows)==1 and rows[0]['status']=='cancelled'

def test_overlapping_slots_protected(store):
    day,t=future()
    store.create_reservation(guest_name='Customer One',party_size=8,date=day,time=t)
    for offset in ['20:10','20:50','21:20']:
        with pytest.raises(DomainError):store.create_reservation(guest_name='Guest Two',party_size=8,date=day,time=offset)
    later=store.create_reservation(guest_name='Later Guest',party_size=8,date=day,time='21:30')
    assert later['table_id']=='T08'

def test_race_only_one_wins_last_table(store):
    day,t=future()
    def run(i):
        try:return store.create_reservation(guest_name=f'Guest {i}',party_size=8,date=day,time=t)
        except DomainError:return None
    with ThreadPoolExecutor(max_workers=10) as executor:
        outcomes=list(executor.map(run,range(10)))
    assert sum(bool(x) for x in outcomes)==1
    assert len([r for r in store.list_reservations(day) if r['status']=='confirmed'])==1

def test_modify_conflict_keeps_old_booking(store):
    day,t=future()
    first=store.create_reservation(guest_name='First Guest',party_size=8,date=day,time=t)
    second=store.create_reservation(guest_name='Other Guest',party_size=8,date=day,time='21:30')
    with pytest.raises(DomainError):store.modify_reservation(second['id'],day,'20:10',8)
    after=[r for r in store.list_reservations(day) if r['id']==second['id']][0]
    assert after['booking_time']=='21:30'

def test_blocked_table_excluded(store):
    day,t=future()
    store.update_table('T08','blocked')
    with pytest.raises(DomainError,match='No suitable'):
        store.create_reservation(guest_name='Blocked Guest',party_size=8,date=day,time=t)

def test_validation(store):
    day,t=future()
    with pytest.raises(DomainError):store.create_reservation(guest_name='A',party_size=3,date=day,time=t)
    with pytest.raises(DomainError):store.create_reservation(guest_name='Valid Guest',party_size=9,date=day,time=t)
    with pytest.raises(DomainError):store.create_reservation(guest_name='Valid Guest',party_size=3,date='yesterday',time=t)

def test_calls_and_tasks(store):
    store.create_call('CALL-123',source='browser')
    store.add_turn('CALL-123','user','Menu please')
    store.add_turn('CALL-123','assistant','Here you go')
    assert len(store.turns('CALL-123'))==2
    t=store.create_task('CALL-123','Birthday cake','Details to review')
    assert store.list_tasks()[0]['status']=='open'
    store.update_task(t['id'],'done')
    assert store.list_tasks()[0]['status']=='done'
