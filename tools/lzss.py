# -*- coding: utf-8 -*-
r"""다크 세이비어 LZSS (PROGRAM.004 해제기 0x2A6D1C, 래퍼 0x2A3758) — 2026-10-03 역어셈블로 확정
  블록 = [u16 압축 바이트 수][압축 데이터]. 창 4 KB, 시작 위치 0xFEE, 창 초기값 0, 플래그 바이트 LSB 우선(1 = 리터럴),
  참조 2 B: 위치 = b0 | (b1 & 0xF0) << 4, 길이 = (b1 & 0x0F) + 3   (오쿠무라 LZSS)
"""
import struct


def decompress_block(d, p):
    n = struct.unpack_from('>H', d, p)[0]
    return decompress(d[p + 2:p + 2 + n]), p + 2 + n


def decompress(src):
    win = bytearray(0x1000); r = 0xFEE; out = bytearray(); i = 0; flags = 0
    while i < len(src):
        flags >>= 1
        if not flags & 0x100:
            flags = src[i] | 0xFF00; i += 1
            if i >= len(src): break
        if flags & 1:
            c = src[i]; i += 1
            out.append(c); win[r] = c; r = (r + 1) & 0xFFF
        else:
            if i + 1 >= len(src): break
            b0, b1 = src[i], src[i + 1]; i += 2
            pos = b0 | (b1 & 0xF0) << 4; ln = (b1 & 0x0F) + 3
            for k in range(ln):
                c = win[(pos + k) & 0xFFF]
                out.append(c); win[r] = c; r = (r + 1) & 0xFFF
    return bytes(out)


def compress(data):
    """탐욕 + 1단 지연 매칭 LZSS (해제기와 같은 규약: 창 0 초기화·시작 0xFEE·길이 3‥18)"""
    N, F, TH = 0x1000, 18, 3
    win = bytearray(N); r = 0xFEE
    # 창 내용을 «원본 + 앞쪽 0 창»으로 보고 후보 위치 색인
    buf = bytes(N) + data                      # buf[i] ↔ 창 위치 (0xFEE - N + i) — 앞 N 바이트 = 초기 창(0)
    base = N
    from collections import defaultdict
    idx = defaultdict(list)
    def add(i):
        if i + 2 < len(buf): idx[buf[i:i + 3]].append(i)
    for i in range(N - 0x12, N): add(i)        # 초기 창의 0 들(시작 위치 앞 18바이트만 의미 있음)
    out = bytearray(); flags_pos = None; bit = 8; i = base
    def best(i):
        bl, bp = 0, 0
        if i + TH > len(buf): return 0, 0
        for j in reversed(idx.get(buf[i:i + 3], [])[-256:]):
            if i - j > N - 1 or i - j <= 0: continue
            l = 0
            while l < F and i + l < len(buf) and buf[j + l] == buf[i + l]: l += 1
            if l > bl: bl, bp = l, j
            if l == F: break
        return bl, bp
    while i < len(buf):
        if bit == 8:
            flags_pos = len(out); out.append(0); bit = 0
        l, j = best(i)
        if l >= TH:
            l2, _ = best(i + 1)
            if l2 > l + 1: l = 0
        if l >= TH:
            pos = (0xFEE + (j - base)) & 0xFFF
            out += bytes([pos & 0xFF, (pos >> 4 & 0xF0) | (l - 3)])
            for k in range(l): add(i + k)
            i += l
        else:
            out[flags_pos] |= 1 << bit; out.append(buf[i]); add(i); i += 1
        bit += 1
    return bytes(out)
