#!/usr/bin/env python3
"""Controlled hardware experiments. Dry-run unless --execute is explicit."""
import argparse
import asyncio
import datetime
import hashlib
import json
import time
from pathlib import Path
from types import SimpleNamespace

from PIL import Image
import tinyprint_cli as driver

SCENARIOS = {
    "single-pause": {"energy": 14500, "delay": .014, "pause_seconds": 10},
    "low-energy": {"energy": 4000, "delay": .014, "pause_seconds": 0},
    "baseline": {"energy": 14500, "delay": .014, "pause_seconds": 0},
    "slow-cadence": {"energy": 14500, "delay": .028, "pause_seconds": 0},
}


class StateUnavailable(RuntimeError):
    pass


class Monitor:
    """Wrap raster writes; request telemetry without waiting between rows."""
    def __init__(self, client, tx, log, pause_at=None, pause_seconds=0):
        self.client, self.tx, self.log = client, tx, log
        self.pause_at, self.pause_seconds = pause_at, pause_seconds
        self.rows = self.strip = self.strip_rows = self.burn_dots = 0
        self.latest = None
        self.sequence = 0
        self.fault = None
        self.subscription = None

    async def subscribe(self):
        for service in self.client.services:
            for ch in service.characteristics:
                if "ae02" in str(ch.uuid).lower() and "notify" in ch.properties:
                    self.subscription = ch
        if self.subscription is None:
            raise StateUnavailable("No AE02 notification characteristic")
        await self.client.start_notify(self.subscription, self.notify)

    def notify(self, _ch, data):
        data = bytes(data)
        state = driver.parse_state(data)
        valid = (len(data) >= 8 and data[:2] == driver.HEADER
                 and len(data) == int.from_bytes(data[4:6], "little") + 8
                 and data[-1] == 255 and driver.crc8(data[6:-2]) == data[-2])
        self.log("notification", frame=data.hex(" "), valid=valid,
                 state=state, rows_sent=self.rows, strip=self.strip,
                 strip_rows_sent=self.strip_rows)
        if state and valid:
            self.latest = state
            self.sequence += 1
            if state["flags"] & 4 and self.fault is None:
                self.fault = {"rows_sent": self.rows, "strip": self.strip,
                              "strip_rows_sent": self.strip_rows, "state": state}

    async def sample(self, timeout=4):
        previous = self.sequence
        await self.client.write_gatt_char(self.tx, driver.CMD_GET_DEV_STATE, response=False)
        deadline = time.monotonic() + timeout
        while self.sequence == previous and time.monotonic() < deadline:
            await asyncio.sleep(.02)
        if self.sequence == previous:
            raise StateUnavailable("No fresh valid A3 state")
        return self.latest

    async def rest_until_ready(self, settle, limit):
        deadline = time.monotonic() + limit
        clear_since = None
        while True:
            state = await self.sample()
            if state["flags"] == 0:
                if clear_since is None:
                    clear_since = time.monotonic()
                if time.monotonic() - clear_since >= settle:
                    self.fault = None
                    return
            else:
                clear_since = None
            if time.monotonic() >= deadline:
                raise StateUnavailable("Fault/readiness timeout; no printing")
            await asyncio.sleep(5)

    async def write_gatt_char(self, tx, packet, response=False):
        if self.fault:
            raise driver.FaultDetected(self.fault["state"])
        await self.client.write_gatt_char(tx, packet, response=response)
        if packet[2] != 0xA2:
            return
        self.rows += 1
        self.strip_rows += 1
        self.burn_dots += sum(b.bit_count() for b in packet[6:-2])
        if self.rows % 100 == 0:
            self.log("progress", rows_sent=self.rows, strip=self.strip,
                     strip_rows_sent=self.strip_rows, burn_dots=self.burn_dots)
            # No wait for reply: cadence retains only the configured row delay.
            await self.client.write_gatt_char(tx, driver.CMD_GET_DEV_STATE, response=False)
        if self.rows == self.pause_at:
            self.log("pause_start", rows_sent=self.rows, seconds=self.pause_seconds)
            await asyncio.sleep(self.pause_seconds)
            state = await self.sample()
            self.log("pause_end", state=state, rows_sent=self.rows)
            if self.fault:
                raise driver.FaultDetected(state)


