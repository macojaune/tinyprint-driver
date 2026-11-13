"""Exercise the normal image command through a BLE-compatible fake transport."""
import asyncio
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from PIL import Image
import protocol
import tinyprint_cli as driver


class FakePrinter:
    def __init__(self, fault=False):
        self.is_connected = True
        self.services = [SimpleNamespace(characteristics=[SimpleNamespace(uuid="ae02", properties=["notify"])])]
        self.callback = None
        self.rows = 0
        self.blocked = False
        self.fault = fault
        self.energies = []

    async def start_notify(self, characteristic, callback):
        self.callback = callback

    def notify(self, command, payload):
        self.callback(None, protocol.make_packet(command, payload))

    def resume(self):
        self.blocked = False
        self.notify(0xAE, b"\0")

    async def write_gatt_char(self, tx, packet, response=False):
        if packet[2] == 0xAF:
            self.energies.append(int.from_bytes(packet[6:-2], "little"))
        if packet[2] == 0xA3:
            self.notify(0xA3, bytes([0, 13, 41]))
        if packet[2] == 0xA2:
            if self.blocked:
                raise AssertionError("Raster sent after XOFF before XON")
            self.rows += 1
            if self.rows == 1:
                self.blocked = True
                self.notify(0xAE, b"\x10")
                loop = asyncio.get_running_loop()
                if self.fault:
                    loop.call_later(.05, self.notify, 0xA3, bytes([4, 13, 41]))
                else:
                    loop.call_later(.05, self.resume)

    async def disconnect(self):
        self.is_connected = False


class DriverTest(unittest.IsolatedAsyncioTestCase):
    async def print_fake(self, fake, **overrides):
        args = SimpleNamespace(strength=3, feed_rows=0, feed_mm=10, force=False,
                               fault_wait=0, chunk_rows=0, chunk_pause=0,
                               smart_pause=True, smart_window=48)
        vars(args).update(overrides)
        with patch.object(driver, "connect", AsyncMock(return_value=(fake, "tx"))):
            return await driver.print_image(args, Image.new("1", (384, 4), 255))

    async def test_image_command_respects_device_flow_control(self):
        fake = FakePrinter()
        self.assertEqual(await self.print_fake(fake), 0)
        self.assertEqual(fake.rows, 4)
        self.assertFalse(fake.is_connected)

    async def test_image_command_aborts_on_fault_during_flow_wait(self):
        fake = FakePrinter(fault=True)
        self.assertEqual(await self.print_fake(fake), 3)
        self.assertEqual(fake.rows, 1)
        self.assertFalse(fake.is_connected)

    async def test_energy_can_be_overridden_without_changing_strength(self):
        fake = FakePrinter()
        self.assertEqual(await self.print_fake(fake, energy=8000, row_delay=0), 0)
        self.assertEqual(fake.energies, [8000])
