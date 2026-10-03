# -*- coding: utf-8 -*-
r"""이스 I · 이스 II · 아스테카 그림 글자 한글화 (2026-10-03) — 위치는 docs/00 «그림 글자 전체 목록»
  python tools/gfx_kr.py      → 고친 파일 바이트(메모리) + 비교 그림 work/gfx_kr_*.png · my files/그래픽/05‥
  build_fc1 / build_fc2 가 patch_*() 를 불러 디스크에 넣는다(디스크 쓰기는 허락받고).
  ⛔영어 그림(SAVE·EXIT·LOAD·PRESS START…)은 그대로(사용자).
"""
import os, struct, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import lzss
from drs_gfx import line_mask, to4, from4

DISC = os.path.join(ROOT, 'work', 'disc')

# 아스테카 지명 — 대사 번역도 이 표기를 따른다(용어 고정)
SUN_PLACES = ['고승의 무덤', '구기장', '카라콜', '수녀원', '카스티요', '전사의 신전',
              '천 기둥의 방', '남쪽 샘', '제물의 샘', '신전 터', '벽']
SUN_PLACES_JP = ['高僧の墓', '球戯場', 'カラコル', '尼僧院', 'カスティーリョ', '戦士の神殿',
                 '千柱の間', '南の泉', 'いけにえの泉', '神殿跡', '壁']


def lz_unpack(d, o):
    n = struct.unpack_from('>I', d, o)[0]
    return lzss.decompress(d[o + 4:o + 4 + n * 2])[:n]


def lz_put(out, o, room, raw, tag):
    comp = lzss.compress(raw)
    assert lzss.decompress(comp)[:len(raw)] == raw
    blk = struct.pack('>I', len(raw)) + comp
    assert len(blk) <= room, ('⛔압축 칸 넘침', tag, hex(o), len(blk), room)
    out[o:o + room] = blk + bytes(room - len(blk))


def stamp(img, m, x0, y0, layers):
    """layers = [(dx, dy, 색)] 순서대로 덮어 그림(뒤가 위)"""
    H, W = img.shape
    for dx, dy, c in layers:
        ys, xs = np.nonzero(m)
        ys = ys + y0 + dy; xs = xs + x0 + dx
        ok = (ys >= 0) & (ys < H) & (xs >= 0) & (xs < W)
        img[ys[ok], xs[ok]] = c


def bold(m):
    """가로 1px 굵게(원본 제목·팝업 획이 2px)"""
    b = np.zeros((m.shape[0], m.shape[1] + 1), m.dtype); b[:, :-1] |= m; b[:, 1:] |= m
    return b


def center_x(w, m):
    return (w - m.shape[1]) // 2


# ── 이스 I 저장 화면 라벨: 색6 글자 + 색F 그림자(+1,+1), 글자 아래끝 = 14행 ──────────────
def ys1_label(w, s):
    img = np.zeros((16, w), np.uint8); m = line_mask('Galmuri9', s, space=4, gap=0)
    assert m.shape[1] + 1 <= w, ('폭 넘침', s)
    y0 = 14 - m.shape[0]; x0 = 1
    stamp(img, m, x0, y0, [(1, 1, 15), (0, 0, 6)]); return img


YS1_L = [  # (L 오프셋, DEM 오프셋, 칸 크기, 폭, 높이, 한글)
    (0x40D10, 0x40D48, 0xD8, 48, 16, '본체 RAM'),
    (0x40DE8, 0x40E20, 0x11C, 88, 16, '카트리지 RAM'),
]


def patch_ys1(L, D):
    Lo, Do = bytearray(L), bytearray(D); pairs = []
    for lo, do, room, w, h, s in YS1_L:
        assert L[lo:lo + room] == D[do:do + room], 'DEM 사본 다름'
        old = from4(lz_unpack(L, lo), w, h); new = ys1_label(w, s)
        lz_put(Lo, lo, room, to4(new), s); lz_put(Do, do, room, to4(new), s)
        pairs.append((old, new, s))
    return bytes(Lo), bytes(Do), pairs


