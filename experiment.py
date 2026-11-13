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


from transport import PrinterSession as Monitor, StateUnavailable


async def run(args, rows, settings, log):
    client = None
    summary = {"scenario": args.scenario, "settings": settings,
               "outcome": "not_started", "rows_sent": 0, "strips_completed": 0,
               "physical_paper_review": "pending; BLE writes do not prove paper motion"}
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
        # The printer can still be consuming queued raster after the last write.
        log("tail_observation_start", seconds=60)
        for _ in range(60):
            await asyncio.sleep(1)
            state = await monitor.sample()
            if monitor.fault:
                raise driver.FaultDetected(state)
            if state["flags"] != 0:
                raise StateUnavailable("Nonzero final flags")
        summary["outcome"] = "completed_no_fault"
    except driver.FaultDetected as exc:
        summary["outcome"] = "fault_0x04" if exc.state["flags"] & 4 else "other_state_error"
    except asyncio.CancelledError:
        summary["outcome"] = "cancelled"
    except Exception as exc:
        summary["outcome"] = "inconclusive"
        summary["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        if monitor:
            summary.update(rows_sent=monitor.rows, first_fault=monitor.fault,
                           last_state=monitor.latest, burn_dots_sent=monitor.burn_dots,
                           flow_wait_seconds=monitor.flow_wait_seconds,
                           flow_stop_requests=monitor.flow_stop_requests)
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
                    respect_ae_flow_control=True, final_observation_seconds=60,
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
