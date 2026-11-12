"""Short paper-motion check; dry-run unless --execute. No photos required."""
import argparse
import asyncio
import json
from types import SimpleNamespace

import tinyprint_cli as driver
from experiment import Monitor


def make_rows():
    rows = []
    for y in range(160):
        row = bytearray(48)
        # Five short horizontal ticks and a narrow alternating central bar.
        for x in range(384):
            if ((y % 40 == 0 or y == 159) and x < 80) or (176 <= x < 208 and (y // 8) % 2 == 0):
                row[x // 8] |= 1 << (x % 8)
        rows.append(bytes(row))
    return rows


async def check(address):
    client, tx = await driver.connect(SimpleNamespace(address=address, timeout=12))
    if client is None or tx is None:
        if client:
            await client.disconnect()
        return 3

    def log(event, **fields):
        if event != "notification" or (fields.get("state") or {}).get("flags"):
            print(json.dumps(dict(event=event, **fields)), flush=True)

    monitor = Monitor(client, tx, log)
    try:
        await monitor.subscribe()
        print("Waiting for 60 seconds of clear status before paper check", flush=True)
        await monitor.rest_until_ready(settle=60, limit=1200)
        print("FEED ONLY: 80 motor steps requested", flush=True)
        await monitor.write_gatt_char(tx, driver.make_packet(0xA1, bytes([80, 0])))
        await asyncio.sleep(3)
        state = await monitor.sample()
        if state["flags"] != 0:
            print("Paper check stopped on status", state, flush=True)
            return 3
        print("MIRE: 160 rows, ticks every 40 rows; energy 14500; 28 ms row delay", flush=True)
        await driver.stream_job(monitor, tx, make_rows(), 14500, .028, chunk=0)
        await driver.finish_job(monitor, tx, feed_rows=80)
        await asyncio.sleep(3)
        state = await monitor.sample()
        print("FINAL STATUS:", state, flush=True)
        print("Physical paper motion and tick spacing need human confirmation", flush=True)
        return 0 if state["flags"] == 0 and not monitor.fault else 3
    finally:
        await client.disconnect()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--address")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        print("DRY RUN: 80 feed steps, 160 sparse raster rows, 80 feed steps. No Bluetooth.")
        return
    if not args.address:
        parser.error("--address required")
    raise SystemExit(asyncio.run(check(args.address)))


if __name__ == "__main__":
    main()
