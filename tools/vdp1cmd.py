# -*- coding: utf-8 -*-
r"""VDP1 명령표 덤프 (이 게임 스테이트는 VDP1 VRAM 도 swap16)  python tools/vdp1cmd.py <work/mem/이름> [최소폭]"""
import struct, sys


def load(d):
    v = open(d + '/VDP1_VRAM.bin', 'rb').read()
    b = bytearray(v); b[0::2], b[1::2] = v[1::2], v[0::2]
    return bytes(b)


def cmds(v):
    i = 0; seen = set(); out = []
    sx = lambda u: struct.unpack('>h', struct.pack('>H', u))[0]
    while i not in seen and len(out) < 2000:
        seen.add(i)
        c = struct.unpack_from('>16H', v, i * 32)
        if c[0] & 0x8000:
            break
        cmd = c[0] & 0xF; jp = (c[0] >> 12) & 7
        if cmd in (0, 1, 2):
            out.append((i, cmd, c[2], c[3], c[4] * 8, ((c[5] >> 8) & 0x3F) * 8, c[5] & 0xFF, sx(c[6]), sx(c[7])))
        i = c[1] // 4 if jp in (1, 2) else i + 1
    return out


if __name__ == '__main__':
    v = load(sys.argv[1]); mw = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    for i, cmd, pm, col, sa, w, h, x, y in cmds(v):
        if w >= mw:
            print('%3d cmd%d pmod %04x colr %04x srca %05x %3dx%-3d at (%d,%d)' % (i, cmd, pm, col, sa, w, h, x, y))
