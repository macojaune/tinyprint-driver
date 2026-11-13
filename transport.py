"""BLE session with validated notifications, device flow control and status probes.

No image handling. The session wraps an already-connected Bleak-compatible client.
"""
import asyncio
import time
import protocol


class FaultDetected(Exception):
    def __init__(self, state):
        super().__init__(f"Printer flags: 0x{state['flags']:02x}")
        self.state = state


class StateUnavailable(RuntimeError):
    pass


class PrinterSession:
    """Wrap raster writes; request telemetry without waiting between rows."""
    def __init__(self, client, tx, log, pause_at=None, pause_seconds=0):
        self.client, self.tx, self.log = client, tx, log
        self.pause_at, self.pause_seconds = pause_at, pause_seconds
        self.rows = self.strip = self.strip_rows = self.burn_dots = 0
        self.latest = None
        self.sequence = 0
        self.fault = None
        self.subscription = None
        self.flow_allowed = asyncio.Event()
        self.flow_allowed.set()
        self.flow_wait_seconds = 0.0
        self.flow_stop_requests = 0

    def __getattr__(self, name):
        return getattr(self.client, name)

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
        state = protocol.parse_state(data)
        valid = (len(data) >= 8 and data[:2] == protocol.HEADER
                 and len(data) == int.from_bytes(data[4:6], "little") + 8
                 and data[-1] == 255 and protocol.crc8(data[6:-2]) == data[-2])
        self.log("notification", frame=data.hex(" "), valid=valid,
                 state=state, rows_sent=self.rows, strip=self.strip,
                 strip_rows_sent=self.strip_rows)
        if valid and data[2] == 0xAE and len(data[6:-2]) == 1:
            value = data[6]
            if value == 0x10:
                self.flow_stop_requests += 1
                self.flow_allowed.clear()
                self.log("flow_stop", rows_sent=self.rows)
            elif value == 0:
                self.flow_allowed.set()
                self.log("flow_resume", rows_sent=self.rows)
        if state and valid:
            self.latest = state
            self.sequence += 1
            if state["flags"] & 0x0F and self.fault is None:
                self.fault = {"rows_sent": self.rows, "strip": self.strip,
                              "strip_rows_sent": self.strip_rows, "state": state}
                self.flow_allowed.set()  # Wake a blocked sender so it can abort.

    async def sample(self, timeout=4):
        previous = self.sequence
        await self.client.write_gatt_char(self.tx, protocol.CMD_GET_DEV_STATE, response=False)
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
        if not self.flow_allowed.is_set():
            started = time.monotonic()
            self.log("flow_wait_start", rows_sent=self.rows)
            try:
                await asyncio.wait_for(self.flow_allowed.wait(), timeout=60)
            except asyncio.TimeoutError:
                raise StateUnavailable("No AE 00 resume within 60 seconds")
            finally:
                elapsed = time.monotonic() - started
                self.flow_wait_seconds += elapsed
                self.log("flow_wait_end", rows_sent=self.rows, seconds=elapsed)
        if self.fault:
            raise FaultDetected(self.fault["state"])
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
            await self.client.write_gatt_char(tx, protocol.CMD_GET_DEV_STATE, response=False)
        if self.rows == self.pause_at:
            self.log("pause_start", rows_sent=self.rows, seconds=self.pause_seconds)
            await asyncio.sleep(self.pause_seconds)
            state = await self.sample()
            self.log("pause_end", state=state, rows_sent=self.rows)
            if self.fault:
                raise FaultDetected(state)

