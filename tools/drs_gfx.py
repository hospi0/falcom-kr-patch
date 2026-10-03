# -*- coding: utf-8 -*-
r"""드래곤 슬레이어 그림 글자 한글화 (2026-10-03)
  글자는 전부 그림 — DRS/0DRSL.BIN(저 워크램 이미지)에 무압축 4bpp, 실행 코드 1DRSH.BIN 의 그림 표
  (12 B 항목 = [L 주소 u32][바이트 수 u16][폭 u16][높이 u8 …])가 가리킨다. 데모 사본 0DRSL.DEM 도 같은 오프셋 → 둘 다 고친다.
  범위(사용자 결정 2026-10-03): 일본어 그림만. 영어 메뉴·범례·스태프 롤(일본어 줄 포함)은 원본 유지.

  python tools/drs_gfx.py              → 미리보기 work/drs_preview.png + my files/그래픽/ 비교 그림
  python tools/drs_gfx.py --write      → work/out/ 트랙 01 (+cue·나머지 트랙은 원본 경로를 cue 로 참조하지 않으므로 복사)
  python tools/drs_gfx.py --install    → + F: 설치
"""
import hashlib, os, shutil, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import bdf, disc, iso

SRC = os.path.dirname(disc.TRACK['fc1'])
TRACK01 = os.path.basename(disc.TRACK['fc1'])
OUT = os.path.join(ROOT, 'work', 'out', 'fc1')
F_DIR = r'F:\hospi\roms\ss roms\Falcom Classics (Japan) (Disc 1) (Game Disc)'
FILES = ['DRS/0DRSL.BIN', 'DRS/0DRSL.DEM']

# 오프닝 10줄: 272×16, 색1 글자 + 검은 테두리(색4), 가운데 맞춤 (원본은 색2 그림자) — 줄마다 [팔레트 32 B][그림 0x880 B]
OPENING = 0x8F9B8
OPENING_EDGE = 4          # 줄 팔레트 [8000 FFFF 8C63 B196 8000 …] 의 4 = 불투명 검정
OPENING_KR = [
    '어딘가로 사라져 버린 검을 찾고,',
    '성스러운 푸른 돌 「파워스톤」으로 힘을 모아,',
    '수많은 마법을 구사하여,',
    '이 세계의 구조를 밝혀내고,',
    '광대한 미궁 끝에 있는',
    '「머리 셋 달린 드래곤」을 쓰러뜨려',
    '네 개의 왕관을 네 손에 되찾아라.',
    '그리고 마지막으로 전설의 검',
    '「드래곤 슬레이어」',
    '를 손에 넣어라.',
]
# 저장 화면: 원본 입체 글자(색 5 → 4 → 1) — 한글은 5 + 그림자 1. (오프셋, 폭, 높이, 줄들, 첫 줄 y, 줄 간격, 맞춤)
SAVE = [
    (0x066BB8, 48, 16, ['본체RAM'], 6, 16, 'left'),
    (0x066D58, 80, 16, ['카트리지RAM'], 6, 16, 'left'),
    (0x066FF8, 112, 16, ['빈 용량이 부족합니다.'], 4, 16, 'left'),
    (0x067398, 184, 88, ['이대로 계속하면 빈 용량이', '부족해서 기록을 저장할 수', '없습니다.',
                         '새 기록을 저장하려면', '113의 빈 용량이 필요합니다.'], 7, 16, 'left'),
    (0x069358, 96, 16, ['사용할 수 없습니다.'], 4, 16, 'left'),
]
# 타이틀 문구 「前代未聞麻薬的爽快遊戯」 224×24, 15단 회색 팔레트 → 한 색(E) + 둘레 1px(4)
TAGLINE = (0x0533F8, 224, 24, '전대미문 마약적 상쾌 유희')


def glyph(font, ch):
    g = bdf.load(font).get(ord(ch))
    if g is None:
        raise SystemExit('⛔글꼴 %s 에 없는 글자 %r' % (font, ch))
    w, h, ox, oy, rows = g
    a = np.zeros((h, w), np.uint8)
    for i, r in enumerate(rows):
        v = int(r, 16); nb = len(r) * 4
        for x in range(w):
            a[i, x] = (v >> (nb - 1 - x)) & 1
    return a, ox, oy, g


