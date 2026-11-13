"""Optional local TinyPOS extension. Start with --tinypos-path; no BLE at startup."""
import argparse
import base64
import asyncio
import io
import json
import secrets
import sqlite3
import sys
import uuid
import zipfile
from contextlib import asynccontextmanager, closing
from pathlib import Path
from types import SimpleNamespace

import tinyprint_cli as driver
from photo_bands import layout, source_image, resolve_render, preview_image, render_strips
from PIL import Image, UnidentifiedImageError


class BridgeRuntime:
    def __init__(self, data_dir, address=None):
        self.root = Path(data_dir).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.address = address
        self.lock = asyncio.Lock()
        self.render_lock = asyncio.Lock()
        self.active = None
        self.tasks = {}
        self.session = secrets.token_urlsafe(32)

    def folder(self, identifier):
        try:
            if uuid.UUID(identifier).hex != identifier:
                raise ValueError()
        except (ValueError, AttributeError):
            raise FileNotFoundError()
        path = self.root / identifier
        if not (path / 'manifest.json').is_file():
            raise FileNotFoundError()
        return path

    def details(self, identifier):
        folder = self.folder(identifier)
        manifest = json.loads((folder / 'manifest.json').read_text())
        state = driver.load_state(folder)
        status = json.loads((folder / 'job.json').read_text()) if (folder / 'job.json').exists() else {'status': 'prepared'}
        if status['status'] in ('queued', 'sending') and identifier not in self.tasks:
            status = {'status': 'interrupted', 'message': 'Service redémarré ; reprise disponible.'}
        return dict(id=identifier, count=len(manifest['order']), size_mm=manifest['final_size_mm'],
                    bands=manifest['bands'], settings=manifest['settings'], direction=manifest['direction'], render=manifest.get('render', {'dither':'floyd','gain':1}), done=state.get('done', []),
                    configured=bool(self.address), layout=manifest.get('layout', {}), **status)

    def render(self, content, direction, count, dither, gain, energy, row_delay, cooldown,
               *, preview=False, size_mode='count', size_mm=None, preset='custom',
               sharpness=None, contrast=None, brightness=None, strength=7, autocrop=False):
        options=resolve_render(dict(preset=preset,dither=dither,gain=gain,sharpness=sharpness,
                                    contrast=contrast,brightness=brightness,strength=strength,autocrop=autocrop))
        with Image.open(io.BytesIO(content)) as source:
            if source.width*source.height>20_000_000:
                raise ValueError('Image trop grande : maximum 20 millions de pixels.')
            source.load()
            adjusted=source_image(source,options['autocrop'])
            plan=layout(adjusted.size,direction,count,size_mode,size_mm)
            sheet=preview_image(source,plan,options)
            bands=[dict(number=i,rows=plan['rows_per_ticket'],length_mm=plan['rows_per_ticket']/8)
                   for i in range(1,plan['count']+1)]
            settings=dict(energy=energy,row_delay=row_delay,cooldown=cooldown)
            if preview:
                buffer=io.BytesIO();sheet.save(buffer,format='PNG')
                return dict(count=plan['count'],size_mm=plan['size_mm'],bands=bands,layout=plan,
                            render=options,settings=settings,direction=direction,configured=bool(self.address),
                            preview='data:image/png;base64,'+base64.b64encode(buffer.getvalue()).decode('ascii'))
            images=render_strips(source,plan,options)
        identifier=uuid.uuid4().hex
        folder=self.root/identifier
        folder.mkdir()
        for index,image in enumerate(images,1):
            image.save(folder/f'{index:02}.png')
        sheet.save(folder/'preview.png')
        manifest=dict(direction=direction,render=options,layout=plan,
                      order=[f'{i:02}.png' for i in range(1,plan['count']+1)],
                      final_size_mm=plan['size_mm'],settings=settings,bands=bands)
        (folder/'manifest.json').write_text(json.dumps(manifest,indent=2))
        return self.details(identifier)

    def prepare(self, *args, **kwargs):
        return self.render(*args, **kwargs)

    def args(self, settings=None, strength=3, resume=False):
        settings = settings or dict(energy=8000, row_delay=.014, cooldown=0)
        return SimpleNamespace(address=self.address, timeout=12, strength=strength, **settings,
                               feed_rows=80, feed_mm=10, force=False, fault_wait=0,
                               chunk_rows=0, chunk_pause=0, smart_pause=True, smart_window=48,
                               cool_max=0, resume=resume)

    async def transmit(self, call):
        async with self.lock:
            self.active = asyncio.current_task()
            try:
                return await call()
            finally:
                self.active = None

    async def send(self, identifier, resume):
        folder = self.folder(identifier)
        def record(status, message=''):
            (folder / 'job.json').write_text(json.dumps(dict(status=status, message=message)))
        record('queued', 'En attente de l’imprimante.')
        async def operation():
            record('sending', 'Envoi en cours ; contrôlez aussi le papier.')
            manifest = json.loads((folder / 'manifest.json').read_text())
            images = []
            for filename in manifest['order']:
                with Image.open(folder / filename) as image:
                    images.append(image.copy())
            return await driver.print_series(self.args(manifest['settings'], resume=resume), images, folder)
        try:
            code = await self.transmit(operation)
            record('sent' if code == 0 else 'failed',
                   'Envoi terminé ; vérifiez dimensions et avance sur le papier.' if code == 0 else 'Envoi interrompu. Vérifiez papier et état avant la reprise.')
        except asyncio.CancelledError:
            record('cancelled', 'Envoi annulé. Le papier déjà engagé peut encore avancer.')
        except Exception:
            record('failed', 'Erreur de transport ; consultez le journal local du service.')
        finally:
            self.tasks.pop(identifier, None)


