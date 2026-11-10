from datetime import timedelta
from uuid import uuid4
from fastapi.testclient import TestClient
from app.main import app,store
from app.config import settings
from app.storage import now_ist

client=TestClient(app)

def test_health_and_capabilities():
    assert client.get('/api/health').status_code==200
    caps=client.get('/api/capabilities').json()
    assert caps['reservation_mode']=='real_sqlite'


def test_admin_requires_key():
    assert client.get('/api/admin/overview').status_code==401
    assert client.get('/api/admin/overview',headers={'X-Admin-Token':'bad'}).status_code==401


def test_dashboard_and_manual_booking(tmp_path):
    auth={'X-Admin-Token':settings.admin_token}
    assert client.get('/api/admin/overview',headers=auth).status_code==200
    day=(now_ist()+timedelta(days=5)).date().isoformat()
    response=client.post('/api/admin/reservations',headers=auth,json={
        'guest_name':'API Test Person','party_size':8,'date':day,'time':'19:00'})
    assert response.status_code==200,response.text
    rid=response.json()['id']
    assert response.json()['table_id']=='T08'
    assert client.post('/api/admin/reservations',headers=auth,json={
        'guest_name':'API Double Book','party_size':8,'date':day,'time':'19:00'}).status_code==409
    assert client.post(f'/api/admin/reservations/{rid}/cancel',headers=auth).status_code==200

def test_reservation_calendar_range_table_modify_and_cancel():
    auth={'X-Admin-Token':settings.admin_token}
    day=(now_ist()+timedelta(days=50+uuid4().int%10000)).date().isoformat()
    created=client.post('/api/admin/reservations',headers=auth,json={
        'guest_name':'Calendar Guest','party_size':2,'date':day,'time':'19:00','table_id':'T02','notes':'Window seat'})
    assert created.status_code==200
    booking=created.json()
    assert booking['table_id']=='T02'
    rows=client.get('/api/admin/reservations/range',headers=auth,
                    params={'start_date':day,'end_date':day}).json()['reservations']
    assert any(row['id']==booking['id'] for row in rows)
    updated=client.patch(f"/api/admin/reservations/{booking['id']}",headers=auth,json={
        'guest_name':'Calendar Guest Updated','party_size':2,'date':day,'time':'20:00',
        'table_id':'T03','notes':'Window seat'})
    assert updated.status_code==200
    assert updated.json()['table_id']=='T03'
    assert updated.json()['booking_time']=='20:00'
    cancelled=client.post(f"/api/admin/reservations/{booking['id']}/cancel",headers=auth)
    assert cancelled.status_code==200 and cancelled.json()['status']=='cancelled'
    rows=client.get('/api/admin/reservations/range',headers=auth,
                    params={'start_date':day,'end_date':day}).json()['reservations']
    assert next(row for row in rows if row['id']==booking['id'])['status']=='cancelled'
    assert client.get('/api/admin/reservations/range',headers=auth,
                      params={'start_date':'invalid','end_date':day}).status_code==409
