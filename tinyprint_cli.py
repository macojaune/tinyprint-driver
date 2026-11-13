#!/usr/bin/env python3
"""
tinyprint_cli.py - standalone driver for Bainiu / "Tiny Print" BLE thermal printers
(MINIPRINT C15, X5/X6/X7, iPrint, GB01 family).

Protocol (reverse engineered, confirmed by TinyPOS-Bridge):
  frame: 51 78 <cmd> 00 <len_lo> <len_hi> <payload...> <crc8(payload)> FF
  A3  get device state
  A4  set quality (200 dpi)
  AF  set energy (uint16 LE)
  BD  set speed (1)
  BE  apply energy
  A6  lattice start / end (0x0B payload)
  A2  raster row (48 bytes = 384 dots, LSB first, 1 = burn)
  A1  feed paper (payload 60 00)

Usage:
  python tinyprint_cli.py scan
  python tinyprint_cli.py info  [--address ADDR]
  python tinyprint_cli.py test  [--address ADDR]
  python tinyprint_cli.py text "hello" [--address ADDR] [--strength 1-7]
  python tinyprint_cli.py image file.png [--address ADDR]
"""
import argparse, asyncio, sys, time, math
from bleak import BleakClient, BleakScanner
from transport import PrinterSession, FaultDetected, StateUnavailable

from protocol import (
    WIDTH,
    HEADER,
    FOOTER,
    crc8,
    make_packet,
    CMD_GET_DEV_STATE,
    CMD_GET_DEV_INFO,
    CMD_SET_QUALITY,
    CMD_APPLY_ENERGY,
    CMD_LATTICE_START,
    CMD_LATTICE_END,
    CMD_FEED,
    CMD_SET_SPEED,
    parse_state,
)

STRENGTH = {1:(8000,0.010,128),2:(11000,0.012,135),3:(14500,0.014,142),4:(18500,0.016,150),
            5:(22500,0.019,162),6:(26500,0.022,174),7:(30000,0.026,185)}

KNOWN_NAMES = ["c15","miniprint","x5","x6","x7","x1","x2","x8","c9","gb01","iprint","tiny print",
               "tinyprint","pocket printer","sc03","rt034","mx0","bainiu"]

def looks_like_printer(name, svc):
    n = (name or "").lower()
    if any(k in n for k in KNOWN_NAMES):
        return True
    return any(s in u for u in svc for s in ("ae30","af30","ff00"))

async def find(timeout=12.0, address=None):
    if address:
        d = await BleakScanner.find_device_by_address(address, timeout=timeout)
        if d:
            return d
    found, seen = [], set()
    def cb(dev, adv):
        svc = [str(u).lower() for u in (adv.service_uuids or [])]
        if looks_like_printer(dev.name or adv.local_name, svc) and dev.address not in seen:
            seen.add(dev.address)
            found.append(dev)
            print(f"  printer candidate: {dev.name!r} {dev.address} rssi={adv.rssi} svc={svc}")
    s = BleakScanner(detection_callback=cb)
    await s.start(); await asyncio.sleep(timeout); await s.stop()
    return found[0] if found else None

def find_tx(client):
    for service in client.services:
        for ch in service.characteristics:
            u = str(ch.uuid).lower()
            if "ae01" in u or "ff02" in u or "8841" in u:
                return ch
    for service in client.services:
        for ch in service.characteristics:
            if "write" in ch.properties:
                return ch
    return None

async def cmd_scan():
    print("Scanning 12s ...")
    seen = 0
    def cb(dev, adv):
        nonlocal seen
        seen += 1
        svc = [str(u) for u in (adv.service_uuids or [])]
        tag = " <== PRINTER?" if looks_like_printer(dev.name or adv.local_name, svc) else ""
        print(f"{dev.name!r:34} {dev.address} rssi={adv.rssi}{tag}")
    s = BleakScanner(detection_callback=cb)
    await s.start(); await asyncio.sleep(12); await s.stop()
    print(f"{seen} devices seen")

async def connect(args):
    dev = await find(timeout=args.timeout, address=args.address)
    if not dev:
        print("Printer not found. Power it on (LED pulsing green) and disconnect the phone app.")
        return None, None
    print(f"Connecting to {dev.name!r} {dev.address} ...")
    client = BleakClient(dev, timeout=20)
    await client.connect()
    print(f"Connected. MTU={getattr(client,'mtu',None)}")
    tx = find_tx(client)
    if not tx:
        print("No writable characteristic found!")
        return client, None
    return client, tx