# ── 이스 II DAT00 (무압축 4bpp): 양각 = 2 밝은 쪽, 3 가운데, E 그림자 ──────────────────
def ys2_emboss(w, h, s, font, y_bot):
    img = np.zeros((h, w), np.uint8); m = line_mask(font, s, space=6, gap=1)
    if h >= 16:
        m = bold(line_mask(font, s, space=6, gap=3))
    assert m.shape[1] + 3 <= w, ('폭 넘침', s, m.shape, w)
    x0 = center_x(w - 2, m); y0 = y_bot - m.shape[0]
    stamp(img, m, x0, y0, [(2, 0, 14), (1, 1, 14), (1, 0, 3), (0, 0, 2)]); return img


YS2_DAT00 = [  # (오프셋, 폭, 높이, 한글, 글꼴, 글자 아래끝)
    (0x1C870, 56, 17, '장 비', 'Galmuri14', 16),
    (0x1CA50, 72, 17, '아이템', 'Galmuri14', 16),
    (0xBEB8, 64, 12, '본체 RAM', 'Galmuri9', 11),
    (0xC038, 96, 11, '카트리지 RAM', 'Galmuri9', 11),   # ★높이 11(0x210 B) — 12 로 쓰면 뒤 0xC248 첫 줄을 덮는다
]
# 선택 상태(초록 무늬 단추, 24px 주기 무늬 위에 F 선 + 1 밝은 선 + D 그림자)
YS2_SEL = [(0xC248, 72, 24, '본체 RAM'), (0xC5A8, 104, 24, '카트리지 RAM')]


def ys2_sel_bg(imgs):
    """두 단추의 글자 없는 칸을 모아 24px 주기 무늬를 복원(글자색 F·1·D 제외, 테두리 0행·끝행·첫열·끝열 유지)"""
    tile = np.zeros((24, 24), np.uint8)
    for y in range(24):
        for ph in range(24):
            vals = [im[y, x] for im in imgs for x in range(1, im.shape[1] - 1) if (x - 1) % 24 == ph and im[y, x] not in (15, 1, 13)]
            if vals:
                v, c = np.unique(vals, return_counts=True); tile[y, ph] = v[np.argmax(c)]
    return tile


def ys2_sel(old, tile, s):
    h, w = old.shape; img = old.copy()
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            img[y, x] = tile[y, (x - 1) % 24]
    m = line_mask('Galmuri11', s, space=4, gap=1)
    assert m.shape[1] + 3 <= w - 4, ('폭 넘침', s, m.shape, w)
    x0 = 2 + (w - 4 - m.shape[1] - 2) // 2; y0 = 5 + (12 - m.shape[0]) // 2
    stamp(img, m, x0, y0, [(2, 0, 13), (1, 1, 13), (1, 0, 1), (0, 0, 15)]); return img


