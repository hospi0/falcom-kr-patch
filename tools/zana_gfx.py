# -*- coding: utf-8 -*-
r"""제나두 그림 글자 한글화 (2026-10-03)
  ① 메뉴 판 VDP2 셀 = L 0x150B0 [u32 크기][LZSS] (풀면 0x58C0 = 셀 0‥709, VRAM 0 에 그대로 → 블록 오프셋 = 셀 번호×32), DEM 사본 0x3EB88(아래 DEM_CELLS).
     맵(패턴 이름 표)은 L 안 무압축 u32 표(0xE1C54·0xE2744·0xE5B98·0xE6514… 위 16비트 = 팔레트 비트) — 이 단계에선 안 고침.
     라벨 = 원본 스타일: 글자 밝기 A(위)→8(아래) · 그림자 1(+1,+1) · 배경은 그 줄 옆 배경 셀 무늬.
  python tools/zana_gfx.py   → 미리보기 work/zana_gfx_preview.png (+ my files/그래픽/)
"""
import os, struct, sys
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import gfx_kr, lzss, vdp2render as V
from drs_gfx import line_mask

CELLS = 0x150B0          # L 오프셋
# (스테이트, NBG, 셀 줄 y, 셀 칸 x, 높이(셀), 폭(셀), 글자, 글꼴)
LABELS = [
    ('x5', 1, 5, 20, 2, 6, '공격력', 'Galmuri14'),
    ('x5', 1, 8, 20, 2, 2, '지', 'Galmuri14'), ('x5', 1, 8, 24, 2, 2, '성', 'Galmuri14'),
    ('x5', 1, 11, 24, 2, 2, '혜', 'Galmuri14'),
    ('x5', 1, 14, 20, 2, 2, '매', 'Galmuri14'), ('x5', 1, 14, 24, 2, 2, '력', 'Galmuri14'),
    ('x5', 1, 17, 20, 2, 6, '손재주', 'Galmuri14'),
    ('x5', 1, 20, 20, 2, 2, '민', 'Galmuri14'), ('x5', 1, 20, 24, 2, 2, '첩', 'Galmuri14'),
    ('x5', 1, 23, 20, 2, 6, '항마력', 'Galmuri14'),
    ('x5', 1, 26, 20, 2, 6, '카르마', 'Galmuri14'),
    ('x6', 1, 6, 8, 2, 4, '무기', 'Galmuri14'),
    ('x6', 1, 9, 9, 2, 2, '갑옷', 'Galmuri11-Condensed'),
    ('x6', 1, 12, 9, 2, 2, '방패', 'Galmuri11-Condensed'),
    ('x6', 1, 15, 8, 2, 4, '마법', 'Galmuri14'),
    ('x6', 1, 18, 8, 2, 4, '도구', 'Galmuri14'),
    ('x7', 1, 9, 17, 2, 8, '현재위치', 'Galmuri14'),
]
SHADE = [0xA, 0xA, 0xA, 0x9, 0x9, 0x9, 0x9, 0x9, 0x8, 0x8, 0x8, 0x8, 0x8, 0x8, 0x8, 0x8]


def cell_px(D, k):
    a = np.frombuffer(D[k * 32:k * 32 + 32], np.uint8)
    return np.stack([a >> 4, a & 15], 1).ravel().reshape(8, 8)


def px_cell(p):
    f = p.ravel()
    return bytes((int(f[i]) << 4) | int(f[i + 1]) for i in range(0, 64, 2))


_grid = {}


def grid(state, nbg):
    if (state, nbg) not in _grid:
        _grid[(state, nbg)] = V.render(state, nbg)[1]['cells']
    return _grid[(state, nbg)]


