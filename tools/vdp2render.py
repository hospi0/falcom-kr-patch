# -*- coding: utf-8 -*-
r"""새턴 VDP2 NBG0‥3 렌더(스테이트 덤프 work/mem/<이름>/ 사용, 2026-10-03)
  레지스터(VDP2_REGS u16 BE) 로 셀/비트맵·글자 크기·색 수·패턴 이름 형식·맵 주소를 읽어 평면 A 를 그린다.
  python tools/vdp2render.py <이름>   → work/v2_<이름>_nbgN.png  (+ 정보 출력)
  ⚠️스크롤·우선순위·투명 합성 안 함. 글자가 어느 면·어느 셀에 있는지 찾는 용도.
"""
import os, struct, sys
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)


def load(name):
    D = os.path.join(ROOT, 'work', 'mem', name)
    v = open(os.path.join(D, 'VDP2_VRAM.bin'), 'rb').read()
    r = open(os.path.join(D, 'VDP2_REGS.bin'), 'rb').read()
    c = open(os.path.join(D, 'CRAM.bin'), 'rb').read()
    c = bytes(b for i in range(0, len(c), 2) for b in (c[i + 1], c[i]))
    reg = lambda o: struct.unpack_from('>H', r, o)[0]
    cram = np.frombuffer(c, '>u2').astype(int)
    return v, reg, cram


def rgb(e):
    e = np.asarray(e)
    return np.stack([(e & 31) << 3, ((e >> 5) & 31) << 3, ((e >> 10) & 31) << 3], -1).astype(np.uint8)


def cell_pixels(v, addr, colors):
    if colors == 16:
        a = np.frombuffer(v[addr:addr + 32], np.uint8); return np.stack([a >> 4, a & 15], 1).ravel().reshape(8, 8).astype(int)
    a = np.frombuffer(v[addr:addr + 64], np.uint8); return a.reshape(8, 8).astype(int)


def info(reg, n):
    bgon = reg(0x20)
    if n < 2:
        ch = reg(0x28) >> (8 * n)
        chsz = ch & 1; bmen = (ch >> 1) & 1; bmsz = (ch >> 2) & 3; cc = (ch >> 4) & (7 if n == 0 else 3)
    else:
        ch = reg(0x2A) >> (4 * (n - 2))
        chsz = ch & 1; bmen = 0; bmsz = 0; cc = (ch >> 1) & 1
    colors = {0: 16, 1: 256, 2: 2048, 3: 32768, 4: 1 << 24}[cc]
    pncn = reg(0x30 + 2 * n)
    mpof = (reg(0x3C) >> (4 * n)) & 7
    plsz = (reg(0x3A) >> (2 * n)) & 3
    mpab = reg(0x40 + 4 * n)
    return dict(on=(bgon >> n) & 1, chsz=chsz, bmen=bmen, bmsz=bmsz, colors=colors, pncn=pncn, mpof=mpof, plsz=plsz,
                mpA=mpab & 0x3F, mpB=(mpab >> 8) & 0x3F, craof=(reg(0xE4) >> (4 * n)) & 7)


def render(name, n, crop=None):
    v, reg, cram = load(name); I = info(reg, n)
    if I['bmen']:
        W, H = [(512, 256), (512, 512), (1024, 256), (1024, 512)][I['bmsz']]
        base = I['mpof'] * 0x20000
        if I['colors'] == 16:
            a = np.frombuffer(v[base:base + W * H // 2], np.uint8); idx = np.stack([a >> 4, a & 15], 1).ravel().reshape(H, W)
        elif I['colors'] == 256:
            idx = np.frombuffer(v[base:base + W * H], np.uint8).reshape(H, W).astype(int)
        else:
            e = np.frombuffer(v[base:base + W * H * 2], '>u2').reshape(H, W); return Image.fromarray(rgb(e)), I
        img = rgb(cram[(I['craof'] << 8) + idx])
        return Image.fromarray(img), I
    one = (I['pncn'] >> 15) & 1
    cnsm = (I['pncn'] >> 14) & 1
    tiles = 2 if I['chsz'] else 1
    ncell = 64 if not I['chsz'] else 32
    pagebytes = ncell * ncell * (2 if one else 4)
    mp = (I['mpof'] << 6) | I['mpA']
    base = (mp * pagebytes) % len(v)
    pxs = ncell * tiles * 8
    out = np.zeros((pxs, pxs, 3), np.uint8)
    cells = np.zeros((ncell, ncell), int)
    for cy in range(ncell):
        for cx in range(ncell):
            o = (base + (cy * ncell + cx) * (2 if one else 4)) % len(v)
            if one:
                w = struct.unpack_from('>H', v, o)[0]
                if I['colors'] == 16:
                    pal = (w >> 12) & 0xF
                    if cnsm == 0:
                        chn = (w & 0x3FF) | ((I['pncn'] & 0x1F) >> 2 << 10) if I['chsz'] else (w & 0x3FF) | ((I['pncn'] & 0x1C) << 8)
                        hf, vf = (w >> 10) & 1, (w >> 11) & 1
                    else:
                        chn = (w & 0xFFF) | ((I['pncn'] & 0x1C) << 10); hf = vf = 0
                    pal |= ((I['pncn'] >> 5) & 7) << 4
                else:
                    pal = ((w >> 12) & 7) << 4
                    chn = (w & 0x3FF) | ((I['pncn'] & 0x1C) << 8); hf, vf = (w >> 10) & 1, (w >> 11) & 1
            else:
                w0, w1 = struct.unpack_from('>HH', v, o)
                chn = w1 & 0x7FFF; pal = w0 & 0x7F; hf, vf = (w0 >> 14) & 1, (w0 >> 15) & 1
            cells[cy, cx] = chn
            for ty in range(tiles):
                for tx in range(tiles):
                    k = ty * tiles + tx
                    if I['colors'] == 16:
                        addr = (chn + k) * 0x20
                    else:
                        addr = (chn + k * 2) * 0x20
                    if addr + 64 > len(v):
                        continue
                    px = cell_pixels(v, addr, I['colors'])
                    if hf: px = px[:, ::-1]
                    if vf: px = px[::-1]
                    if I['colors'] == 16:
                        e = cram[((I['craof'] << 8) + pal * 16 + px) & 0x7FF]
                    else:
                        e = cram[((I['craof'] << 8) + (pal >> 4 << 8) + px) & 0x7FF]
                    col = rgb(e); col[px == 0] = 0
                    yy = (cy * tiles + (vf and 1 - ty or ty)) * 8; xx = (cx * tiles + (hf and 1 - tx or tx)) * 8
                    out[yy:yy + 8, xx:xx + 8] = col
    return Image.fromarray(out), dict(I, base=hex(base), one=one, cells=cells)


if __name__ == '__main__':
    name = sys.argv[1]
    for n in range(4):
        im, I = render(name, n)
        print('NBG%d' % n, {k: (hex(v) if isinstance(v, int) and k in ('pncn',) else v) for k, v in I.items() if k != 'cells'})
        im.save(os.path.join(ROOT, 'work', 'v2_%s_nbg%d.png' % (name, n)))
