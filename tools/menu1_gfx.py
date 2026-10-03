# -*- coding: utf-8 -*-
r"""팔콤 클래식 1편 메인 메뉴 그림 글자 (2026-10-03)
  루트 파일 `0`(메뉴 프로그램, 고 워크램 0x06006000 적재) 안 그림 표 0x2C5C0: 8 B 항목 [RAM 주소 u32][바이트 수 u16][폭 u8][높이 u8].
  무압축 4bpp 그림 — 게임 이름 3개(112×16, 색 15 한 색) · 저장 안내 2개(240×64 / 240×32, 색2 글자 + 색1 그림자).
  NOW LOADING(영어)은 둠. 화면 아래 「で選択、STARTで決定。」 = VDP2 셀(③ patch_guide, LZSS 블록). 배경 「ファルコムクラシックス」 무늬는 로고라 둠.
"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from drs_gfx import line_mask, to4, from4

BASE = 0x06006000
NAMES = [(0x24E7E, '이스'), (0x2521E, '드래곤 슬레이어'), (0x255BE, '제나두')]
MSGS = [(0x25E3E, 240, 64, ['게임 종료 기록 「FALCOM_COM_」을', '저장할 수 없습니다.',
                             '기록을 저장하려면 빈 용량이 2', '필요합니다.']),
        (0x27C5E, 240, 32, ['게임 종료 기록 「FALCOM_COM_」을', '사용할 수 없습니다.'])]


def draw_name(s):
    w, h = 112, 16
    m = line_mask('Galmuri11', s, space=5, gap=1)
    assert m.shape[1] <= w - 2, ('이름 폭 넘침', s, m.shape)
    img = np.zeros((h, w), np.uint8)
    x0 = (w - m.shape[1]) // 2; y0 = max(0, min(5 + (11 - m.shape[0] + 1) // 2, h - m.shape[0]))
    reg = img[y0:y0 + m.shape[0], x0:x0 + m.shape[1]]; reg[m == 1] = 15
    return img


def draw_msg(w, h, lines):
    img = np.zeros((h, w), np.uint8)
    for k, s in enumerate(lines):
        m = line_mask('Galmuri11', s, space=5, gap=0)
        assert m.shape[1] + 1 <= w - 3, ('안내 폭 넘침', s, m.shape)
        y = 4 + k * 16 - (1 if m.shape[0] > 12 else 0)
        for dx, dy, c in ((4, 1, 1), (3, 0, 2)):                       # 원본: 2 글자 + 1 오른쪽 아래
            reg = img[y + dy:y + dy + m.shape[0], dx:dx + m.shape[1]]; reg[m[:reg.shape[0]] == 1] = c
    return img


def patch_0(d):
    out = bytearray(d); regions = []; pairs = []
    for o, s in NAMES:
        n = 112 * 16 // 2; new = draw_name(s)
        pairs.append((from4(d[o:o + n], 112, 16), new, s)); out[o:o + n] = to4(new); regions.append((o, o + n))
    for o, w, h, lines in MSGS:
        n = w * h // 2; new = draw_msg(w, h, lines)
        pairs.append((from4(d[o:o + n], w, h), new, lines[0])); out[o:o + n] = to4(new); regions.append((o, o + n))
    blk, (s0, e0), pr = patch_guide(d)
    out[s0:e0] = blk; regions.append((s0, e0)); pairs.append(pr)
    for i in range(len(d)):
        if d[i] != out[i] and not any(a <= i < b for a, b in regions):
            raise SystemExit('⛔허용 범위 밖 변경 0 0x%X' % i)
    return bytes(out), regions, pairs


# ③ 화면 아래 「で選択、STARTで決定。」 — VDP2 NBG2 셀. `0` 0x3BF90 LZSS 블록([풀린 크기 u32][오쿠무라 LZSS], 0x11C0 B 셀 묶음)
#    안의 셀 94‥141. 스테이트 맵(행 26‥28 × 열 12‥28, 136×24)으로 셀 번호를 확정했다(2026-10-03).
GUIDE_BLOCK = 0x3BF90
GUIDE_ROOM_END = 0x3C978          # 블록 끝 0x3C971 + 0 채움 7 B (다음 자료 0x3C978‥)
GUIDE_MAP = [[94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, None],
             [111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 127],
             [129, 130, None, 131, 132, 133, 134, 135, 136, 137, None, None, 138, 139, 140, 141, None]]
GUIDE_TEXT = [('로 선택,', 13, 54), ('로 결정.', 87, 127)]     # (글, x0, x1) — 원본 「で選択、」 14‥53 · 「で決定。」 88‥125


def patch_guide(d):
    import lzss, struct
    o = GUIDE_BLOCK; n = struct.unpack('>I', d[o:o + 4])[0]
    raw = bytearray(lzss.decompress(d[o + 4:GUIDE_ROOM_END])[:n])
    img = np.zeros((24, 136), np.uint8)
    for r, row in enumerate(GUIDE_MAP):
        for c, k in enumerate(row):
            if k is not None:
                img[r * 8:r * 8 + 8, c * 8:c * 8 + 8] = from4(bytes(raw[k * 32:k * 32 + 32]), 8, 8)
    old = img.copy()
    for s, x0, x1 in GUIDE_TEXT:
        sub = img[:, x0:x1 + 1]; sub[(sub == 15) | (sub == 1)] = 0
        m = line_mask('Galmuri11', s, space=4, gap=0)
        assert m.shape[1] + 1 <= x1 - x0 + 1 and m.shape[0] + 1 <= 13, ('안내 칸 넘침', s, m.shape)
        y0 = 15 - m.shape[0]                                          # 그림자까지 y≤15 (아래 셀 줄은 공유 빈 셀이 섞임)
        for dx, dy, c in ((1, 1, 1), (0, 0, 15)):
            reg = img[y0 + dy:y0 + dy + m.shape[0], x0 + dx:x0 + dx + m.shape[1]]; reg[m == 1] = c
    for r, row in enumerate(GUIDE_MAP):
        for c, k in enumerate(row):
            blk = img[r * 8:r * 8 + 8, c * 8:c * 8 + 8]
            if k is None:
                assert not blk.any(), ('공유 빈 셀에 그림이 걸침', r, c)
            else:
                raw[k * 32:k * 32 + 32] = to4(blk)
    comp = lzss.compress(bytes(raw)); assert lzss.decompress(comp)[:n] == bytes(raw)
    room = GUIDE_ROOM_END - o
    assert 4 + len(comp) <= room, ('안내 블록 압축 넘침', 4 + len(comp), room)
    new = struct.pack('>I', n) + comp
    return new + bytes(room - len(new)), (o, GUIDE_ROOM_END), (old, img, 'guide')
