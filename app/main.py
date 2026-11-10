"""Atithi AI: demonstrable reservation engine and turn-based Gnani voice bridge."""
from __future__ import annotations
import asyncio
import hmac
import base64
import hashlib
import os
import re
import secrets
import subprocess
import tempfile
import time
import uuid
from collections import defaultdict,deque
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

import httpx
from fastapi import FastAPI,Request,UploadFile,File,Form,Header,HTTPException,Depends
from fastapi.responses import FileResponse,Response,JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel,Field
from .storage import Storage,DomainError
from .dialogue import Dialogue
from .providers import gnani_stt,gnani_tts,ProviderFailure
from .config import settings

BASE=Path(__file__).resolve().parent
app=FastAPI(title='Atithi AI',version='0.1.0',docs_url='/api/docs',redoc_url=None)
app.mount('/assets',StaticFiles(directory=BASE/'static'),name='assets')
if settings.public_base_url and settings.admin_token == 'replace-with-a-long-random-local-token':
    raise RuntimeError('Set a unique ADMIN_TOKEN before exposing a public URL')
store=Storage(settings.db_path)
dialogue=Dialogue(store)
limits=defaultdict(deque)

@app.exception_handler(DomainError)
async def domain_error_handler(_req:Request,exc:DomainError):
    return JSONResponse(status_code=409,content={'error':str(exc)})
@app.exception_handler(ProviderFailure)
async def provider_error_handler(_req:Request,exc:ProviderFailure):
    return JSONResponse(status_code=503,content={'error':str(exc),'mode':'provider_error'})


def admin_required(x_admin_token:str=Header(default='')):
    if not settings.admin_token or not secrets.compare_digest(x_admin_token,settings.admin_token):
        raise HTTPException(401,'Invalid manager token')
    return True


def rate_limit(req:Request):
    ip=(req.client.host if req.client else 'unknown')
    q=limits[ip];n=time.monotonic()
    while q and n-q[0]>60:q.popleft()
    if len(q)>=30:raise HTTPException(429,'Too many demo requests. Retry shortly.')
    q.append(n)

class ReservationIn(BaseModel):
    guest_name:str=Field(min_length=2,max_length=80)
    party_size:int=Field(ge=1,le=8)
    date:str
    time:str
    phone:str=Field(default='',max_length=50)
    notes:str=Field(default='',max_length=500)
    table_id:str|None=None
class ReservationChange(BaseModel):
    date:str
    time:str
    party_size:int=Field(ge=1,le=8)
    table_id:str|None=None
    guest_name:str|None=Field(default=None,min_length=2,max_length=80)
    notes:str|None=Field(default=None,max_length=500)
class AvailabilityIn(BaseModel):
    date:str
    time:str
    party_size:int=Field(ge=1,le=8)
class TableUpdate(BaseModel):status:str
class TaskUpdate(BaseModel):status:str
class TextTurnIn(BaseModel):
    text:str=Field(min_length=1,max_length=2000)
    session_id:str|None=None

@app.get('/')
async def index():return FileResponse(BASE/'static'/'index.html',media_type='text/html')

@app.get('/api/health')
async def health():return {'status':'ok','service':'atithi','database':'sqlite'}

@app.get('/api/capabilities')
async def capabilities():
    return {'gnani_configured':bool(settings.gnani_api_key),'gemini_configured':bool(settings.gemini_api_key),
            'parser_fallback_enabled':settings.allow_rule_demo,
            'twilio_bridge_configured':bool(settings.twilio_auth_token and settings.public_base_url),
            'phone_mode':'turn_based_recording','reservation_mode':'real_sqlite','floor_sensor':'staff_only'}

@app.get('/api/admin/overview',dependencies=[Depends(admin_required)])
async def overview():return store.dashboard()

@app.get('/api/admin/reservations/range',dependencies=[Depends(admin_required)])
async def reservations_range(start_date:str,end_date:str):
    return {'reservations':store.list_reservations_range(start_date,end_date)}

@app.post('/api/admin/availability',dependencies=[Depends(admin_required)])
async def admin_avail(payload:AvailabilityIn):return {'tables':store.availability(payload.date,payload.time,payload.party_size)}

@app.post('/api/admin/reservations',dependencies=[Depends(admin_required)])
async def admin_book(payload:ReservationIn):return store.create_reservation(**payload.model_dump())

