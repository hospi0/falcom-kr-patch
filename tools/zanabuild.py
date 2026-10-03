# -*- coding: utf-8 -*-
r"""제나두 대사 되쓰기 (2026-10-03)
  대사 = ZANA/1ZANAH.BIN 0x921EC‥0x95F10 u16 BE(아틀라스 번호, FFD 줄 · FFF 끝) — 포인터 표 H 0x95F10‥0x966E4(u32, 501개, 0x06002000 기준).
         표 항목 2개는 문장 «중간 줄 머리»(FFD 뒤)를 가리킨다 → (문장, 줄 번호) 로 기억했다가 새 위치로.
         1ZANAH.DEM = 같은 내용이 +0x3CC 에, 포인터 값도 +0x3CC.
  글꼴 = ZANA/0ZANAL.BIN(.DEM 도 같은 자리) 12×12 2bpp 아틀라스 L 0xBB3A0 — 가나·한자 칸(0x50‥0x34F, 기호 0xF0‥0xFF 빼고)에 한글.
         단색(0/1), 갈무리11. 반각 공백 코드가 없어 공백 = 0(빈 칸 12px).
  번역 = my files/번역/zana_*.tsv + work/tr_fix/zana.tsv (ystrans: 대화 16칸 · 오프닝/엔딩/제작진 24칸)
"""
import collections, os, re, struct, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import ystext, ystrans, zanatext, ysbuild

BASE = 0x06002000
TXT = (0x921EC, 0x95F10)
TAB = (0x95F10, 0x966E4)
DEM = 0x3CC
ORIGIN, ROWB = zanatext.ORIGIN, zanatext.ROWB
NL = chr(92) + 'n'; PG = chr(92) + 'p'
FW = dict(ysbuild.FW); FW.update({' ': '　', '(': '（', ')': '）', '+': '＋', '=': '＝', '-': '－'})