async def cmd_info(args):
    client, tx = await connect(args)
    if not client:
        return
    try:
        for service in client.services:
            print(f"service {service.uuid} {service.description}")
            for ch in service.characteristics:
                print(f"   char {ch.uuid} {ch.properties} {ch.description}")
        print(f"\nTX = {tx.uuid if tx else None}")
        if tx:
            got = []
            def on_notify(_c, data: bytearray):
                got.append(bytes(data)); print("  notify:", bytes(data).hex(" "))
            for service in client.services:
                for ch in service.characteristics:
                    if "notify" in ch.properties:
                        try: await client.start_notify(ch, on_notify)
                        except Exception as e: print("notify fail", ch.uuid, e)
            await client.write_gatt_char(tx, CMD_GET_DEV_STATE, response=False)
            await asyncio.sleep(0.6)
            await client.write_gatt_char(tx, CMD_GET_DEV_INFO, response=False)
            await asyncio.sleep(1.2)
            print(f"\nstate responses: {len(got)}")
            for g in got:
                if len(g) > 7 and g[2] == 0xA8:
                    payload = g[6:-2]
                    ver = "".join(chr(b) for b in payload if 32 <= b < 127)
                    print(f"firmware/version string: {ver!r}  (payload {payload.hex(' ')})")
                elif len(g) > 7 and g[2] == 0xA3:
                    print(f"state A3 payload: {g[6:-2].hex(' ')}")
    finally:
        await client.disconnect()

def rows_from_image(img, threshold=150):
    from PIL import Image
    if img.mode != "1":
        img = img.convert("L")
    w, h = img.size
    px = img.load()
    out = []
    for y in range(h):
        row = bytearray(w // 8)
        for x in range(w):
            v = px[x, y]
            black = (v == 0) if img.mode == "1" else (v < threshold)
            if black:
                row[x // 8] |= 1 << (x % 8)
        out.append(bytes(row))
    return out

def text_image(text, width=WIDTH, size=32):
    from PIL import Image, ImageDraw, ImageFont
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", size)
    except Exception:
        font = ImageFont.load_default()
    dummy = Image.new("L", (10, 10))
    d = ImageDraw.Draw(dummy)
    box = d.multiline_textbbox((0, 0), text, font=font, spacing=6)
    img = Image.new("L", (width, box[3] + 24), 255)
    d = ImageDraw.Draw(img)
    d.multiline_text((8, 8), text, font=font, fill=0, spacing=6)
    return img


BAYER8 = [
    [0,32,8,40,2,34,10,42],[48,16,56,24,50,18,58,26],
    [12,44,4,36,14,46,6,38],[60,28,52,20,62,30,54,22],
    [3,35,11,43,1,33,9,41],[51,19,59,27,49,17,57,25],
    [15,47,7,39,13,45,5,37],[63,31,55,23,61,29,53,21],
]

def dither(img, method="floyd", gain=1.0, invert=False):
    """Return a 1-bit image suitable for the thermal head. 1 = black."""
    from PIL import Image, ImageOps, ImageEnhance
    g = img.convert("L")
    g = ImageOps.autocontrast(g, cutoff=1)
    if gain != 1.0:
        lut = [min(255, int((v / 255.0) ** (1.0 / gain) * 255)) for v in range(256)]
        g = g.point(lut)
    if invert:
        g = ImageOps.invert(g)
    w, h = g.size
    px = g.load()
    out = Image.new("1", (w, h), 1)  # white
    op = out.load()

    if method == "none":
        for y in range(h):
            for x in range(w):
                op[x, y] = 0 if px[x, y] < 128 else 1
        return out

    if method == "bayer":
        for y in range(h):
            for x in range(w):
                t = (BAYER8[y % 8][x % 8] + 0.5) / 64.0 * 255.0
                op[x, y] = 0 if px[x, y] < t else 1
        return out

    # error diffusion
    buf = [[float(px[x, y]) for x in range(w)] for y in range(h)]
    if method == "atkinson":
        coeffs = [(1, 0, 1/8), (2, 0, 1/8), (-1, 1, 1/8),
                  (0, 1, 1/8), (1, 1, 1/8), (0, 2, 1/8)]
        for y in range(h):
            for x in range(w):
                old = buf[y][x]
                new = 255.0 if old > 127 else 0.0
                op[x, y] = 0 if new == 0 else 1
                err = (old - new) / 8.0
                for dx, dy, _ in coeffs:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < w and 0 <= ny < h:
                        buf[ny][nx] += err
        return out

    # Floyd-Steinberg
    for y in range(h):
        for x in range(w):
            old = buf[y][x]
            new = 255.0 if old > 127 else 0.0
            op[x, y] = 0 if new == 0 else 1
            err = old - new
            if x + 1 < w: buf[y][x + 1] += err * 7 / 16
            if y + 1 < h:
                if x > 0: buf[y + 1][x - 1] += err * 3 / 16
                buf[y + 1][x] += err * 5 / 16
                if x + 1 < w: buf[y + 1][x + 1] += err * 1 / 16
    return out

def fit_width(img, width=WIDTH):
    if img.width != width:
        h = max(1, round(img.height * width / img.width))
        img = img.resize((width, h), getattr(__import__("PIL.Image", fromlist=["Image"]), "LANCZOS"))
    return img


def pdf_pages(path, width=WIDTH, page_gap=28, max_pages=None):
    """Render a PDF to one tall grayscale strip, `width` dots wide, with white gaps."""
    import fitz
    from PIL import Image
    doc = fitz.open(path)
    pages = []
    for i, page in enumerate(doc):
        if max_pages and i >= max_pages:
            break
        zoom = width / page.rect.width
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), colorspace=fitz.csGRAY, alpha=False)
        im = Image.frombytes("L", (pix.width, pix.height), pix.samples)
        if im.width != width:
            im = im.resize((width, max(1, round(im.height * width / im.width))), Image.LANCZOS)
        pages.append(im)
    if not pages:
        raise SystemExit("PDF vide")
    gap = Image.new("L", (width, page_gap), 255)
    out = Image.new("L", (width, sum(p.height for p in pages) + page_gap * (len(pages) - 1)), 255)
    y = 0
    for i, p in enumerate(pages):
        out.paste(p, (0, y))
        y += p.height
        if i != len(pages) - 1:
            y += page_gap
    return out, len(pages)