def build_app(tinypos_path, data_dir, address=None):
    from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
    from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
    from fastapi.templating import Jinja2Templates
    from jinja2 import ChoiceLoader, FileSystemLoader, PrefixLoader

    bridge = Path(tinypos_path).resolve()
    if not (bridge / 'main.py').is_file() or not (bridge / 'server/config.py').is_file():
        raise ValueError('Le chemin doit désigner le clone TinyPOS-Bridge.')
    sys.path.insert(0, str(bridge))
    import main as tinypos
    import printer_ble
    import server.config as config
    import server.db as db
    from server.auth import require_login
    runtime = BridgeRuntime(data_dir, address)
    # Preserve original database. Schema upgrades and test jobs target a separate copy.
    database = runtime.root / 'tinypos.db'
    if not database.exists() and Path(config.DB_PATH).exists():
        with closing(sqlite3.connect(f'file:{config.DB_PATH}?mode=ro', uri=True)) as source, closing(sqlite3.connect(database)) as dest:
            source.backup(dest)
    config.DB_PATH = db.DB_PATH = database
    app = tinypos.app
    original_lifespan = app.router.lifespan_context
    @asynccontextmanager
    async def lifespan(application):
        async with original_lifespan(application):
            yield
            tasks = list(runtime.tasks.values())
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
    app.router.lifespan_context = lifespan
    original_status = printer_ble.get_printer_status
    original_feed = printer_ble.CMD_FEED_PAPER
    async def send_bitmap(img, address=None, strength=7, job_id=None):
        if not runtime.address:
            return False, 'Configurez --address au lancement du bridge.'
        try:
            result = await runtime.transmit(lambda: driver.print_image(runtime.args(strength=strength), img))
            return result == 0, 'Envoi terminé ; contrôle papier nécessaire.' if result == 0 else 'Envoi interrompu par le pilote.'
        except asyncio.CancelledError:
            return False, 'Impression annulée.'
    def stop():
        if runtime.active:
            runtime.active.cancel()
            return True, 'Annulation demandée.'
        return False, 'Aucun envoi actif.'
    async def status():
        if runtime.active:
            return dict(status='online', is_printing=True, printer_name='Tiny Print driver', active_job_id=None, mode='bluetooth')
        return await original_status()
    printer_ble.send_bitmap_to_printer = send_bitmap
    printer_ble.stop_printing = stop
    printer_ble.get_printer_status = status
    # Existing feed endpoint also shares the hardware lock.
    import server.services.print_service as service
    original_feed_function = service.feed_paper_cmd
    async def feed(group=None):
        if db.get_setting('bridge_mode', 'bluetooth') != 'bluetooth':
            return await original_feed_function(group=group)
        if not runtime.address:
            return False, 'Configurez --address au lancement.'
        async def operation():
            client, tx = await driver.connect(runtime.args())
            if not client or not tx:
                return False, 'Imprimante introuvable.'
            try:
                state = await driver.query_state(client, tx)
                if not state or state['flags']:
                    return False, 'État non prêt ; avance annulée.'
                await client.write_gatt_char(tx, original_feed, response=False)
                return True, 'Avance envoyée.'
            finally:
                await client.disconnect()
        return await runtime.transmit(operation)
    service.feed_paper_cmd = feed
    # Routes import these functions directly; replace their feed bindings too.
    import server.routes.internal_api as internal
    import server.routes.public_api as public
    internal.feed_paper_cmd = public.feed_paper_cmd = feed
    templates = Jinja2Templates(directory=str(Path(__file__).parent / 'integrations/tinypos/templates'))
    templates.env.loader = ChoiceLoader([templates.env.loader, PrefixLoader({'tinypos': FileSystemLoader(str(bridge / 'UI'))}), FileSystemLoader(str(bridge / 'UI'))])

    async def admin(request: Request, user=Depends(require_login)):
        if not secrets.compare_digest(request.cookies.get('driver_session', ''), runtime.session):
            raise HTTPException(401, 'Reconnectez-vous à TinyPOS pour ouvrir l’atelier.')
        if request.method != 'GET':
            origin = request.headers.get('origin')
            if origin and origin != str(request.base_url).rstrip('/'):
                raise HTTPException(403, 'Origine non autorisée.')
    router = APIRouter(dependencies=[Depends(admin)])
    def folder(identifier):
        try:
            return runtime.folder(identifier)
        except FileNotFoundError:
            raise HTTPException(404, 'Série introuvable.')
    @router.get('/photo-bands')
    async def page(request: Request):
        return templates.TemplateResponse(request=request, name='bands.html', context={'active_page': 'bands'})
    @router.post('/api/internal/bands/preview')
    @router.post('/api/internal/bands/prepare')
    async def prepare(request: Request, file: UploadFile = File(...), direction: str = Form('vertical'),
                      count: int = Form(3, ge=1), dither: str = Form(None), gain: float = Form(1, ge=.25, le=4),
                      energy: int = Form(8000, ge=1, le=65535), row_delay: float = Form(.014, ge=.001, le=.2),
                      cooldown: float = Form(0, ge=0, le=120), size_mode: str = Form('count'), size_mm: float = Form(None),
                      preset: str = Form('custom'), sharpness: float = Form(None, ge=0, le=3),
                      contrast: float = Form(None, ge=.25, le=3), brightness: float = Form(None, ge=.25, le=3),
                      strength: int = Form(7, ge=1, le=7), autocrop: bool = Form(False)):
        content=await file.read(20*1024*1024+1)
        if len(content)>20*1024*1024:
            raise HTTPException(413,'Photo limitée à 20 Mo.')
        try:
            async with runtime.render_lock:
                return await asyncio.to_thread(runtime.render,content,direction,count,dither,gain,energy,row_delay,cooldown,
                    preview=request.url.path.endswith('/preview'),size_mode=size_mode,size_mm=size_mm,preset=preset,
                    sharpness=sharpness,contrast=contrast,brightness=brightness,strength=strength,autocrop=autocrop)
        except (UnidentifiedImageError,OSError,ValueError,Image.DecompressionBombError) as exc:
            raise HTTPException(422,str(exc) if isinstance(exc,ValueError) else 'Image illisible ou trop grande.')
    @router.get('/api/internal/bands/{identifier}')
    async def details(identifier: str):
        folder(identifier)
        return runtime.details(identifier)
    @router.get('/api/internal/bands/{identifier}/preview')
    async def preview(identifier: str):
        return FileResponse(folder(identifier) / 'preview.png', media_type='image/png')
    @router.get('/api/internal/bands/{identifier}/download')
    async def download(identifier: str):
        path = folder(identifier)
        manifest = json.loads((path / 'manifest.json').read_text())
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name in ['manifest.json', 'preview.png']+manifest['order']:
                archive.write(path/name, name)
        return Response(buffer.getvalue(), media_type='application/zip', headers={'Content-Disposition':'attachment; filename="photo-bands.zip"'})
    @router.post('/api/internal/bands/{identifier}/print')
    async def send(identifier: str, resume: bool = False):
        folder(identifier)
        if not runtime.address:
            raise HTTPException(409, 'Aucune imprimante configurée au lancement.')
        if db.get_setting('bridge_mode','bluetooth') != 'bluetooth':
            raise HTTPException(409, 'Cet atelier utilise le Bluetooth local, pas le relais distant.')
        if identifier in runtime.tasks:
            raise HTTPException(409, 'Cette série est déjà en cours.')
        (folder(identifier) / 'job.json').write_text(json.dumps({'status':'queued', 'message':'En attente de l’imprimante.'}))
        runtime.tasks[identifier] = asyncio.create_task(runtime.send(identifier, resume))
        return JSONResponse({'status':'queued'}, status_code=202)
    @router.post('/api/internal/bands/{identifier}/cancel')
    async def cancel(identifier: str):
        folder(identifier)
        task = runtime.tasks.get(identifier)
        if task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            runtime.tasks.pop(identifier, None)
            (folder(identifier) / 'job.json').write_text(json.dumps({'status':'cancelled', 'message':'Envoi annulé ; contrôlez le papier.'}))
        return {'status':'cancellation_requested'}
    app.include_router(router)

    @app.middleware('http')
    async def navigation_and_session(request, call_next):
        # Protect both the extension and TinyPOS admin surfaces with the verified login session.
        path = request.url.path
        internal_api = path.startswith('/api/internal/')
        admin_page = any(path == prefix or path.startswith(prefix+'/') for prefix in
                         ('/test', '/settings', '/playground', '/api-keys', '/documentation', '/photo-bands'))
        valid_session = secrets.compare_digest(request.cookies.get('driver_session', ''), runtime.session)
        if (internal_api or admin_page) and not valid_session:
            if internal_api:
                return JSONResponse({'detail':'Connexion TinyPOS nécessaire.'}, status_code=401)
            response = RedirectResponse('/login', status_code=303)
            response.delete_cookie('tinypos_session')
            return response
        if internal_api and request.method not in ('GET', 'HEAD'):
            origin = request.headers.get('origin')
            if origin and origin != str(request.base_url).rstrip('/'):
                return JSONResponse({'detail':'Origine non autorisée.'}, status_code=403)
        if request.url.path == '/login' and request.method == 'GET' and request.cookies.get('tinypos_session') and request.cookies.get('driver_session') != runtime.session:
            response = RedirectResponse('/login', status_code=303)
            response.delete_cookie('tinypos_session')
            return response
        response = await call_next(request)
        if request.url.path == '/login' and request.method == 'POST' and response.status_code in (302,303) and response.headers.get('location') == '/test':
            response.set_cookie('driver_session', runtime.session, httponly=True, samesite='strict')
        if request.url.path == '/logout':
            response.delete_cookie('driver_session')
        if 'text/html' in response.headers.get('content-type',''):
            body = b''.join([part async for part in response.body_iterator])
            marker = b'<ul class="nav nav-pills flex-column mb-0">'
            link = b'<li class="nav-item"><a href="/photo-bands" class="nav-link">Atelier photo en bandes</a></li>'
            if request.url.path == '/photo-bands':
                link = link.replace(b'class="nav-link"', b'class="nav-link active" aria-current="page"')
            body = body.replace(marker, marker+link, 1)
            body = body.replace(
                b"printerBadge.innerHTML = '<i class=\"bi bi-check-circle-fill me-1\"></i>Bainiu / X6';",
                b"printerBadge.textContent = data.printer_name || 'Imprimante BLE';")
            body = body.replace(b'384 Dots (57mm)', b'384 points (48 mm utiles)')
            headers = dict(response.headers)
            headers.pop('content-length', None)
            return Response(body, status_code=response.status_code, headers=headers, media_type='text/html')
        return response
    app.state.bands = runtime
    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tinypos-path', required=True)
    parser.add_argument('--address')
    parser.add_argument('--data-dir', default='private/web-bands')
    parser.add_argument('--port', type=int, default=8100)
    args = parser.parse_args()
    import uvicorn
    app = build_app(args.tinypos_path, args.data_dir, args.address)
    uvicorn.run(app, host='127.0.0.1', port=args.port)


if __name__ == '__main__':
    main()