def line_mask(font, s, space=4, gap=1):
    """한 줄 → 0/1 (베이스라인 맞춤). 글자 간격 = 비트맵 폭 + 1 + gap, 공백 = space(글꼴 공백은 비트맵 폭 0 이라 따로)"""
    parts = []; top = 0; bot = 0
    for ch in s:
        if ch == ' ':
            parts.append((np.zeros((1, max(space - 1 - gap, 0)), np.uint8), 0, 0)); continue
        a, ox, oy, g = glyph(font, ch)
        parts.append((a, ox, oy)); top = max(top, a.shape[0] + oy); bot = min(bot, oy)
    adv = lambda a, ox: a.shape[1] + max(ox, 0) + 1 + gap
    W = sum(adv(a, ox) for a, ox, oy in parts)
    img = np.zeros((top - bot, W + 2), np.uint8); x = 0
    for a, ox, oy in parts:
        y = top - (a.shape[0] + oy); xx = x + max(ox, 0)
        img[y:y + a.shape[0], xx:xx + a.shape[1]] |= a; x += adv(a, ox)
    xs = np.nonzero(img.any(0))[0]
    return img[:, :xs[-1] + 1] if len(xs) else img


def to4(px):
    return bytes((int(px.flat[i]) << 4) | int(px.flat[i + 1]) for i in range(0, px.size, 2))


def from4(b, w, h):
    raw = np.frombuffer(b, np.uint8)
    return np.stack([raw >> 4, raw & 15], 1).reshape(h, w)


def draw_opening(s):
    """2026-10-03 사용자: 갈무리11 보통체 + 검은 1px 테두리(팔레트 4 = 0x8000 불투명 검정). 원본 회색 그림자(색2)는 뺌."""
    W, H = 272, 16
    m = line_mask('Galmuri11', s, space=6)
    assert m.shape[1] + 2 <= W - 2, ('오프닝 줄 폭 넘침', s, m.shape)
    img = np.zeros((H, W), np.uint8)
    x0 = (W - m.shape[1]) // 2; y0 = max(1, min(4 + (11 - m.shape[0] + 1) // 2, H - 1 - m.shape[0]))
    ink = np.zeros((H, W), bool); ink[y0:y0 + m.shape[0], x0:x0 + m.shape[1]] = m == 1
    ring = np.zeros_like(ink)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            ring |= np.roll(np.roll(ink, dy, 0), dx, 1)
    img[ring & ~ink] = OPENING_EDGE; img[ink] = 1
    return img


def draw_emboss(w, h, lines, y0, pitch, align):
    img = np.zeros((h, w), np.uint8)
    for k, s in enumerate(lines):
        m = line_mask('Galmuri9', s, space=4, gap=0)
        assert m.shape[1] + 1 <= w, ('저장 문구 폭 넘침', s, m.shape[1] + 1, w)
        x0 = 0 if align == 'left' else (w - m.shape[1] - 2) // 2
        y = y0 + k * pitch
        assert y + m.shape[0] + 1 <= h, ('저장 문구 높이 넘침', s)
        L = lambda dx, dy: (slice(y + dy, y + dy + m.shape[0]), slice(x0 + dx, x0 + dx + m.shape[1]))
        for dx, dy, c in ((1, 1, 1), (0, 0, 5)):     # 원본은 5·4·1 세 겹(획 3px)인데 한글 9px 은 뭉개져서 5 글자 + 1 그림자(+1,+1)만(2026-10-03 확대 비교)
            reg = img[L(dx, dy)]; reg[m == 1] = c
    return img