def slice_image(img, direction, count=None, strip=None):
    """Cut `img` into strips. Returns list of (index, PIL image) in assembly order."""
    W, H = img.size
    if direction == "vertical":
        n = count if count else max(1, round(W / strip))
        n = max(1, min(n, W))
        edges = [round(i * W / n) for i in range(n + 1)]
        return [(i + 1, img.crop((edges[i], 0, edges[i + 1], H))) for i in range(n)]
    n = count if count else max(1, round(H / strip))
    n = max(1, min(n, H))
    edges = [round(i * H / n) for i in range(n + 1)]
    return [(i + 1, img.crop((0, edges[i], W, edges[i + 1]))) for i in range(n)]


def strip_to_print(img, width=WIDTH):
    """Scale a strip so it fills the 384-dot head, keeping proportions."""
    h = max(1, round(img.height * width / img.width))
    from PIL import Image
    return img.resize((width, h), Image.LANCZOS)


def assemble(strips, direction, gap_rows=8, gap_cols=8, labels=True):
    """Contact sheet of the strips, to check the order before printing."""
    from PIL import Image, ImageDraw
    if direction == "vertical":
        w = sum(s.width for s in strips) + gap_cols * (len(strips) - 1)
        h = max(s.height for s in strips)
        out = Image.new("L", (w, h), 255)
        x = 0
        for i, s in enumerate(strips):
            out.paste(s, (x, 0))
            if labels:
                d = ImageDraw.Draw(out)
                d.rectangle([x, 0, x + 22, 16], fill=255)
                d.text((x + 4, 2), str(i + 1), fill=0)
            x += s.width + gap_cols
    else:
        w = max(s.width for s in strips)
        h = sum(s.height for s in strips) + gap_rows * (len(strips) - 1)
        out = Image.new("L", (w, h), 255)
        y = 0
        for i, s in enumerate(strips):
            out.paste(s, (0, y))
            if labels:
                d = ImageDraw.Draw(out)
                d.rectangle([0, y, 22, y + 16], fill=255)
                d.text((4, y + 2), str(i + 1), fill=0)
            y += s.height + gap_rows
    return out




