"""Tiny Print packet codec and observed command constants. No BLE or image dependency.

Reference: https://github.com/bitbank2/Thermal_Printer/wiki/Cat-Rabbit-printer-info
Status flag names follow that family's documentation; byte2/byte3 remain unknown.
"""
WIDTH = 384
HEADER, FOOTER = b"\x51\x78", b"\xff"

def crc8(data: bytes) -> int:
    """CRC-8, polynomial 0x07, initial value 0, no reflection or final XOR."""
    crc = 0
    for value in data:
        crc ^= value
        for _ in range(8):
            crc = ((crc << 1) ^ 0x07) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc


def make_packet(cmd: int, payload: bytes = b"") -> bytes:
    n = len(payload)
    return HEADER + bytes([cmd, 0x00, n & 0xFF, (n >> 8) & 0xFF]) + payload + bytes([crc8(payload), 0xFF])

CMD_GET_DEV_STATE = bytes.fromhex("5178A30001000000FF")
CMD_GET_DEV_INFO = bytes.fromhex("5178A80001000000FF")
CMD_SET_QUALITY = bytes.fromhex("5178A4000100329EFF")
CMD_APPLY_ENERGY = bytes.fromhex("5178BE0001000107FF")
CMD_LATTICE_START = bytes.fromhex("5178A6000B00AA551738445F5F5F44382CA1FF")
CMD_LATTICE_END = bytes.fromhex("5178A6000B00AA5517000000000000001711FF")
CMD_FEED = bytes.fromhex("5178A10002006000F5FF")
CMD_SET_SPEED = make_packet(0xBD, b"\x01")


def parse_state(data: bytes):
    """Decode an A3 notification: 51 78 a3 01 03 00 <flags> <temp> <0x29> <crc> ff"""
    if len(data) < 8 or data[2] != 0xA3:
        return None
    payload = data[6:-2]
    if len(payload) < 3:
        return None
    flags, temp = payload[0], payload[1]
    return {
        "flags": flags,
        "temp": temp,
        "overheat": bool(flags & 0x04),
        "paper": bool(flags & 0x02),
        "raw": payload.hex(" "),
    }