def u16s(b): return list(struct.unpack('>%dH' % (len(b) // 2), b))


def strings(H, delta=0):
    """구역 안 문장 [(시작, 끝)] (FFF 단위, 파일 안 절대 위치)"""
    t = TXT[0] + delta
    v = u16s(H[t:TXT[1] + delta]); out = []; a = 0
    for i, c in enumerate(v):
        if c == 0xFFF:
            out.append((t + 2 * a, t + 2 * (i + 1))); a = i + 1
    return out


def slots(H, trmap, m):
    """한글을 그릴 칸: 가나·한자 칸 중 «번역 안 되는 문장»이 쓰지 않는 것"""
    keep = set()
    for a, e in strings(H):
        cs = u16s(H[a:e - 2])
        if ystext.decode(cs, m) not in trmap: keep.update(cs)
    return [c for c in range(0x50, 0x350) if not 0xF0 <= c < 0x100 and c not in keep]


def alloc(trmap, sl):
    syl = collections.Counter(ch for t in trmap.values() for ch in t if '가' <= ch <= '힣')
    order = sorted(syl, key=lambda c: (-syl[c], c))
    if len(order) > len(sl):
        raise SystemExit('⛔제나두 글자 칸 부족: 필요 %d · 칸 %d' % (len(order), len(sl)))
    return {ch: sl[i] for i, ch in enumerate(order)}


def encode(s, amap, inv):
    out = []; i = 0
    while i < len(s):
        if s.startswith(NL, i): out.append(0xFFD); i += 2; continue
        if s.startswith(PG, i): out.append(0xFFE); i += 2; continue
        ch = s[i]; i += 1
        if ch in amap: out.append(amap[ch]); continue
        c2 = FW.get(ch, ch)
        if 'A' <= c2 <= 'Z': c2 = chr(ord(c2) - 0x41 + 0xFF21)
        if 'a' <= c2 <= 'z': c2 = chr(ord(c2) - 0x61 + 0xFF41)
        if c2 in inv and (inv[c2] < 0x50 or 0xF0 <= inv[c2] < 0x100):
            out.append(inv[c2]); continue
        raise SystemExit('⛔제나두 인코딩 못 하는 글자 %r in %r' % (ch, s[:30]))
    return out + [0xFFF]


def write_font(L, amap):
    L = bytearray(L); cell = 12; bpr = ROWB // cell
    for ch, code in amap.items():
        m = ysbuild.glyph_mask(ch, 'Galmuri11', cell)
        r, c = divmod(code, 16)
        for y in range(cell):
            base = ORIGIN + (r * cell + y) * bpr + c * cell // 4
            row = 0
            for x in range(cell):
                row = (row << 2) | int(m[y, x])
            L[base:base + cell // 4] = row.to_bytes(cell // 4, 'big')
    return bytes(L)


def build_h(H0, trmap, amap, inv, m, delta=0):
    """H(또는 DEM) → 새 바이트. delta = DEM 이면 0x3CC"""
    H = bytearray(H0)
    t0, t1 = TAB[0] + delta, TAB[1] + delta
    P = [struct.unpack_from('>I', H0, q)[0] - BASE - delta for q in range(t0, t1, 4)]
    S = strings(H0, delta)
    # 각 표 항목 → (문장 번호, 줄 번호)
    idx = []
    for p in P:
        p += delta
        k = next(k for k, (a, e) in enumerate(S) if a <= p < e)
        a = S[k][0]; line = u16s(H0[a:p]).count(0xFFD)
        assert p == a or H0[p - 2:p] == b'\x0f\xfd', ('항목이 줄 머리가 아님', hex(p))
        idx.append((k, line))
    encs = []; stat = collections.Counter()
    for a, e in S:
        cs = u16s(H0[a:e])
        src = ystext.decode(cs[:-1], m)
        if src in trmap:
            encs.append(tuple(encode(trmap[src], amap, inv))); stat['tr'] += 1
        else:
            encs.append(tuple(cs)); stat['keep'] += 1
    # 같은 문장·다른 문장의 꼬리와 같은 문장은 자리를 함께 쓴다(실행 중 대사 구역은 고쳐 쓰이지 않음 — 스테이트 8개 확인)
    new = []; at = {}
    for c in sorted(set(encs), key=len, reverse=True):
        host = next((h for h in at if len(h) > len(c) and h[-len(c):] == c), None)
        if host is not None:
            at[c] = at[host] + len(host) - len(c); stat['tail_shared'] += 1
        else:
            at[c] = len(new); new += c
    starts = [at[c] for c in encs]
    room = (TXT[1] - TXT[0]) // 2
    if len(new) > room:
        raise SystemExit('⛔제나두 대사 구역 넘침 %d > %d 단어' % (len(new), room))
    stat['words'] = len(new); stat['room'] = room
    new += [0] * (room - len(new))
    H[TXT[0] + delta:TXT[1] + delta] = struct.pack('>%dH' % room, *new)
    for q, (k, line) in zip(range(t0, t1, 4), idx):
        w = starts[k]; n = 0
        while n < line:
            if new[w] == 0xFFD: n += 1
            w += 1
            if new[w - 1] == 0xFFF: raise SystemExit('⛔제나두 줄 수 줄어듦: 문장 %d 줄 %d' % (k, line))
        struct.pack_into('>I', H, q, BASE + delta + TXT[0] + 2 * w)
    return bytes(H), stat


def build(H0, D0, L0, LD0):
    """→ (새 H, 새 H DEM, 새 L, 새 L DEM, 정보)"""
    m = zanatext.charmap(); inv = {}
    for k, v in sorted(m.items()): inv.setdefault(v, k)
    trmap, probs = ystrans.translations('zana')
    if probs: raise SystemExit('⛔제나두 번역 문제 %d: %s' % (len(probs), probs[:3]))
    amap = alloc(trmap, slots(H0, trmap, m))
    H, st = build_h(H0, trmap, amap, inv, m)
    D, st2 = build_h(D0, trmap, amap, inv, m, DEM)
    assert H[TXT[0]:TXT[1]] == D[TXT[0] + DEM:TXT[1] + DEM]
    L = write_font(L0, amap); LD = write_font(LD0, amap)
    for o, n, rg in ((H0, H, [TXT, TAB]), (D0, D, [(a + DEM, b + DEM) for a, b in (TXT, TAB)]),
                     (L0, L, [(ORIGIN, ORIGIN + ROWB * 53)]), (LD0, LD, [(ORIGIN, ORIGIN + ROWB * 53)])):
        d = np.nonzero(np.frombuffer(o, np.uint8) != np.frombuffer(n, np.uint8))[0]
        bad = [i for i in d if not any(a <= i < b for a, b in rg)]
        if bad: raise SystemExit('⛔제나두 허용 범위 밖 변경 0x%X' % bad[0])
    return H, D, L, LD, dict(syllables=len(amap), **st)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    rd = lambda n: open(os.path.join(ROOT, 'work', 'disc', 'fc1', 'zana', n), 'rb').read()
    H, D, L, LD, info = build(rd('1ZANAH.BIN'), rd('1ZANAH.DEM'), rd('0ZANAL.BIN'), rd('0ZANAL.DEM'))
    print(info)