def draw_label(D, spec):
    state, nbg, cy, cx, h, w, text, font = spec
    g = grid(state, nbg)
    cells = g[cy:cy + h, cx:cx + w]
    old = np.vstack([np.hstack([cell_px(D, k) for k in r]) for r in cells])
    bg = np.vstack([np.hstack([cell_px(D, g[cy + r, cx - 1])] * w) for r in range(h)])
    m = line_mask(font, text, space=4, gap=0)
    H, W = bg.shape
    assert m.shape[1] + 1 <= W and m.shape[0] + 1 <= H, ('⛔라벨 폭 넘침', text, m.shape, bg.shape)
    x0 = (W - m.shape[1] - 1) // 2; y0 = (H - m.shape[0] - 1) // 2
    new = bg.copy()
    ys, xs = np.nonzero(m)
    new[ys + y0 + 1, xs + x0 + 1] = 1                         # 그림자
    for y, x in zip(ys, xs):
        new[y + y0, x + x0] = SHADE[min(len(SHADE) - 1, y * 16 // max(1, m.shape[0]))]
    out = {}
    for r in range(h):
        for c in range(w):
            k = int(cells[r, c]); blk = px_cell(new[r * 8:r * 8 + 8, c * 8:c * 8 + 8])
            assert out.get(k, blk) == blk, ('⛔같은 셀에 다른 그림', hex(k), text)
            out[k] = blk
    return out, old, new


# ── 탭(NBG2): ステータス·アイテム 두 탭이 셀 일부를 함께 씀 → 두 탭을 같이 다시 그리고 같은 그림끼리 묶어 원래 글자 셀 22개 안에서 재배정 + 맵 고침
TAB_ROW = [0x111, 0x277, 0x278, 0x279, 0x27A, 0x27B, 0x278, 0x27C, 0x112, 0x111, 0x277, 0x27D]   # 맵 둘째 줄 첫머리(검색 열쇠)
TAB_POOL = [0x275, 0x276] + list(range(0x278, 0x280)) + list(range(0x281, 0x28A)) + [0x113, 0x13B]   # 277·280(왼쪽 가장자리)은 MAP 탭도 써서 뺌   # 13B(탭2 아래 테두리) = 137 과 점 2개 차이 → 맵에서 137 로 돌리고 풀에 넣음
TABS = [((16, 62), '상태', 28), ((88, 126), '아이템', 91)]     # 안쪽 칸 가로(영역 왼쪽 = 맵 칸 1) · 세로 10‥23 · 글자 x(셀 수 최소 탐색)
TAB_FONT = 'Galmuri11-Condensed'   # 셀 21개 안에서 가운데 배치되는 글꼴(탐색)


def tab_maps(L):
    a = np.frombuffer(L[:len(L) // 4 * 4], '>u4'); lo = a & 0xFFFF
    m = np.ones(len(lo) - len(TAB_ROW), bool)
    for k, s in enumerate(TAB_ROW): m &= lo[k:len(lo) - len(TAB_ROW) + k] == s
    return [int(i) for i in np.nonzero(m)[0]]          # u32 색인(맵 줄 2, 칸 1)


def tab_tile(img, y0, y1):
    import collections
    t = np.zeros((y1 - y0 + 1, 8), np.uint8)
    for y in range(y0, y1 + 1):
        for j in range(8):
            c = collections.Counter(int(img[y, x]) for x in list(range(9, 63)) + list(range(81, 127)) if x % 8 == j and img[y, x] in (7, 8, 9))
            t[y - y0, j] = c.most_common(1)[0][0] if c else 8
    return t


def build_tabs(D, L):
    g = grid('x5', 2)
    cells = g[1:4, 1:18]
    img = np.vstack([np.hstack([cell_px(D, k) for k in r]) for r in cells])
    old = img.copy()
    for (xa, xb), text, ox in TABS:
        y0, y1 = 10, 23
        tile = tab_tile(old, y0, y1)                       # 원본 안쪽 배경에서 뽑은 8px 타일(셀 격자 주기 → 빈 셀끼리 같은 그림)
        for x in range(xa, xb + 1):
            img[y0:y1 + 1, x] = tile[:, x % 8]
        m = line_mask(TAB_FONT, text, space=4, gap=1)
        h, w = m.shape; H, W = y1 - y0 + 1, xb - xa + 1
        assert w + 2 <= W and h + 2 <= H, ('⛔탭 글자 넘침', text, m.shape)
        oy = y0 + (H - h) // 2
        ys, xs = np.nonzero(m)
        img[ys + oy + 1, xs + ox + 1] = 6                   # 그림자(거의 검정) — 테두리는 셀이 모자라 뺌
        for y, x in zip(ys, xs):
            img[y + oy, x + ox] = [4, 4, 4, 4, 5, 5, 5, 3, 3, 3, 3, 3][min(11, y * 12 // h)]
    # 셀로 자르고 같은 그림끼리 묶어 풀에 배정
    assign = {}; content = {}; pos = {}
    for r in range(3):
        for c in range(17):
            k = int(cells[r, c])
            if k not in TAB_POOL: continue
            blk = px_cell(img[r * 8:r * 8 + 8, c * 8:c * 8 + 8])
            if blk not in content:
                assert len(content) < len(TAB_POOL), '⛔탭 셀 모자람'
                content[blk] = TAB_POOL[len(content)]
            pos[(r, c)] = content[blk]
    for blk, k in content.items():
        D[k * 32:k * 32 + 32] = blk
    return pos, (old, img, '탭'), len(content)


def patch_tab_maps(L, pos):
    L = bytearray(L); n = 0
    for i in tab_maps(bytes(L)):
        for (r, c), k in pos.items():
            j = (i + (r - 1) * 128 + (c - 0)) * 4          # i = 맵 줄 2·칸 1 → (r=1, c=0)
            hi = struct.unpack_from('>H', L, j)[0]
            struct.pack_into('>HH', L, j, hi, k)
        j = (i + 2 * 128 + 13) * 4                          # 맵 줄 4·칸 14 (13B → 137)
        hi, k = struct.unpack_from('>HH', L, j); assert k == 0x13B, hex(k)
        struct.pack_into('>HH', L, j, hi, 0x137)
        n += 1
    return bytes(L), n


def build_cells(L0):
    D = bytearray(gfx_kr.lz_unpack(L0, CELLS)); pairs = []; written = {}
    for spec in LABELS:
        out, old, new = draw_label(bytes(D), spec)
        for k, blk in out.items():
            assert written.get(k, blk) == blk, ('⛔라벨끼리 셀 충돌', hex(k), spec[6])
            written[k] = blk
        pairs.append((old, new, spec[6]))
    for k, blk in written.items():
        D[k * 32:k * 32 + 32] = blk
    pos, tp, ntab = build_tabs(D, L0)
    pairs.append(tp)
    return bytes(D), pairs, pos


def put_block(L0, D, off=CELLS):
    """셀 블록을 제자리에 다시 넣고 → (새 L, 비게 된 꼬리 [시작, 끝))"""
    L = bytearray(L0)
    room = 4 + len(gfx_kr.lzss_used(L0, off))
    gfx_kr.lz_put(L, off, room, D, 'zana cells')
    used = 4 + len(gfx_kr.lzss_used(bytes(L), off))
    return bytes(L), ((off + used + 3) & ~3, off + room)


# ── ② VDP1 그림(저장 화면·가게) = L 두 번째 그림 표 항목 [u32 주소(0x200000+)][u16 폭][u16 높이] → [u32 크기][LZSS] 4bpp, 색 F 한 색(그림자는 다른 색표로 한 번 더 그림)
DEM_TABLE = 0x29AD8          # DEM 표 = L 표 + 이 값
DEM_CELLS = 0x3EB88
SPRITES = [  # (L 표 항목, 글자, 글꼴)
    (0x1CAC, '쓸 수 없는 데이터', 'Galmuri11'),       # このセーブデータは使えません 112×16
    (0x1CB4, '데이터 없음', 'Galmuri11'),             # データがありません 72×16
    (0x1CBC, '빈 용량이 없음', 'Galmuri11'),          # 空き容量がありません 88×16
    (0x1CC4, '본체RAM', 'Galmuri11-Condensed'),        # 本体RAM 40×16
    (0x1CCC, '카트리지RAM', 'Galmuri11'),             # カートリッジRAM 72×16
    (0x1D24, '팔기', 'Galmuri11'),                    # 売る 24×16
    (0x1D2C, '사기', 'Galmuri11'),                    # 買う
    (0x1D34, '대금', 'Galmuri11'),                    # 代金
]
LEGEND = 0x1D44              # 지도 범례 88×48(아이콘 여러 개) — 둘째 아이콘 아래 작은 「ワ-プ」(5‥11행, 가로 37‥48, 색 7 + 그림자 6) → 「워프」 Galmuri7 한 색(7)


def legend_img(old):
    img = old.copy()
    img[5:12, 34:53] = 0
    m = line_mask('Galmuri7', '워프', space=2, gap=0)
    y0, x0 = 5, 36
    ys, xs = np.nonzero(m)
    img[ys + y0, xs + x0] = 7                                # 7px 글자라 그림자 빼야 또렷함
    return img


def sprite_img(w, h, text, font):
    m = line_mask(font, text, space=4, gap=0)
    assert m.shape[1] <= w and m.shape[0] <= h, ('⛔그림 폭 넘침', text, m.shape, w)
    img = np.zeros((h, w), np.uint8)
    y0 = (h - m.shape[0]) // 2 + 1
    img[y0:y0 + m.shape[0], 0:m.shape[1]][m == 1] = 15
    return img


def put_sprites(L, table_delta, tail):
    """→ (새 바이트, 그림 쌍, 옮긴 개수)"""
    L = bytearray(L); pairs = []; moved = 0; t0, t1 = tail
    for e, text, font in SPRITES + [(LEGEND, '워프', None)]:
        e += table_delta
        a, w, h = struct.unpack_from('>IHH', L, e); o = a - 0x200000
        old = np.frombuffer(gfx_kr.lz_unpack(bytes(L), o), np.uint8)
        old = np.stack([old >> 4, old & 15], 1).ravel().reshape(h, w)
        if font is None:
            new = legend_img(old)
        else:
            assert set(np.unique(old)) <= {0, 15}, '⛔원본 색 가정 다름'
            new = sprite_img(w, h, text, font)
        raw = bytes((int(a2) << 4) | int(b2) for a2, b2 in new.reshape(-1, 2))
        comp = struct.pack('>I', len(raw)) + lzss.compress(raw)
        room = (4 + len(gfx_kr.lzss_used(bytes(L), o)) + 3) & ~3
        if len(comp) <= room:
            L[o:o + room] = comp + bytes(room - len(comp))
        else:                                               # 셀 블록 꼬리(셀 블록 풀 때만 읽던 자리)로 옮김
            assert t0 + len(comp) <= t1, ('⛔옮길 자리 없음', text)
            L[t0:t0 + len(comp)] = comp
            struct.pack_into('>I', L, e, 0x200000 + t0)
            t0 = (t0 + len(comp) + 3) & ~3; moved += 1
        pairs.append((old, new, text))
    return bytes(L), pairs, moved


def build(L0, M0):
    """→ (새 0ZANAL.BIN, 새 0ZANAL.DEM, 미리보기 쌍, 정보)"""
    D, pairs, pos = build_cells(L0)
    assert gfx_kr.lz_unpack(M0, DEM_CELLS) == gfx_kr.lz_unpack(L0, CELLS), '⛔DEM 셀 블록이 다름'
    out = []
    for X0, off, td in ((L0, CELLS, 0), (M0, DEM_CELLS, DEM_TABLE)):
        X, tail = put_block(X0, D, off)
        X, nmap = patch_tab_maps(X, pos)
        assert nmap >= 1, '⛔탭 맵 못 찾음'
        X, sp, moved = put_sprites(X, td, tail)
        out.append((X, nmap, moved, sp))
    (L, n1, m1, sp), (M, n2, m2, _) = out
    return L, M, pairs + sp, dict(tab_maps=(n1, n2), moved=(m1, m2), tab_cells=len(set(pos.values())))


def preview(pairs, path):
    v, reg, cram = V.load('x5')
    pal = np.array([V.rgb(cram[0x4d * 16 + c]) for c in range(16)])
    rows = []
    for old, new, s in pairs:
        W = max(64 * 3, old.shape[1])
        a = np.zeros((old.shape[0] * 2 + 2, W), int); a[:old.shape[0], :old.shape[1]] = old; a[old.shape[0] + 2:, :new.shape[1]] = new
        rows.append(a)
    im = np.vstack(rows)
    Image.fromarray(pal[im].astype(np.uint8)).resize((im.shape[1] * 4, im.shape[0] * 4), Image.NEAREST).save(path)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    L0 = open(os.path.join(ROOT, 'work', 'disc', 'fc1', 'zana', '0ZANAL.BIN'), 'rb').read()
    M0 = open(os.path.join(ROOT, 'work', 'disc', 'fc1', 'zana', '0ZANAL.DEM'), 'rb').read()
    L, M, pairs, info = build(L0, M0)
    print(info)
    preview(pairs, os.path.join(ROOT, 'work', 'zana_gfx_preview.png'))