async def query_state(client, tx, timeout=1.5):
    if isinstance(client, PrinterSession):
        try:
            return await client.sample(timeout=timeout)
        except StateUnavailable:
            return None
    got = []
    sub = None
    for s in client.services:
        for ch in s.characteristics:
            if "ae02" in str(ch.uuid).lower():
                sub = ch
    if sub is None:
        return None
    try:
        await client.start_notify(sub, lambda _c, d: got.append(bytes(d)))
        await client.write_gatt_char(tx, CMD_GET_DEV_STATE, response=False)
        waited = 0.0
        while waited < timeout and not got:
            await asyncio.sleep(0.1)
            waited += 0.1
    finally:
        try:
            await client.stop_notify(sub)
        except Exception:
            pass
    for g in got:
        st = parse_state(g)
        if st:
            return st
    return None




def choose_pause_rows(rows, chunk, lookahead=48):
    """Pause after a light row, without exceeding chunk rows between stops."""
    if chunk < 0 or lookahead < 0:
        raise ValueError("chunk and smart window must be non-negative")
    if not chunk or chunk >= len(rows):
        return set()
    counts = [sum(b.bit_count() for b in r) for r in rows]
    pauses, previous = set(), 0
    while previous + chunk < len(rows):
        target = previous + chunk
        start = max(previous + 1, target - lookahead)
        # Later rows win ties so blank areas do not create extra stops.
        best = min(range(start, target + 1), key=lambda n: (counts[n - 1], -n))
        pauses.add(best)
        previous = best
    return pauses


async def stream_job(client, tx, rows, energy, delay, label="", chunk=0, chunk_pause=0,
                     probe=None, smart_pause=True, smart_window=48):
    """Send one self-contained job: header, raster rows, end lattice, feed.

    With chunk/chunk_pause, the lattice stays open and the paper stops between
    chunks. Physical pause marks may remain visible.
    """
    seq = [CMD_GET_DEV_STATE, CMD_SET_QUALITY,
           make_packet(0xAF, bytes([energy & 0xFF, energy >> 8])),
           CMD_SET_SPEED, CMD_APPLY_ENERGY, CMD_LATTICE_START]
    for p in seq:
        await client.write_gatt_char(tx, p, response=False)
        await asyncio.sleep(0.03)
    pauses = choose_pause_rows(rows, chunk, smart_window) if (chunk and smart_pause) else set()
    print(f"{label}{len(rows)} lignes  (energie={energy}"
          f"{', %d pauses' % len(pauses) if pauses else ''})")
    total = len(rows)
    for i, r in enumerate(rows, 1):
        await client.write_gatt_char(tx, make_packet(0xA2, r), response=False)
        if delay:
            await asyncio.sleep(delay)
        if i % 200 == 0:
            print(f"  {label}{i}/{total}", end="\r", flush=True)
        boundary = (i in pauses) if pauses else (chunk and i % chunk == 0)
        if boundary and i < total:
            print()
            if chunk_pause:
                await asyncio.sleep(chunk_pause)
            if probe:
                st = await probe()
                print(f"  {label}pause a {i}/{total}"
                      + (f" (byte2={st['temp']} flags=0x{st['flags']:02x})" if st else ""))
                if st and st["overheat"]:
                    raise FaultDetected(st)
    if total >= 200:
        print()


async def finish_job(client, tx, feed_rows=96):
    await asyncio.sleep(0.08)
    await client.write_gatt_char(tx, CMD_LATTICE_END, response=False)
    await asyncio.sleep(0.08)
    await client.write_gatt_char(tx, make_packet(0xA1, bytes([feed_rows & 0xFF, feed_rows >> 8])),
                                 response=False)
    await asyncio.sleep(0.5)


async def wait_cooling(client, tx, seconds, cool_max, label=""):
    """Pause, then keep polling until the fault bit clears."""
    print(f"{label}pause {seconds:g} s (decoupe + refroidissement)")
    await asyncio.sleep(seconds)
    st = await query_state(client, tx)
    waited = 0.0
    while st and st["overheat"] and waited < cool_max:
        print(f"  defaut encore leve (byte2={st['temp']}) -> +5 s")
        await asyncio.sleep(5)
        waited += 5
        st = await query_state(client, tx) or st
    if st:
        print(f"  etat: byte2={st['temp']} flags=0x{st['flags']:02x}"
              f"{' defaut' if st['overheat'] else ' ok'}")
    return st


