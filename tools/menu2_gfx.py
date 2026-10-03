# -*- coding: utf-8 -*-
r"""팔콤 클래식 2편 메인 메뉴 그림 글자 (2026-10-03)
  SUN/0FC2L.BIN(저 워크램 0x00200000 적재) 안 그림 표 0x704BC: 8 B 항목 [RAM 주소 u32][폭 u16][높이 u16].
  그림 = [풀린 크기 u32 BE][오쿠무라 LZSS(다크 세이비어 lzss.py 와 같은 규약: 창 4 KB·시작 0xFEE·플래그 LSB·1=리터럴)].
  블록이 빈틈없이 이어져 있다 → 다시 압축한 길이가 원래 칸(다음 블록까지) 안이어야 한다.
  일본어 4장만: 「ゲームを選択して下さい。」 · 「で選択、 、 、 で決定。」(빈칸에 START·A·C 버튼 그림이 얹힘 → 칸 위치 유지)
  · 「イースII」 · 「太陽の神殿ASTEKA II」. SELECT GAME·PRESS START BUTTON·저작권은 영어라 둠.
  원본 = 회색 15단 부드러운 글씨 → 한글은 흰색(15) 한 색(기본 규칙).
"""
import os, struct, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import lzss
from drs_gfx import line_mask, to4, from4

TABLE = 0x704BC
BLOCKS = sorted([0x46944, 0x46CA8, 0x46F10, 0x46FB8, 0x472B8, 0x4738C, 0x47414, 0x4748C, 0x475D8, 0x47990])
F = 'Galmuri14'


def unpack(d, o, w, h):
    n = struct.unpack('>I', d[o:o + 4])[0]
    raw = lzss.decompress(d[o + 4:o + 4 + n * 2])[:n]
    assert len(raw) == n == w * h // 2, ('크기 다름', hex(o))
    return from4(raw, w, h)


def put(img, m, x0, y0, c=15):
    reg = img[y0:y0 + m.shape[0], x0:x0 + m.shape[1]]; reg[m[:reg.shape[0], :reg.shape[1]] == 1] = c


def ybase(m, h):
    return max(0, (h - m.shape[0] + 1) // 2)


def draw_select(w=200, h=16):
    img = np.zeros((h, w), np.uint8); m = line_mask(F, '게임을 선택해 주세요.', space=6, gap=1)
    assert m.shape[1] <= w, m.shape; put(img, m, 0, ybase(m, h)); return img


def draw_guide(w=208, h=16):
    """원본 칸: 「で選択、」 0‥51 | START 버튼 52‥96 | 「、」 97‥100 | A 101‥122 | 「、」 123‥126 | C 127‥149 | 「で決定。」 150‥205"""
    img = np.zeros((h, w), np.uint8)
    for s, x0, x1 in (('로 선택,', 0, 51), (',', 97, 100), (',', 123, 126), ('로 결정.', 150, 207)):
        m = line_mask(F, s, space=5, gap=0)
        assert m.shape[1] <= x1 - x0 + 1, ('안내 칸 넘침', s, m.shape[1], x1 - x0 + 1)
        put(img, m, x0, ybase(m, h))
    return img


def draw_title(parts, w, h):
    """parts = [(글꼴, 문자열)] 를 밑줄(아래끝) 맞춰 이어 붙인다"""
    ms = [line_mask(f, s, space=5, gap=1) for f, s in parts]
    pads = [4 if s.endswith(' ') else 0 for f, s in parts]               # 끝 공백은 line_mask 가 잘라 내므로 따로
    H = max(m.shape[0] for m in ms); W = sum(m.shape[1] + 1 + p for m, p in zip(ms, pads))
    assert W <= w, ('제목 폭 넘침', W, w)
    img = np.zeros((h, w), np.uint8); x = 0; y0 = ybase(np.zeros((H, 1)), h)
    for m, p in zip(ms, pads):
        put(img, m, x, y0 + H - m.shape[0]); x += m.shape[1] + 1 + p
    return img


ITEMS = [(0x46944, 200, 16, draw_select), (0x46FB8, 208, 16, draw_guide),
         (0x4748C, 88, 17, lambda: draw_title([(F, '「이스Ⅱ」')], 88, 17)),
         (0x475D8, 168, 17, lambda: draw_title([(F, '「태양의 신전 '), ('Galmuri9', 'ASTEKA Ⅱ'), (F, '」')], 168, 17))]


def patch_l(d):
    out = bytearray(d); regions = []; pairs = []
    for o, w, h, fn in ITEMS:
        old = unpack(d, o, w, h); new = fn()
        comp = lzss.compress(to4(new))
        assert lzss.decompress(comp)[:w * h // 2] == to4(new)
        room = BLOCKS[BLOCKS.index(o) + 1] - o
        assert 4 + len(comp) <= room, ('압축 칸 넘침', hex(o), 4 + len(comp), room)
        blk = struct.pack('>I', w * h // 2) + comp
        out[o:o + room] = blk + bytes(room - len(blk)); regions.append((o, o + room))
        pairs.append((old, new, hex(o)))
    for i in range(len(d)):
        if d[i] != out[i] and not any(a <= i < b for a, b in regions):
            raise SystemExit('⛔허용 범위 밖 변경 0FC2L 0x%X' % i)
    return bytes(out), regions, pairs
