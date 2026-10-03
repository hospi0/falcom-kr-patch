"""이스 I·이스 II·아스테카 글꼴 아틀라스 읽기 / 대사 렌더링 검사.

아틀라스 = 폭 16글자 한 장, 2bpp(값 1 글자·3 그림자). 주소는 L 이미지 파일 오프셋.
코드: 0x00‥2F → 표0, 0x30‥DF → 표1(가나), 0xE0‥ → 표2(한자, 이스 I 524 · 이스 II 634 · 아스테카 419).
사용: python tools/ysfont.py  → work/font_<게임>_*.png
"""
import numpy as np
from PIL import Image

ROOT = 'work/disc/'
GAMES = {
    # 이름: (파일, 글자 크기, [(코드 시작, 코드 끝, 아틀라스 파일 오프셋)], 글꼴 표 위치)
    'ys1': ('fc1/YS1_0YS1L.BIN', 16, [(0x00, 0x30, 0x8E9D4), (0x30, 0xE0, 0x8F5D4), (0xE0, 0xE0 + 524, 0x921D4)], 0xA0E14),
    'ys2': ('fc2/YS2_0YS2L.BIN', 16, [(0x00, 0x30, 0x2D608), (0x30, 0xE0, 0x2E208), (0xE0, 0xE0 + 634, 0x30E08)], 0x45A88),
    'ys2b': ('fc2/YS2_0YS2L.BIN', 16, [(0x00, 0x10, 0x3AE08), (0x30, 0xE0, 0x3B208), (0xE0, 0xE0 + 384, 0x3DE08)], 0x45A88),   # 이스 II 굵은 둘째 벌(마물 모습일 때 대사)
    'sun': ('fc2/SUN_0SUNL.BIN', 12, [(0x00, 0x30, 0x2B390), (0x30, 0xE0, 0x2BA50), (0xE0, 0xE0 + 419, 0x2D310)], 0x30FD0),
}
# 이스 II 굵은 글씨 둘째 벌(표 3‥5): 숫자 16칸 0x3AE08 · 가나 0x3B208 · 한자 384자 0x3DE08 — 쓰는 화면 미확인.
PAL = np.array([[0, 0, 96], [255, 255, 255], [255, 0, 0], [90, 90, 90]], np.uint8)


def load(game):
    f, gs, tab, _ = GAMES[game]
    return open(ROOT + f, 'rb').read(), gs, tab


def glyph(d, off, gs, idx):
    bpr = gs * 16 // 4
    r, c = divmod(idx, 16)
    g = np.zeros((gs, gs), np.uint8)
    for y in range(gs):
        row = d[off + (r * gs + y) * bpr: off + (r * gs + y + 1) * bpr]
        for x in range(gs):
            X = c * gs + x
            g[y, x] = (row[X // 4] >> (6 - 2 * (X % 4))) & 3
    return g


def code_glyph(d, gs, tab, v):
    for lo, hi, off in tab:
        if lo <= v < hi:
            return glyph(d, off, gs, v - lo)
    return None


def sheet(game):
    d, gs, tab = load(game)
    for i, (lo, hi, off) in enumerate(tab):
        n = hi - lo
        rows = (n + 15) // 16
        img = np.zeros((rows * gs, 16 * gs), np.uint8)
        for k in range(n):
            r, c = divmod(k, 16)
            img[r * gs:(r + 1) * gs, c * gs:(c + 1) * gs] = glyph(d, off, gs, k)
        Image.fromarray(PAL[img]).resize((img.shape[1] * 2, img.shape[0] * 2), Image.NEAREST) \
            .save(f'work/font_{game}_{i}.png')


if __name__ == '__main__':
    for g in GAMES:
        sheet(g)