async def preflight(client, tx, args):
    st = await query_state(client, tx)
    if st is None:
        print("etat: pas de reponse A3 (arret preventif)")
        return None
    print(f"etat initial: byte2={st['temp']} flags=0x{st['flags']:02x}")
    waited = 0.0
    while st["overheat"] and not args.force and waited < args.fault_wait:
        print(f"  defaut leve (0x04) : l'imprimante accepte les donnees mais n'imprime pas.")
        print(f"  attente {waited:g}/{args.fault_wait:g} s ...")
        await asyncio.sleep(5)
        waited += 5
        st = await query_state(client, tx) or st
    return st


async def cmd_status(args):
    client, tx = await connect(args)
    if not client:
        return 1
    try:
        st = await query_state(client, tx, timeout=4.0)
        if not st:
            print("aucune reponse A3")
            return 1
        print(f"flags   : 0x{st['flags']:02x}  (bits: "
              f"{','.join(str(b) for b in range(8) if st['flags'] & (1 << b)) or 'aucun'})")
        print(f"byte2   : {st['temp']}  (probablement temperature ou niveau batterie, non confirme)")
        print(f"payload : {st['raw']}")
        return 0 if not st["overheat"] else 3
    finally:
        await client.disconnect()


async def print_image(args, img):
    energy, delay, thr = STRENGTH[max(1, min(7, args.strength))]
    rows = rows_from_image(img, thr)
    feed_rows = args.feed_rows if args.feed_rows else max(1, round(args.feed_mm * 8))
    client, tx = await connect(args)
    if not client:
        return 1
    try:
        def log_session(event, **fields):
            if event in ("flow_stop", "flow_resume", "flow_wait_start", "flow_wait_end"):
                print(f"{event}: {fields}", flush=True)
        client = PrinterSession(client, tx, log_session)
        await client.subscribe()
        st = await preflight(client, tx, args)
        if st is None:
            return 2
        if st["flags"] == 0:
            client.fault = None
        if st and st["flags"] != 0 and not args.force:
            print("l'imprimante est encore en defaut : rien ne sortirait.")
            print("Laisse-la reposer (le defaut est retombe seul lors des essais), puis relance.")
            return 2
        await stream_job(client, tx, rows, energy, delay,
                         chunk=args.chunk_rows, chunk_pause=args.chunk_pause,
                         probe=lambda: query_state(client, tx),
                         smart_pause=args.smart_pause, smart_window=args.smart_window)
        await finish_job(client, tx, feed_rows)
        post = await query_state(client, tx, timeout=4.0)
        if post is None:
            raise StateUnavailable("No final A3 state")
        if client.fault:
            raise FaultDetected(client.fault["state"])
        if post["flags"] != 0:
            raise StateUnavailable(f"Final flags: 0x{post['flags']:02x}")
        print("envoi termine ; controle papier necessaire")
        return 0
    except FaultDetected as e:
        print(f"\ndefaut en cours de job (byte2={e.state['temp']} flags=0x{e.state['flags']:02x}) :")
        print("job interrompu, l'impression est incomplete.")
        return 3
    except StateUnavailable as exc:
        print(f"Transport interrompu, impression non confirmee: {exc}")
        return 3
    finally:
        await client.disconnect()


def load_state(outdir):
    import json, os
    p = os.path.join(outdir, "state.json")
    if os.path.exists(p):
        try:
            with open(p) as fh:
                return json.load(fh)
        except Exception:
            pass
    return {"done": [], "failed": None}


def save_state(outdir, state):
    import json, os, datetime
    state["updated"] = datetime.datetime.now().isoformat(timespec="seconds")
    p = os.path.join(outdir, "state.json")
    tmp = p + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(state, fh, indent=2, ensure_ascii=False)
    os.replace(tmp, p)