def patch_ys2(D):
    out = bytearray(D); pairs = []
    for o, w, h, s, f, yb in YS2_DAT00:
        n = w * h // 2; old = from4(D[o:o + n], w, h); new = ys2_emboss(w, h, s, f, yb)
        out[o:o + n] = to4(new); pairs.append((old, new, s))
    olds = [from4(D[o:o + w * h // 2], w, h) for o, w, h, _ in YS2_SEL]
    tile = ys2_sel_bg(olds)
    for (o, w, h, s), old in zip(YS2_SEL, olds):
        new = ys2_sel(old, tile, s); out[o:o + w * h // 2] = to4(new); pairs.append((old, new, s))
    return bytes(out), pairs


# ── 아스테카 저장 버튼 (SAVE.BIN 112×28, 무압축): 글자 자리를 버튼 바탕 5 로 지우고 F 글자 + 2·3·4 그림자 ──
def sun_clean_button(b1, b2):
    """두 버튼(같은 모양)에서 글자 없는 기둥을 모아 빈 버튼: 1번 글자 x25‥92, 2번 x16‥96 → 가운데는 바탕 5"""
    bg = b1.copy(); bg[6:22, 12:97] = 5
    return bg


def sun_button(bg, s):
    img = bg.copy()
    m = line_mask('Galmuri11-Bold', s, space=4, gap=0)
    assert m.shape[1] + 3 <= 86, ('폭 넘침', s, m.shape)
    x0 = 12 + (85 - m.shape[1] - 3) // 2; y0 = 8
    stamp(img, m, x0, y0, [(3, 3, 4), (2, 2, 3), (1, 1, 2), (0, 0, 15)]); return img


SUN_SAVE = [(0x15980, '본체 RAM'), (0x15FA0, '카트리지 RAM')]


def patch_sun_save(S):
    out = bytearray(S); pairs = []; n = 112 * 28 // 2
    bg = sun_clean_button(*[from4(S[o:o + n], 112, 28) for o, _ in SUN_SAVE])
    for o, s in SUN_SAVE:
        old = from4(S[o:o + n], 112, 28); new = sun_button(bg, s)
        out[o:o + n] = to4(new); pairs.append((old, new, s))
    return bytes(out), pairs


# ── 아스테카 지명 팝업 (96×24, u32+LZSS 블록 11개 연속; H 와 MD.BIN 두 벌) ────────────────
SUN_POP_H = [0x7672B, 0x769BE, 0x76C25, 0x76E3D, 0x77081, 0x7730C, 0x7760A, 0x77879, 0x77A90, 0x77D9B, 0x77FEB]
SUN_POP_MD = [0xE713, 0xE9A6, 0xEC0D, 0xEE25, 0xF069, 0xF2F4, 0xF5F2, 0xF861, 0xFA78, 0xFD83, 0xFFD3]
SUN_POP_ORDER = ['高僧の墓', '球戯場', 'カラコル', '尼僧院', 'カスティーリョ', '戦士の神殿', '千柱の間', '南の泉', 'いけにえの泉', '神殿跡', '壁']


def sun_popup(old, s):
    img = old.copy(); img[3:21, 4:92] = 4                            # 안쪽 바탕(4)으로 지움
    m = bold(line_mask('Galmuri14', s, space=4, gap=1))
    if m.shape[1] + 2 > 88:
        m = bold(line_mask('Galmuri14', s, space=3, gap=0))
    assert m.shape[1] + 2 <= 88, ('폭 넘침', s, m.shape)
    x0 = 4 + (88 - m.shape[1] - 2) // 2; y0 = 4 + (15 - m.shape[0]) // 2
    stamp(img, m, x0, y0, [(2, 2, 3), (1, 1, 2), (0, 0, 14)]); return img


def patch_sun_popups(H, M):
    Ho, Mo = bytearray(H), bytearray(M); pairs = []
    for k, (ho, mo) in enumerate(zip(SUN_POP_H, SUN_POP_MD)):
        hend = SUN_POP_H[k + 1] if k + 1 < len(SUN_POP_H) else None
        raw = lz_unpack(H, ho); assert raw == lz_unpack(M, mo), 'MD 사본 다름'
        # 블록 칸 = 다음 블록 시작까지(마지막은 원래 압축 길이)
        clen = len(lzss_used(H, ho)) + 4
        room = (hend - ho) if hend else clen
        jp = SUN_POP_ORDER[k]; s = SUN_PLACES[SUN_PLACES_JP.index(jp)]
        old = from4(raw, 96, 24); new = sun_popup(old, s)
        lz_put(Ho, ho, room, to4(new), s); lz_put(Mo, mo, room, to4(new), s)
        pairs.append((old, new, s))
    return bytes(Ho), bytes(Mo), pairs


def lzss_used(d, o):
    """블록이 실제로 먹은 압축 바이트"""
    n = struct.unpack_from('>I', d, o)[0]; src = d[o + 4:]
    i = 0; got = 0; flags = 0
    while got < n:
        flags >>= 1
        if not flags & 0x100:
            flags = src[i] | 0xFF00; i += 1
        if flags & 1:
            i += 1; got += 1
        else:
            got += (src[i + 1] & 0xF) + 3; i += 2
    return src[:i]


# ── 아스테카 클리어 타임 화면 SUN/LT_013.BIN (320×224 RGB555 무압축): 검은 상자(0x8842) 라벨 2개 ──────
LT013 = [((42, 59, 20, 109), '「이스Ⅱ」'), ((43, 60, 197, 302), '「태양의 신전」')]


def patch_lt013(b):
    a = np.frombuffer(b, '>u2').reshape(224, 320).copy(); pairs = []
    for (y0, y1, x0, x1), s in LT013:
        old = a[y0:y1, x0:x1].copy()
        a[y0:y1, x0:x1] = 0x8842
        m = line_mask('Galmuri14', s, space=5, gap=1)
        w = x1 - x0; h = y1 - y0
        assert m.shape[1] + 2 <= w, ('폭 넘침', s, m.shape, w)
        xx = x0 + (w - m.shape[1] - 1) // 2; yy = y0 + (h - m.shape[0]) // 2
        reg = a[yy + 1:yy + 1 + m.shape[0], xx + 1:xx + 1 + m.shape[1]]; reg[m == 1] = 0x98C6
        reg = a[yy:yy + m.shape[0], xx:xx + m.shape[1]]; reg[m == 1] = 0xFFFF
        pairs.append((old, a[y0:y1, x0:x1].copy(), s))
    return a.astype('>u2').tobytes(), pairs


def rgb(a):
    a = a.astype(int)
    return np.dstack([(a & 31) << 3, ((a >> 5) & 31) << 3, ((a >> 10) & 31) << 3]).astype(np.uint8)


# ── 허용 범위 검사(바뀐 바이트가 그림 칸 밖이면 중단) ──────────────────────────────────
def allowed(name):
    if name == 'YS1/0YS1L.BIN':
        return [(o, o + r) for o, _, r, *_ in YS1_L]
    if name == 'YS1/0YS1L.DEM':
        return [(d, d + r) for _, d, r, *_ in YS1_L]
    if name == 'YS2/DAT00.BIN':
        return [(o, o + w * h // 2) for o, w, h, *_ in YS2_DAT00] + [(o, o + w * h // 2) for o, w, h, _ in YS2_SEL]
    if name == 'SUN/SAVE.BIN':
        return [(o, o + 112 * 28 // 2) for o, _ in SUN_SAVE]
    if name in ('SUN/1SUNH.BIN', 'SUN/MD.BIN'):
        lst = SUN_POP_H if name == 'SUN/1SUNH.BIN' else SUN_POP_MD
        return [(lst[0], lst[-1] + 0x400)]
    if name == 'SUN/LT_013.BIN':
        return [(0, 224 * 320 * 2)]
    raise KeyError(name)


def check(name, old, new):
    assert len(old) == len(new), ('길이 바뀜', name)
    rg = allowed(name)
    diff = np.nonzero(np.frombuffer(old, np.uint8) != np.frombuffer(new, np.uint8))[0]
    bad = [i for i in diff if not any(a <= i < b for a, b in rg)]
    if bad:
        raise SystemExit('⛔허용 범위 밖 변경 %s 0x%X' % (name, bad[0]))
    return len(diff)


def build_fc1(read):
    L, D = read('YS1/0YS1L.BIN'), read('YS1/0YS1L.DEM')
    L1, D1, p = patch_ys1(L, D)
    return {'YS1/0YS1L.BIN': L1, 'YS1/0YS1L.DEM': D1}, p


def build_fc2(read):
    out = {}; pairs = []
    D1, p = patch_ys2(read('YS2/DAT00.BIN')); out['YS2/DAT00.BIN'] = D1; pairs += p
    S1, p = patch_sun_save(read('SUN/SAVE.BIN')); out['SUN/SAVE.BIN'] = S1; pairs += p
    H1, M1, p = patch_sun_popups(read('SUN/1SUNH.BIN'), read('SUN/MD.BIN')); out['SUN/1SUNH.BIN'] = H1; out['SUN/MD.BIN'] = M1; pairs += p
    T1, _ = patch_lt013(read('SUN/LT_013.BIN')); out['SUN/LT_013.BIN'] = T1
    return out, pairs


# ── 실제 색표(스테이트 VDP1 LUT / CRAM) ─────────────────────────────────────────
def state_pal(state, colr, mode):
    import vdp1cmd
    if mode == 1:
        v = vdp1cmd.load(os.path.join(ROOT, 'work', 'mem', state))
        ent = struct.unpack('>16H', v[colr * 8:colr * 8 + 32])
    else:
        c = open(os.path.join(ROOT, 'work', 'mem', state, 'CRAM.bin'), 'rb').read()
        c = bytes(b for i in range(0, len(c), 2) for b in (c[i + 1], c[i]))
        ent = [struct.unpack_from('>H', c, ((colr & 0x7F0) + k) * 2)[0] for k in range(16)]
    return np.array([[(e & 31) << 3, ((e >> 5) & 31) << 3, ((e >> 10) & 31) << 3] for e in ent], np.uint8)


PALS = {'ys2sel': ('y8', 0x7180, 0), 'ys1': ('s6', 0x1C9C, 1), 'ys2': ('y5', 0x1C8C, 1), 'ys2s': ('y7', 0x7190, 0),
        'sun_save': ('a1', 0x1D54, 1), 'sun_popup': ('a2', 0x1D6C, 1)}


# ── 비교 그림 ──────────────────────────────────────────────────────────────
def sheet(pairs, name, pal_key=None):
    from PIL import Image
    pal = state_pal(*PALS[pal_key or name]); pal[0] = (40, 40, 60)
    W = max(a.shape[1] for a, b, s in pairs) * 2 + 8
    rows = []
    for a, b, s in pairs:
        r = np.zeros((a.shape[0], W, 3), np.uint8); r[:, :a.shape[1]] = pal[a]; r[:, a.shape[1] + 8:a.shape[1] * 2 + 8] = pal[b]
        rows.append(r); rows.append(np.full((3, W, 3), 90, np.uint8))
    img = Image.fromarray(np.vstack(rows)); img = img.resize((img.width * 4, img.height * 4), 0)
    img.save(os.path.join(ROOT, 'work', 'gfx_kr_%s.png' % name))
    return img


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    rd = lambda p: open(os.path.join(DISC, p), 'rb').read()
    L1, D1, p1 = patch_ys1(rd('fc1/YS1_0YS1L.BIN'), rd('fc1/ys1/0YS1L.DEM')); sheet(p1, 'ys1')
    _, p2 = patch_ys2(rd('fc2/ys2/DAT00.BIN')); sheet(p2[:2], 'ys2'); sheet(p2[2:4], 'ys2s'); sheet(p2[4:], 'ys2sel')
    _, p3 = patch_sun_save(rd('fc2/sun/SAVE.BIN')); sheet(p3, 'sun_save')
    _, _, p4 = patch_sun_popups(rd('fc2/SUN_1SUNH.BIN'), rd('fc2/sun/MD.BIN')); sheet(p4, 'sun_popup')
    print('이스I %d · 이스II %d · 아스테카 버튼 %d · 팝업 %d' % (len(p1), len(p2), len(p3), len(p4)))


if __name__ == '__main__':
    main()
