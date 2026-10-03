# -*- coding: utf-8 -*-
r"""2편 메뉴 로고 「ファルコムクラシックスⅡ」 → 「팔콤 / 클래식스Ⅱ」 시험작 (2026-10-03)
  SUN/0FC2L.BIN 그림 표 0x70594 → 0x435C8 (312×120 8bpp, u32+LZSS), 색 = 2편 메뉴 CRAM 512번대(work/mem/m2).
  가타카나 덩어리만 지우고(연결 성분 + 붉은/흰 색) 장식 덩굴·영문·Ⅱ 는 둔다.
  새 글자 = 원본 줄별 대표색 그라데이션 + 짙은 테두리 + 왼쪽 하이라이트, 원본처럼 오른쪽으로 기울이고 글자 사이를 띄움.
  python tools/logo_fc2.py [글꼴키]   → work/logo_fc2_<글꼴키>.png (위 원본 / 아래 시험작)
"""
import os, struct, sys
from collections import deque
import numpy as np
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import lzss

TABLE_ENTRY = 0x70594; W, H = 312, 120
FD = r'C:/claude/utils/font/'
FONTS = {'bhs': FD + 'logo/BlackHanSans.ttf', 'gasoek': FD + 'logo/GasoekOne-Regular.ttf', 'gugi': FD + 'logo/Gugi.ttf',
         'nanumeb': FD + 'nanum-gothic/NanumGothicExtraBold.ttf', 'myeongjo': FD + 'nanum-myeongjo/NanumMyeongjoExtraBold.ttf',
         'yeonsung': FD + 'yeonsung/YeonSung-Regular.ttf'}
# (글자, 원본 줄 띠 y0‥y1, x 시작‥끝, 글자 높이)
LINES = [('팔콤', 18, 59, 18, 190, 38), ('클래식스', 64, 104, 60, 256, 34)]
SHEAR = 0.22


def load():
    d = open(os.path.join(ROOT, 'work', 'disc', 'fc2', 'SUN_0FC2L.BIN'), 'rb').read()
    o = struct.unpack_from('>I', d, TABLE_ENTRY)[0] - 0x200000
    n = struct.unpack_from('>I', d, o)[0]
    a = np.frombuffer(lzss.decompress(d[o + 4:o + 4 + n * 2])[:n], np.uint8).reshape(H, W).copy()
    c = open(os.path.join(ROOT, 'work', 'mem', 'm2', 'CRAM.bin'), 'rb').read()
    c = bytes(b for i in range(0, len(c), 2) for b in (c[i + 1], c[i]))
    e = np.frombuffer(c, '>u2').astype(int)[512:768]
    pal = np.stack([(e & 31) << 3, ((e >> 5) & 31) << 3, ((e >> 10) & 31) << 3], 1).astype(np.uint8)
    return d, o, a, pal


def components(m):
    lab = np.zeros(m.shape, int); n = 0
    for y in range(m.shape[0]):
        for x in range(m.shape[1]):
            if m[y, x] and not lab[y, x]:
                n += 1; q = deque([(y, x)]); lab[y, x] = n
                while q:
                    cy, cx = q.popleft()
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            yy, xx = cy + dy, cx + dx
                            if 0 <= yy < m.shape[0] and 0 <= xx < m.shape[1] and m[yy, xx] and not lab[yy, xx]:
                                lab[yy, xx] = n; q.append((yy, xx))
    return lab


def erode(m):
    r = m.copy()
    for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        r &= np.roll(np.roll(m, dy, 0), dx, 1)
    return r


def dilate(m):
    r = m.copy()
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            r |= np.roll(np.roll(m, dy, 0), dx, 1)
    return r


def glyph_mask(ch, font, height):
    f = ImageFont.truetype(font, size=int(height * 1.4))
    l, t, r, b = f.getbbox(ch)
    im = Image.new('L', (r - l + 40, b - t + 20), 0)
    ImageDraw.Draw(im).text((20 - l, 10 - t), ch, font=f, fill=255)
    m = np.array(im) > 110
    ys, xs = np.nonzero(m); m = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    s = height / m.shape[0]
    im = Image.fromarray((m * 255).astype(np.uint8)).resize((max(1, int(m.shape[1] * s)), height), Image.LANCZOS)
    m = np.array(im) > 127
    h, w = m.shape; out = np.zeros((h, w + int(h * SHEAR) + 1), bool)
    for y in range(h):
        sh = int((h - 1 - y) * SHEAR); out[y, sh:sh + w] = m[y]
    return out