@app.patch('/api/admin/reservations/{rid}',dependencies=[Depends(admin_required)])
async def admin_modify(rid:str,payload:ReservationChange):return store.modify_reservation(rid,**payload.model_dump())

@app.post('/api/admin/reservations/{rid}/cancel',dependencies=[Depends(admin_required)])
async def admin_cancel(rid:str):return store.cancel_reservation(rid)

@app.patch('/api/admin/tables/{tid}',dependencies=[Depends(admin_required)])
async def admin_table(tid:str,payload:TableUpdate):return store.update_table(tid,payload.status)

@app.patch('/api/admin/tasks/{task_id}',dependencies=[Depends(admin_required)])
async def admin_task(task_id:str,payload:TaskUpdate):return store.update_task(task_id,payload.status)

@app.get('/api/admin/calls/{call_id}/turns',dependencies=[Depends(admin_required)])
async def admin_turns(call_id:str):return {'turns':store.turns(call_id)}

@app.post('/api/chat/turn')
async def chat_turn(payload:TextTurnIn,request:Request):
    rate_limit(request)
    result=await dialogue.turn(payload.text,payload.session_id)
    return result.__dict__


def convert_to_wav(blob:bytes,suffix:str)->bytes:
    """Browser MediaRecorder often produces WebM; Gnani REST expects WAV/OGG/etc."""
    if len(blob)>10_000_000:raise HTTPException(413,'Audio exceeds 10 MB.')
    if len(blob)<64:raise HTTPException(400,'Audio file too short.')
    if suffix not in {'.wav','.webm','.ogg','.mp3','.m4a','.mp4','.flac','.aac'}:
        raise HTTPException(415,'Unsupported recording format.')
    with tempfile.TemporaryDirectory() as folder:
        source=Path(folder)/('input'+suffix);target=Path(folder)/'output.wav'
        source.write_bytes(blob)
        try:
            proc=subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y',
                '-i',str(source),'-t','29','-vn','-ac','1','-ar','16000','-c:a','pcm_s16le',str(target)],
                capture_output=True,timeout=25,check=False)
        except (FileNotFoundError,subprocess.TimeoutExpired):
            raise HTTPException(503,'FFmpeg not available or conversion timed out.')
        if proc.returncode!=0 or not target.exists():raise HTTPException(422,'Could not decode audio. Record again.')
        output=target.read_bytes()
        if len(output)<16000:raise HTTPException(422,'Recording too short or silent.')
        return output


def save_voice_audio(audio:bytes)->str:
    folder=settings.runtime_dir/'audio';folder.mkdir(parents=True,exist_ok=True)
    token=uuid.uuid4().hex
    (folder/(token+'.wav')).write_bytes(audio)
    return '/api/audio/'+token

@app.get('/api/audio/{token}')
async def public_audio(token:str):
    if not re.fullmatch(r'[a-f0-9]{32}',token):raise HTTPException(404)
    path=settings.runtime_dir/'audio'/(token+'.wav')
    if not path.is_file():raise HTTPException(404)
    # Short-lived, unguessable URL; recording output is never exposed here.
    if time.time()-path.stat().st_mtime > 3600:raise HTTPException(410,'Audio link expired.')
    return FileResponse(path,media_type='audio/wav',headers={'Cache-Control':'private, max-age=60'})

async def spoken_turn(wav:bytes,session_id:str|None,source:str='voice',caller:str=''):
    transcript,stt_model=await gnani_stt(wav)
    result=await dialogue.turn(transcript,session_id,source=source,caller=caller)
    response=result.__dict__.copy()
    response['stt_model']=stt_model
    response['audio_url']=None
    response['tts_status']='not_requested'
    try:
        tts_data=await gnani_tts(result.reply)
        response['audio_url']=save_voice_audio(tts_data)
        response['tts_status']='live_gnani'
    except ProviderFailure as exc:
        response['tts_status']='unavailable'
        response['tts_error']=str(exc)
    return response

@app.post('/api/voice/turn')
async def voice_turn(request:Request, audio:UploadFile=File(...),session_id:str=Form(default='')):
    rate_limit(request)
    filename=(audio.filename or 'clip.webm').lower()
    suffix=Path(filename).suffix.lower()
    blob=await audio.read(10_000_001)
    wav=convert_to_wav(blob,suffix)
    return await spoken_turn(wav,session_id or None)

