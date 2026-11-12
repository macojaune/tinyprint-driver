"""Harness checks only. These tests do not reproduce the hardware fault."""
import unittest

import tinyprint_cli as driver
from experiment import Monitor


class FakeClient:
    def __init__(self):
        self.writes = []

    async def write_gatt_char(self, tx, packet, response=False):
        self.writes.append(packet)


class ExperimentTest(unittest.IsolatedAsyncioTestCase):
    async def test_one_pause_and_nonblocking_telemetry_keep_raster_intact(self):
        client, events = FakeClient(), []
        monitor = Monitor(client, None, lambda event, **kw: events.append(event),
                          pause_at=3, pause_seconds=0)

        async def sample():
            return {"flags": 0}

        monitor.sample = sample
        rows = [bytes([i % 256]) * 48 for i in range(201)]
        for row in rows:
            await monitor.write_gatt_char(None, driver.make_packet(0xA2, row))
        self.assertEqual([p[6:-2] for p in client.writes if p[2] == 0xA2], rows)
        self.assertEqual(sum(p[2] == 0xA3 for p in client.writes), 2)
        self.assertEqual(events.count("pause_start"), 1)
        self.assertEqual(monitor.rows, 201)

    async def test_fault_blocks_next_write(self):
        client = FakeClient()
        monitor = Monitor(client, None, lambda *a, **kw: None)
        monitor.notify(None, driver.make_packet(0xA3, bytes([4, 13, 41])))
        with self.assertRaises(driver.FaultDetected):
            await monitor.write_gatt_char(None, driver.make_packet(0xA2, bytes(48)))
        self.assertEqual(client.writes, [])

    async def test_bad_crc_cannot_mark_printer_ready(self):
        monitor = Monitor(FakeClient(), None, lambda *a, **kw: None)
        packet = bytearray(driver.make_packet(0xA3, bytes([0, 13, 41])))
        packet[-2] ^= 1
        monitor.notify(None, packet)
        self.assertIsNone(monitor.latest)


if __name__ == "__main__":
    unittest.main()