async def print_series(args, strips, outdir, start=1):
    """One job per strip, with a cooling pause between strips. Resumable."""
    energy, delay, thr = STRENGTH[max(1, min(7, args.strength))]
    feed_rows = args.feed_rows if args.feed_rows else max(1, round(args.feed_mm * 8))
    rows_list = [(i, rows_from_image(s, thr)) for i, s in enumerate(strips, 1)]
    state = load_state(outdir) if args.resume else {"done": [], "failed": None}
    done = set(state.get("done") or [])
    if done:
        print(f"reprise : {len(done)} bande(s) deja imprimee(s) -> {sorted(done)}")
    client, tx = await connect(args)
    if not client:
        return 1
    try:
        def log_session(event, **fields):
            if event in ("flow_stop", "flow_resume", "flow_wait_start", "flow_wait_end"):
                print(f"{event}: {fields}", flush=True)
        client = PrinterSession(client, tx, log_session)
        await client.subscribe()
        st = await preflight(client, tx, args)
        if st is None:
            return 2
        if st["flags"] == 0:
            client.fault = None
        if st and st["flags"] != 0 and not args.force:
            print("l'imprimante est encore en defaut : les donnees seraient avalees sans imprimer.")
            print("Laisse-la reposer (le defaut est retombe seul lors des essais), puis relance avec --resume.")
            return 2
        for idx, rows in rows_list:
            if idx < start or idx in done:
                print(f"bande {idx}/{len(rows_list)} : deja faite, sautee")
                continue
            print(f"\nbande {idx}/{len(rows_list)}")
            state["failed"] = idx
            state["done"] = sorted(done)
            state["total"] = len(rows_list)
            save_state(outdir, state)
            try:
                await stream_job(client, tx, rows, energy, delay, label=f"[{idx}] ",
                                 chunk=args.chunk_rows, chunk_pause=args.chunk_pause,
                                 probe=lambda: query_state(client, tx),
                                 smart_pause=args.smart_pause, smart_window=args.smart_window)
            except FaultDetected as e:
                print(f"\n  defaut pendant la bande {idx} "
                      f"(byte2={e.state['temp']} flags=0x{e.state['flags']:02x}).")
                print(f"  Le job est casse, la bande {idx} est incomplete : elle sera refaite.")
                state["failed"] = idx
                state["done"] = sorted(done)
                state["total"] = len(rows_list)
                save_state(outdir, state)
                return 3
            await finish_job(client, tx, feed_rows)
            post = await query_state(client, tx, timeout=4.0)
            if post is None:
                await asyncio.sleep(1.5)
                post = await query_state(client, tx, timeout=4.0)
            if post:
                print(f"  etat apres bande {idx}: byte2={post['temp']} flags=0x{post['flags']:02x}")
            else:
                print(f"  etat apres bande {idx}: pas de reponse (non confirme)")
                raise StateUnavailable("No final A3 state; strip remains pending")
            if post and (post["flags"] != 0 or client.fault):
                print(f"  defaut detecte pendant la bande {idx} : elle est probablement")
                print(f"  incomplete a la fin. Elle ne sera pas notee comme faite.")
                state["failed"] = idx
                state["done"] = sorted(done)
                state["total"] = len(rows_list)
                save_state(outdir, state)
                print("Relance avec --resume une fois le defaut retombe.")
                return 3
            done.add(idx)
            state["done"] = sorted(done)
            state["failed"] = None
            state["total"] = len(rows_list)
            save_state(outdir, state)
            print(f"bande {idx} : terminee")
            if idx != len(rows_list):
                st = await wait_cooling(client, tx, args.cooldown, args.cool_max,
                                        label=f"[{idx}] ")
                if st and st["flags"] != 0 and not args.force:
                    print("defaut persistant : arret preventif.")
                    print("Relance la meme commande avec --resume apres une pause.")
                    state["failed"] = idx + 1
                    save_state(outdir, state)
                    return 3
        print(f"\nserie envoyee : {len(done)}/{len(rows_list)} bandes ; controle papier necessaire")
        return 0
    except (StateUnavailable, FaultDetected) as exc:
        print(f"Transport interrompu, serie non confirmee: {exc}")
        return 3
    finally:
        await client.disconnect()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["scan","info","status","test","text","image","pdf","tile","tile-send","dump"])
    ap.add_argument("value", nargs="?")
    ap.add_argument("--address")
    ap.add_argument("--strength", type=int, default=3)
    ap.add_argument("--dither", default=None, choices=["floyd", "atkinson", "bayer", "none"])
    ap.add_argument("--gain", type=float, default=1.0)
    ap.add_argument("--preview")
    ap.add_argument("--no-print", action="store_true")
    ap.add_argument("--pages", type=int, default=None)
    ap.add_argument("--gap", type=int, default=16)
    ap.add_argument("--dir", dest="direction", default="vertical", choices=["vertical", "horizontal"])
    ap.add_argument("--count", type=int, default=None)
    ap.add_argument("--mm", type=float, default=None)
    ap.add_argument("--strip", type=int, default=None)
    ap.add_argument("--outdir", default="strips")
    ap.add_argument("--rotate", type=int, default=0)
    ap.add_argument("--label", action="store_true")
    ap.add_argument("--flat", action="store_true")
    ap.add_argument("--send", action="store_true")
    ap.add_argument("--cooldown", type=float, default=45.0)
    ap.add_argument("--cool-max", type=float, default=180.0)
    ap.add_argument("--fault-wait", type=float, default=600.0)
    ap.add_argument("--feed-mm", type=float, default=10.0)
    ap.add_argument("--feed-rows", type=int, default=0)
    ap.add_argument("--chunk-rows", type=int, default=400)
    ap.add_argument("--chunk-pause", type=float, default=6.0)
    ap.add_argument("--no-smart-pause", dest="smart_pause", action="store_false")
    ap.add_argument("--smart-window", type=int, default=48)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--start", type=int, default=1)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--timeout", type=float, default=12.0)
    a = ap.parse_args()
    if a.chunk_rows < 0 or a.smart_window < 0 or a.chunk_pause < 0:
        ap.error("chunk-rows, smart-window and chunk-pause must be non-negative")

    if a.action == "scan":
        asyncio.run(cmd_scan()); return
    if a.action == "info":
        asyncio.run(cmd_info(a)); return
    if a.action == "status":
        sys.exit(asyncio.run(cmd_status(a)))
    if a.action == "dump":
        img = text_image(a.value or "hello")
        rows = rows_from_image(img, STRENGTH[a.strength][2])
        data = CMD_GET_DEV_STATE + CMD_SET_QUALITY + CMD_LATTICE_START
        data += b"".join(make_packet(0xA2, r) for r in rows) + CMD_LATTICE_END + CMD_FEED
        open("stream.bin","wb").write(data)
        print(f"{len(rows)} rows, {len(data)} bytes -> stream.bin"); return
    if a.action == "tile-send":
        import os, json
        from PIL import Image
        with open(a.value) as fh:
            m = json.load(fh)
        base = os.path.dirname(os.path.abspath(a.value))
        imgs = []
        for p in m["order"]:
            im = Image.open(os.path.join(base, os.path.basename(p)))
            if im.mode != "1":
                im = im.convert("1")
            imgs.append(im)
        print(f"{len(imgs)} bandes, {sum(i.height for i in imgs)} lignes au total")
        if a.no_print:
            print("render only")
            return
        sys.exit(asyncio.run(print_series(a, imgs, base)))

    if a.action == "tile":
        import os, json
        from PIL import Image, ImageDraw
        orig = Image.open(a.value)
        if a.rotate:
            orig = orig.rotate(-a.rotate, expand=True)
        count = a.count
        if not count and a.mm:
            count = max(1, math.ceil(a.mm * 8.0 / WIDTH))  # 8 dots/mm ~ 203 dpi
            print(f"taille cible {a.mm:g} mm -> {count} bandes (48 mm chacune)")
        strips = slice_image(orig, a.direction, count, a.strip)
        outdir = a.outdir
        os.makedirs(outdir, exist_ok=True)
        n = len(strips)
        method = a.dither or "none"
        ready, files = [], []
        rotate_strips = (a.direction == "horizontal" and not a.flat)
        for idx, s in strips:
            if rotate_strips:
                s = s.rotate(-90, expand=True)
            p = strip_to_print(s)
            p = dither(p, method, a.gain)
            if a.label:
                d = ImageDraw.Draw(p)
                txt = f"{idx}/{n}"
                tw = d.textlength(txt)
                d.rectangle([0, 0, int(tw) + 9, 13], fill=255)
                d.text((4, 2), txt, fill=0)
            fn = os.path.join(outdir, f"{idx:02d}.png")
            p.save(fn)
            files.append(fn)
            ready.append(p)
            print(f"  {fn}  {p.width}x{p.height} px")
        heights = [p.height for p in ready]
        total = sum(heights) + a.gap * (n - 1)
        if a.direction == "vertical":
            final_dots = (n * WIDTH, heights[0])
        elif rotate_strips:
            final_dots = (heights[0], n * WIDTH)
        else:
            final_dots = (WIDTH, sum(heights))
        if a.direction == "vertical":
            assembly = "coller cote a cote, de gauche a droite"
        elif rotate_strips:
            assembly = "remettre chaque ticket a l'endroit (rotation 90 sens horaire) puis empiler de haut en bas"
        else:
            assembly = "empiler de haut en bas"
        manifest = {
            "source": os.path.abspath(a.value),
            "direction": a.direction,
            "strips": n,
            "strip_size": [WIDTH, heights[0]],
            "gap_rows": a.gap,
            "order": files,
            "assembly": assembly,
            "strip_rotation_deg": 90 if rotate_strips else 0,
            "final_size_mm": [round(final_dots[0] / 8.0, 1), round(final_dots[1] / 8.0, 1)],
            "total_height_px": total,
            "strength": a.strength,
            "cooldown_s": a.cooldown,
            "feed_rows_between_strips": a.feed_rows if a.feed_rows else max(1, round(a.feed_mm * 8)),
        }
        with open(os.path.join(outdir, "manifest.json"), "w") as fh:
            json.dump(manifest, fh, indent=2, ensure_ascii=False)
        with open(os.path.join(outdir, "print-all.sh"), "w") as fh:
            fh.write("#!/bin/sh\n# imprime les bandes dans l'ordre\nset -e\n")
            fh.write(f'cd "$(dirname "$0")"\n')
            fh.write(f'exec ../.venv/bin/python ../tools/tinyprint_cli.py tile-send manifest.json --strength {a.strength} --cooldown {a.cooldown:g} --resume\n')
        os.chmod(os.path.join(outdir, "print-all.sh"), 0o755)
        print(f"\n{n} bande(s) {WIDTH}x{heights[0]} px, {a.direction}, total {total} px")
        print(f"format final ~ {manifest['final_size_mm'][0]:g} x {manifest['final_size_mm'][1]:g} mm")
        print(f"ordre : {manifest['assembly']}")
        if a.preview:
            prev = ready
            if rotate_strips:
                prev = [p.rotate(90, expand=True) for p in ready]
            sheet = assemble(prev, a.direction, gap_rows=22, gap_cols=22).convert("L")
            if sheet.width > 1400:
                r = 1400 / sheet.width
                sheet = sheet.resize((1400, max(1, round(sheet.height * r))), Image.LANCZOS)
            sheet.save(a.preview)
            print(f"assemblage -> {a.preview}")
        if not a.send:
            print("export seulement (--send pour imprimer)")
            return
        sys.exit(asyncio.run(print_series(a, ready, outdir)))

    if a.action == "test":
        img = text_image("TINY PRINT\nOK 384 dots\nline 3")
    elif a.action == "text":
        img = text_image(a.value or "hello")
    elif a.action == "pdf":
        from PIL import Image
        strip, npages = pdf_pages(a.value, page_gap=a.gap, max_pages=a.pages)
        method = a.dither or "none"
        img = dither(strip, method, a.gain)
        print(f"{npages} page(s) -> render {img.width}x{img.height} px, dither={method}")
        if a.preview:
            scale = 2 if img.height <= 2400 else 1
            img.convert("L").resize((img.width * scale, img.height * scale), Image.NEAREST).save(a.preview)
            print(f"preview -> {a.preview}")
    else:
        from PIL import Image
        img = fit_width(Image.open(a.value))
        method = a.dither or "floyd"
        img = dither(img, method, a.gain)
        if a.preview:
            img.convert("L").resize((img.width * 2, img.height * 2), Image.NEAREST).save(a.preview)
            print(f"preview -> {a.preview}")
    if a.no_print:
        print(f"render only: {img.width}x{img.height} px")
        return
    sys.exit(asyncio.run(print_image(a, img)))

if __name__ == "__main__":
    main()