# TWILIO: staged phone bridge. Trial accounts may reject custom instructions.
# Uses <Record> turn taking, NOT interruptible full-duplex Media Streams.
# Production usage requires webhook signing, public HTTPS and an upgraded/supported number.
def _twilio_check(url:str,form:dict,signature:str):
    if not settings.twilio_auth_token or not signature:return False
    material=url+''.join(k+v for k,v in sorted(form.items()))
    expected=base64.b64encode(hmac.new(settings.twilio_auth_token.encode(),material.encode(),hashlib.sha1).digest()).decode()
    return secrets.compare_digest(expected,signature)

async def checked_twilio_form(request:Request):
    if not settings.public_base_url:raise HTTPException(503,'PUBLIC_BASE_URL not configured')
    if request.method!='POST':raise HTTPException(405)
    form={k:str(v) for k,v in (await request.form()).items()}
    signed_url=settings.public_base_url+request.url.path
    if request.url.query:signed_url+='?'+request.url.query
    if not _twilio_check(signed_url,form,request.headers.get('x-twilio-signature','')):
        raise HTTPException(403,'Invalid Twilio signature')
    return form


def twiml(text:str='',audio_url:str|None=None,call_id:str|None=None,end:bool=False):
    root=ET.Element('Response')
    if audio_url and settings.public_base_url:
        ET.SubElement(root,'Play').text=settings.public_base_url+audio_url
    else:
        # Twilio TTS fallback distinctly logged; can occur only when Gnani is down.
        ET.SubElement(root,'Say',{'language':'en-US'}).text=text or 'Sorry, please try again.'
    if end:ET.SubElement(root,'Hangup')
    elif call_id:
        ET.SubElement(root,'Record',{
            'action':settings.public_base_url+'/twilio/turn',
            'method':'POST','maxLength':'25','timeout':'2',
            'playBeep':'false','finishOnKey':'#'
        })
    return Response(ET.tostring(root,encoding='unicode'),media_type='application/xml')

@app.post('/twilio/voice')
async def twilio_voice(request:Request):
    data=await checked_twilio_form(request)
    call_id=data.get('CallSid') or 'TW-'+uuid.uuid4().hex
    store.create_call(call_id,source='twilio',caller=data.get('From',''))
    greeting='Namaste! Welcome to Atithi restaurant. Please tell me how I can help. Press hash to finish speaking.'
    try: greeting_audio=save_voice_audio(await gnani_tts(greeting))
    except ProviderFailure:greeting_audio=None
    return twiml(greeting,greeting_audio,call_id)

async def _retrieve_twilio_wav(url:str)->bytes:
    parsed=urlparse(url)
    if parsed.scheme!='https' or parsed.hostname!='api.twilio.com' or '/Recordings/' not in parsed.path:
        raise ProviderFailure('Unexpected Twilio recording address')
    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        raise ProviderFailure('Twilio credentials missing')
    # Twilio may notify action before recording is actually downloadable.
    async with httpx.AsyncClient(timeout=9,auth=(settings.twilio_account_sid,settings.twilio_auth_token)) as client:
        for _ in range(3):
            try:
                response=await client.get(url+'.wav')
                if response.status_code==200 and response.content.startswith(b'RIFF'):
                    return response.content
            except httpx.HTTPError:
                pass
            await asyncio.sleep(0.5)
    raise ProviderFailure('Twilio recording is not ready; use browser-call demo or retry')

@app.post('/twilio/turn')
async def twilio_turn(request:Request):
    data=await checked_twilio_form(request)
    sid=data.get('CallSid','')
    if not sid or store.get_call(sid) is None:raise HTTPException(403,'Unknown call')
    url=data.get('RecordingUrl','')
    if not url:return twiml('I did not hear you. Please try again.',call_id=sid)
    try:
        wav=await _retrieve_twilio_wav(url)
        result=await spoken_turn(wav,sid,source='twilio',caller=data.get('From',''))
        return twiml(result['reply'],result['audio_url'],sid)
    except (ProviderFailure,DomainError,HTTPException):
        return twiml('Sorry, I could not process that response. Please speak again.',call_id=sid)