def make(fontkey='bhs'):
    d, o, a, pal = load()
    p = pal.astype(int); lum = p.sum(1)
    letter_col = (p[:, 0] > p[:, 2] + 24) | (p.min(1) > 215)
    lab = components(a != 0)
    keep = set(np.unique(lab[:, 262:])) | set(np.unique(lab[103:, 90:210])); keep.discard(0)   # Ⅱ · 영문
    orn = lab[2, 30]                                                  # 위쪽 덩굴(첫 줄 글자와 붙어 있음)
    neutral = (np.abs(p[:, 0] - p[:, 2]) < 40)[a] & ~(p.min(1) > 215)[a]
    L = (a != 0) & ~np.isin(lab, list(keep))
    L &= ~((lab == orn) & ((np.arange(H)[:, None] < 19) | (neutral & (np.arange(W)[None, :] < 16) & (np.arange(H)[:, None] < 34))))   # 덩굴 = 위 19행 + 왼쪽 곡선
    letters_only = L & letter_col[a]                                   # 질감 통계는 글자색만
    core = erode(letters_only); edge = letters_only & ~core
    mode = lambda v: np.unique(v, return_counts=True)[0][np.argmax(np.unique(v, return_counts=True)[1])]
    ev = a[edge]; OUT = min([v for v in np.unique(ev) if (ev == v).sum() > 20], key=lambda v: lum[v])
    lv = a[letters_only]; HI = max([v for v in np.unique(lv) if (lv == v).sum() > 10], key=lambda v: lum[v])
    new = a.copy(); new[L] = 0
    for text, y0, y1, x0, x1, gh in LINES:
        rows = {y: mode(a[y][core[y]]) for y in range(y0, y1) if core[y].any()}
        ms = [glyph_mask(ch, FONTS[fontkey], gh) for ch in text]
        gap0 = 8; need = (x1 - x0) - gap0 * (len(ms) - 1); tot0 = sum(m.shape[1] for m in ms)
        k = min(1.5, max(1.0, need / tot0))                            # 줄 폭에 맞춰 가로로 늘임(최대 1.5배)
        if k > 1.01:
            ms = [np.array(Image.fromarray((m * 255).astype(np.uint8)).resize((int(m.shape[1] * k), m.shape[0]), Image.LANCZOS)) > 127 for m in ms]
        tot = sum(m.shape[1] for m in ms); gap = min(10, max(1, (x1 - x0 - tot) // max(1, len(ms) - 1)))
        span = tot + gap * (len(ms) - 1); x = x0
        assert x0 + span <= x1 + 2, ('로고 폭 넘침', text, span, x1 - x0)
        top = y0 + (y1 - y0 - gh) // 2
        M = np.zeros((H, W), bool)
        for m in ms:
            hm, wm = m.shape; wm = min(wm, W - x); M[top:top + hm, x:x + wm] |= m[:, :wm]; x += m.shape[1] + gap
        new[dilate(M) & ~M & (new == 0)] = OUT
        for y in range(top, top + gh):
            src = y0 + int((y - top) * (y1 - y0) / gh); src = min(rows, key=lambda r: abs(r - src))
            new[y][M[y]] = rows[src]
        new[M & ~np.roll(M, 1, 1)] = HI
    return a, new, pal


def main():
    key = sys.argv[1] if len(sys.argv) > 1 else 'bhs'
    a, new, pal = make(key)
    bg = np.array([90, 110, 140], np.uint8)
    show = lambda x: np.where((x == 0)[..., None], bg, pal[x])
    img = Image.fromarray(np.vstack([show(a), np.full((6, W, 3), 255, np.uint8), show(new)]))
    img.resize((W * 3, img.height * 3), 0).save(os.path.join(ROOT, 'work', 'logo_fc2_%s.png' % key))
    print('ok', key)


if __name__ == '__main__':
    main()