async def run(args, rows, settings, log):
    client = None
    summary = {"scenario": args.scenario, "settings": settings,
               "outcome": "not_started", "rows_sent": 0, "strips_completed": 0}
    monitor = None
    try:
        client, tx = await driver.connect(SimpleNamespace(address=args.address, timeout=12))
        if client is None or tx is None:
            raise StateUnavailable("Printer connection unavailable")
        pause_at = len(rows[0]) + len(rows[1]) // 2 if args.scenario == "single-pause" else None
        monitor = Monitor(client, tx, log, pause_at, settings["pause_seconds"])
        await monitor.subscribe()
        log("rest_start", settle_seconds=args.settle, timeout_seconds=args.ready_timeout)
        await monitor.rest_until_ready(args.settle, args.ready_timeout)
        log("ready", state=monitor.latest)
        for idx, raster in enumerate(rows, 1):
            monitor.strip, monitor.strip_rows = idx, 0
            log("strip_start", strip=idx, rows=len(raster))
            await driver.stream_job(monitor, tx, raster, settings["energy"],
                                    settings["delay"], chunk=0, label=f"[{idx}] ")
            await driver.finish_job(monitor, tx, feed_rows=80)
            state = await monitor.sample()
            if monitor.fault:
                raise driver.FaultDetected(state)
            if state["flags"] != 0:
                raise StateUnavailable("Nonzero flags after strip")
            summary["strips_completed"] = idx
            log("strip_complete", strip=idx, state=state, rows_sent=monitor.rows)
            # No deliberate pause between jobs. Header/feed/status overhead remains.
        await asyncio.sleep(3)
        state = await monitor.sample()
        if monitor.fault:
            raise driver.FaultDetected(state)
        if state["flags"] != 0:
            raise StateUnavailable("Nonzero final flags")
        summary["outcome"] = "completed_no_fault"
    except driver.FaultDetected:
        summary["outcome"] = "fault_0x04"
    except Exception as exc:
        summary["outcome"] = "inconclusive"
        summary["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        if monitor:
            summary.update(rows_sent=monitor.rows, first_fault=monitor.fault,
                           last_state=monitor.latest, burn_dots_sent=monitor.burn_dots)
        if client and client.is_connected:
            await client.disconnect()
        log("result", **summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", choices=SCENARIOS)
    parser.add_argument("images", nargs=2, type=Path)
    parser.add_argument("--address")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--settle", type=float, default=60)
    parser.add_argument("--ready-timeout", type=float, default=1200)
    args = parser.parse_args()
    if args.settle < 0 or args.ready_timeout < args.settle:
        parser.error("Invalid readiness timing")
    rows = []
    inputs = []
    for path in args.images:
        with Image.open(path) as img:
            if img.width != 384 or img.mode != "1":
                parser.error("Use the same pre-rendered 384 px monochrome strips")
            raster = driver.rows_from_image(img)
        rows.append(raster)
        inputs.append({"file": path.name, "rows": len(raster),
                       "raster_sha256": hashlib.sha256(b"".join(raster)).hexdigest(),
                       "black_dots": sum(b.bit_count() for row in raster for b in row)})
    settings = dict(SCENARIOS[args.scenario], inputs=inputs, settle_seconds=args.settle,
                    telemetry_every_rows=100, inter_strip_deliberate_pause=0,
                    note="Rows sent are not a measurement of physical printed rows")
    print(json.dumps(settings, indent=2), flush=True)
    if not args.execute:
        print("DRY RUN: no Bluetooth access or printing. Add --execute to print.")
        return
    if not args.address:
        parser.error("--address is required for hardware tests")
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    out = Path("runs") / f"{stamp}-{args.scenario}"
    out.mkdir(parents=True)
    (out / "settings.json").write_text(json.dumps(settings, indent=2))
    started = time.monotonic()
    with (out / "events.jsonl").open("w") as fh:
        def log(event, **fields):
            entry = dict(event=event, elapsed=round(time.monotonic()-started, 3),
                         at=datetime.datetime.now().isoformat(timespec="milliseconds"), **fields)
            line = json.dumps(entry)
            fh.write(line + "\n"); fh.flush()
            if event != "notification" or (fields.get("state") or {}).get("flags"):
                print(line, flush=True)
        summary = asyncio.run(run(args, rows, settings, log))
    (out / "result.json").write_text(json.dumps(summary, indent=2))
    print(f"Artifacts: {out.resolve()}", flush=True)
    raise SystemExit(0 if summary["outcome"] == "completed_no_fault" else 3)


if __name__ == "__main__":
    main()