def draw_tagline(w, h, s):
    m = line_mask('Galmuri14', s, space=6)
    assert m.shape[1] + 2 <= w, ('타이틀 문구 폭 넘침', s, m.shape)
    img = np.zeros((h, w), np.uint8)
    x0 = (w - m.shape[1]) // 2; y0 = (h - m.shape[0]) // 2 + 1
    ink = np.zeros((h, w), bool); ink[y0:y0 + m.shape[0], x0:x0 + m.shape[1]] = m == 1
    ring = np.zeros_like(ink)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            ring |= np.roll(np.roll(ink, dy, 0), dx, 1)
    img[ring & ~ink] = 4; img[ink] = 14
    return img


def patch_l(L):
    """→ 새 L 바이트, 바뀐 구역 목록, 비교용 (원본, 새) 그림 목록"""
    out = bytearray(L); regions = []; pairs = []
    for k, s in enumerate(OPENING_KR):
        o = OPENING + k * 0x8A0
        new = draw_opening(s); pairs.append((from4(L[o:o + 0x880], 272, 16), new, 'op%d' % k))
        out[o:o + 0x880] = to4(new); regions.append((o, o + 0x880))
    for o, w, h, lines, y0, pitch, al in SAVE:
        n = w * h // 2; new = draw_emboss(w, h, lines, y0, pitch, al)
        pairs.append((from4(L[o:o + n], w, h), new, lines[0])); out[o:o + n] = to4(new); regions.append((o, o + n))
    o, w, h, s = TAGLINE; n = w * h // 2; new = draw_tagline(w, h, s)
    pairs.append((from4(L[o:o + n], w, h), new, 'tagline')); out[o:o + n] = to4(new); regions.append((o, o + n))
    for i in range(len(L)):                                            # 범위 밖 변경 0
        if L[i] != out[i] and not any(a <= i < b for a, b in regions):
            raise SystemExit('⛔허용 범위 밖 변경 0x%X' % i)
    return bytes(out), regions, pairs


def preview(pairs, L):
    pal = np.zeros((16, 3), np.uint8)
    for c in range(16):
        pal[c] = (c * 17,) * 3
    pal[1] = (250, 250, 250); pal[2] = (120, 120, 120); pal[4] = (110, 110, 140); pal[5] = (230, 230, 255)
    rows = []
    for a, b, _ in pairs:
        w = a.shape[1]; pad = np.zeros((a.shape[0] * 2 + 6, 320, 3), np.uint8)
        pad[:a.shape[0], :w] = pal[a]; pad[a.shape[0] + 2:a.shape[0] * 2 + 2, :w] = pal[b]
        rows.append(pad)
    img = np.vstack(rows)
    from PIL import Image
    Image.fromarray(img).resize((640, img.shape[0] * 2), 0).save(os.path.join(ROOT, 'work', 'drs_preview.png'))
    gd = os.path.join(ROOT, 'my files', '그래픽'); os.makedirs(gd, exist_ok=True)
    Image.fromarray(img).resize((640, img.shape[0] * 2), 0).save(os.path.join(gd, '01_드래곤슬레이어_글자그림(줄마다 위원본_아래한글).png'))


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    a = sys.argv[1:]
    L0 = disc.read('fc1', FILES[0]); D0 = disc.read('fc1', FILES[1])
    assert L0 == D0 or True
    L1, regions, pairs = patch_l(L0)
    D1 = bytearray(D0)
    for s, e in regions:
        assert D0[s:e] == L0[s:e], ('DEM 사본이 다른 구역', hex(s))
        D1[s:e] = L1[s:e]
    preview(pairs, L0)
    print('그림 %d장 · 바뀐 바이트 %d (BIN) / DEM 같은 구역' % (len(pairs), sum(e - s for s, e in regions)))
    if '--write' in a or '--install' in a:
        os.makedirs(OUT, exist_ok=True)
        dst = os.path.join(OUT, TRACK01); shutil.copyfile(disc.TRACK['fc1'], dst)
        iso.patch_sub(dst, {FILES[0]: L1, FILES[1]: bytes(D1)})
        print('트랙 01', dst, hashlib.md5(open(dst, 'rb').read()).hexdigest())
        if '--install' in a:
            shutil.copyfile(dst, os.path.join(F_DIR, TRACK01)); print('F: 설치', F_DIR)


if __name__ == '__main__':
    main()
