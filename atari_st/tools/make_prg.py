#!/usr/bin/env python3
from __future__ import annotations

import argparse
import struct
import subprocess
from pathlib import Path

HEADER_MAGIC = 0x601A
HEADER_SIZE = 0x1C


def build_prg(payload: bytes, bss: int = 0) -> bytes:
    """The PRG of a flat image. The last `bss` bytes of the image are not stored: TOS makes room for them behind the program (the header's bss length)."""
    if bss:
        if bss % 2 or bss > len(payload) or any(payload[len(payload) - bss:]):
            raise SystemExit(f"the last {bss} bytes of the image must be an even number of zeros to be left out of the file")
        payload = payload[:len(payload) - bss]
    header = struct.pack(
        ">HLLLLLLH",
        HEADER_MAGIC,
        len(payload),
        0,
        bss,
        0,
        0,
        0,
        1,
    )
    return header + payload


def check_prg(path: Path) -> None:
    data = path.read_bytes()
    if len(data) < HEADER_SIZE:
        raise SystemExit(f"{path} is too small to be a TOS executable")

    magic, text_len, data_len, bss_len, sym_len, reserved, prg_flags, abs_flag = struct.unpack(
        ">HLLLLLLH", data[:HEADER_SIZE]
    )

    if magic != HEADER_MAGIC:
        raise SystemExit(f"{path} has wrong magic: 0x{magic:04x}")
    if abs_flag != 1:
        raise SystemExit(
            f"{path} has absflag={abs_flag}; this checker only validates the absolute, relocation-free PRGs emitted by this build"
        )

    # This build emits absolute PRGs without a relocation table, so header + text + data + symbols is the full file.
    expected_size = HEADER_SIZE + text_len + data_len + sym_len
    if expected_size != len(data):
        raise SystemExit(
            f"{path} header size mismatch: header expects {expected_size} bytes, found {len(data)}"
        )

    print(
        f"Validated {path}: text={text_len} data={data_len} bss={bss_len} symbols={sym_len} flags={prg_flags}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Wrap a flat 68000 binary in a minimal Atari TOS PRG header")
    parser.add_argument("input", nargs="?")
    parser.add_argument("output", nargs="?")
    parser.add_argument("--check", dest="check", type=Path)
    parser.add_argument("--elf", type=Path, help="the linked ELF, for --bss-from")
    parser.add_argument("--bss-from", help="a symbol of --elf: the image from there on is zeros (a buffer) and is not stored in the file")
    parser.add_argument("--nm", default="m68k-linux-gnu-nm")
    args = parser.parse_args()

    if args.check is not None:
        check_prg(args.check)
        return

    if not args.input or not args.output:
        parser.error("input and output are required unless --check is used")

    payload = Path(args.input).read_bytes()
    bss = 0
    if args.bss_from:
        if not args.elf:
            parser.error("--bss-from needs --elf")
        out = subprocess.run([args.nm, str(args.elf)], check=True, capture_output=True, text=True).stdout
        found = [int(line.split()[0], 16) for line in out.splitlines() if line.split()[-1:] == [args.bss_from]]
        if not found:
            parser.error(f"{args.bss_from} is not a symbol of {args.elf}")
        bss = len(payload) - found[0]
    Path(args.output).write_bytes(build_prg(payload, bss))
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
