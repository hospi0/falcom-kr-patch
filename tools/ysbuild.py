# -*- coding: utf-8 -*-
r"""이스 계열 대사 되넣기 (2026-10-03, 먼저 이스 I)
  ① 한글 음절 → 글꼴 칸 배정(가나 0x30‥0xCF + 한자 0xE0‥) ② 번역 인코딩(u16) ③ 문장 배치
  배치 규칙
   · 스크립트 묶음 안 문장(참조 명령 있는 것) = 묶음 문장 구역 안에서 다시 깔고 참조 피연산자 고침
   · 그 밖 문장·시스템 목록 줄 = 제자리(원래 길이 안, 남는 칸은 공백 0x000)
  python tools/ysbuild.py ys1 budget   → 예산 표
"""
import collections, os, re, struct, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import ystext, ysrefs, ystrans

NL = chr(92) + 'n'; PG = chr(92) + 'p'
FW = {'0': '０', '1': '１', '2': '２', '3': '３', '4': '４', '5': '５', '6': '６', '7': '７', '8': '８', '9': '９',
      ',': '，', '.': '．', '!': '！', '?': '？', '(': '（', ')': '）', '/': '／', ':': '：', '=': '＝', '-': '－', '"': '”',
      '~': '～'}
ARG_CMDS = {0xFFB}                      # 뒤 한 칸이 인자(원래 코드값 그대로)
SPECIAL = ["'"]
PRIV = 0xF0000                           # 이스 I 오리지널 집 안 창용 «16px 전용 칸» 글자(원래 글자 + PRIV) — 세트 3 영문 칸이 10×12 라 숫자·부호가 겹침                         # 글꼴에 없어 빈 칸에 새로 그리는 기호


def slots(game):
    lim = ystext.limit(game)
    s = list(range(0x30, 0xD0))                         # 히라가나·가타카나
    s += list(range(0x100 if game == 'sun' else 0xE0, lim))   # 한자(아스테카는 E0‥FF 영소문자 유지)
    return s


def alloc(game, trs):
    syl = collections.Counter()
    for v in trs.values():
        body = re.sub(r'\{FFB\}.', '', re.sub(r'\{[0-9A-F]+\}', lambda m: m.group(0) if m.group(0) == '{FFB}' else '', v))
        for ch in body:
            if '가' <= ch <= '힣' or ch in SPECIAL or ord(ch) >= PRIV: syl[ch] += 1
    sl = slots(game)
    order = sorted(syl, key=lambda c: (-syl[c], c))
    if len(order) > len(sl):
        raise SystemExit('⛔글자 칸 부족 %s: 필요 %d · 칸 %d' % (game, len(order), len(sl)))
    return {ch: sl[i] for i, ch in enumerate(order)}


def encode(game, s, amap, inv):
    out = []; i = 0
    while i < len(s):
        m = re.match(r'\{([0-9A-F]{3,4})\}', s[i:])
        if m:
            c = int(m.group(1), 16); out.append(c); i += len(m.group(0))
            if c in ARG_CMDS:
                out.append(inv[s[i]]); i += 1           # 인자 = 원래 코드
            continue
        if s.startswith(NL, i): out.append(0xFFD); i += 2; continue
        if s.startswith(PG, i): out.append(0xFFE); i += 2; continue
        ch = s[i]; i += 1
        if ch in amap: out.append(amap[ch]); continue
        if ch == ' ': out.append(0x000); continue   # E08 은 멈춤 코드(공백 아님 — 이스 I·아스테카 실기 2026-10-03) → 전각 공백
        if ch == '　': out.append(0x000); continue
        ch2 = FW.get(ch, ch)
        if 'A' <= ch2 <= 'Z': ch2 = chr(ord(ch2) - 0x41 + 0xFF21)
        if 'a' <= ch2 <= 'z': ch2 = chr(ord(ch2) - 0x61 + 0xFF41)
        if ch2 in inv and (inv[ch2] < 0x30 or 0xD0 <= inv[ch2] < 0xE0 or (game == 'sun' and 0xE0 <= inv[ch2] < 0x100)):
            out.append(inv[ch2]); continue
        raise SystemExit('⛔인코딩 못 하는 글자 %r in %r' % (ch, s[:40]))
    return out + [0xFFF]


def model(game):
    """→ 문장 목록 [{파일, 시작, 끝, 원문코드, 원문, 종류(block/fixed/sys), 묶음}]"""
    rows = [l.rstrip('\n').split('\t') for l in open(os.path.join(ROOT, 'work', 'text', game + '.tsv'), encoding='utf-8')][1:]
    blocks = ysrefs.blocks(game); R = ysrefs.refs(game)
    refd = collections.defaultdict(list)
    for f, B, p, op, S in R:
        refd[(os.path.basename(f), S)].append((B, p))
    bl = {os.path.basename(f): sorted(b) for f, b in blocks.items()}
    out = []
    for r in rows:
        f, a, e, src = r[1], int(r[2], 16), int(r[3], 16), r[4]
        kind = 'sys' if r[0][len(game)] == 's' else ('block' if (f, a) in refd else 'fixed')
        B = None
        if kind == 'block':
            B = refd[(f, a)][0][0]
        out.append(dict(no=r[0], file=f, a=a, e=e, src=src, kind=kind, B=B, refs=refd.get((f, a), [])))
    return out, bl


def budget(game):
    trs, probs = ystrans.translations(game)
    amap = alloc(game, trs); inv = {v: k for k, v in ystext.charmap(game).items()}
    S, bl = model(game)
    per = collections.defaultdict(lambda: [0, 0]); over = []
    for s in S:
        n_old = (s['e'] - s['a']) // 2
        tr = trs.get(s['src'])
        if tr is None:
            n_new = n_old
        else:
            n_new = len(encode(game, tr, amap, inv)) - (1 if s['kind'] == 'sys' else 0)
        key = (s['kind'], s['B'])
        per[key][0] += n_old; per[key][1] += n_new
        if s['kind'] != 'block' and n_new > n_old:
            over.append((s['no'], s['kind'], hex(s['a']), n_old, n_new, s['src'][:20]))
    print(game, '음절', len(amap), '/ 칸', len(slots(game)))
    for k in sorted(per, key=lambda k: (k[0], k[1] or 0)):
        o, n = per[k]; print('  %-6s %-8s 원래 %6d  번역 %6d  %s' % (k[0], hex(k[1]) if k[1] else '-', o, n, '⛔넘침' if n > o else ''))
    print('  제자리 문장 넘침', len(over))
    for x in over[:30]: print('   ', x)
    return amap


# ── 이스 I 배치 ─────────────────────────────────────────────────────────────
YS1 = dict(
    file='fc1/YS1_0YS1L.BIN',
    ops={0x50, 0x51, 0x52},
    groups=[(0x84E9C, None), (0x8E8F4, None)],          # 묶음 표 위치(u32 절대, 묶음 무리 바로 뒤)
    seq=[  # (시작, 끝, 구분 코드) — 순서만 지키면 되는 영역(포인터는 시작만)
        (0x79B1C, 0x7A274, 0xFFD), (0x7A274, 0x7A330, None), (0x7A330, 0x7A474, 0xFFD),
        (0x7B20A, 0x7BBFE, 0xFFD), (0x7BBFE, 0x7C470, 0xFFF), (0x7C470, 0x7CB20, 0xFFF)],
)


def u16s(b):
    return list(struct.unpack('>%dH' % (len(b) // 2), b))


def pack16(v):
    return struct.pack('>%dH' % len(v), *v)


def seq_region(L, a, e, trmap, game, amap, inv, sep):
    """[a,e) = 구분 코드로 나뉜 줄/문장 열. 각 조각을 번역으로 바꿔 순서대로 다시 깔고 끝 조각에 공백을 채운다"""
    v = u16s(L[a:e]); m = ystext.charmap(game)
    # 조각: 끝 코드(FFD/FFF/FFE) 포함
    parts = []; cur = []
    for c in v:
        cur.append(c)
        if c in (0xFFD, 0xFFF) and (sep is None or c == sep or c == 0xFFF):
            parts.append(cur); cur = []
    if cur: parts.append(cur)
    out = []
    for p in parts:
        body, end = p[:-1], p[-1]
        if end not in (0xFFD, 0xFFF):
            body, end = p, None
        src = ystext.decode(body, m)
        tr = trmap.get(src)
        nb = encode(game, tr, amap, inv)[:-1] if tr is not None else body
        out.append(nb + ([end] if end is not None else []))
    flat = [c for p in out for c in p]
    room = len(v)
    if len(flat) > room:
        raise SystemExit('⛔영역 넘침 0x%X‥0x%X: %d > %d' % (a, e, len(flat), room))
    # 남는 칸: 마지막 조각의 끝 코드 앞에 반각 공백
    pad = room - len(flat)
    last = out[-1]
    if last and last[-1] in (0xFFD, 0xFFF):
        out[-1] = last[:-1] + [0xE08] * pad + [last[-1]]
    else:
        out[-1] = last + [0xE08] * pad
    flat = [c for p in out for c in p]
    assert len(flat) == room
    return pack16(flat)


def seq_bytes(L, a, e, trmap, game, amap, inv):
    """FFF 로 끝나는 문장 열을 번역해 이어 붙인 코드 목록(패딩 없음)"""
    v = u16s(L[a:e]); m = ystext.charmap(game); out = []; cur = []
    for c in v:
        cur.append(c)
        if c == 0xFFF:
            src = ystext.decode(cur[:-1], m); tr = trmap.get(src)
            out += encode(game, tr, amap, inv) if tr is not None else cur
            cur = []
    assert not cur, '영역 끝이 FFF 아님'
    return out


# ── 줄 목록 다시 깔기 + 그 줄을 가리키는 표 고치기 (2026-10-03 실기: 목록은 «표가 줄마다» 가리킨다) ──
def relayout(L, a, e, trmap, game, amap, inv, seps=(0xFFD, 0xFFF), join=True):
    """[a,e) 를 seps 로 끝나는 조각으로 나눠 번역 → (새 코드, {옛 시작: 새 시작}, {옛 시작: (옛 글자 수, 새 글자 수)}). a 에 깐다고 보고 주소 계산.
    join = 번역의 줄바꿈·쪽을 공백으로(목록 줄은 표가 줄마다 가리켜서 줄을 늘리면 뒷부분이 안 나온다)"""
    v = u16s(L[a:e]); m = ystext.charmap(game); out = []; posmap = {}; lens = {}; cur = []; old = a
    for c in v:
        cur.append(c)
        if c in seps:
            body, end = cur[:-1], cur[-1]
            tr = trmap.get(ystext.decode(body, m))
            if tr is not None and join: tr = tr.replace(NL, ' ').replace(PG, ' ')
            nb = encode(game, tr, amap, inv)[:-1] if tr is not None else body
            posmap[old] = a + 2 * len(out)
            lens[old] = (sum(1 for x in body if x < 0xE00), sum(1 for x in nb if x < 0xE00))
            out += nb + [end]; old += 2 * len(cur); cur = []
    assert not cur, '목록 끝이 구분 코드 아님 0x%X' % e
    return out, posmap, lens


def fit_region(out, a, e):
    room = (e - a) // 2
    if len(out) > room: raise SystemExit('⛔목록 넘침 0x%X‥0x%X: %d > %d' % (a, e, len(out), room))
    return pack16(out + [0xFFF] * (room - len(out)))     # 남는 칸 = 마지막 줄 «뒤» 빈 문장(E08 을 글자로 그리는 화면이 있다 — 오프닝 실기 2026-10-03)


def fix_u16(L, L0, ta, te, base, posmap, newbase=None, run=False):
    """u16 단어 오프셋 표(값 = (줄−base)/2). run = 첫 «줄 아닌 값»에서 멈춤(표 끝을 모를 때). → 고친 칸 수"""
    nb = base if newbase is None else newbase; n = 0; q = ta
    while q < te:
        w = struct.unpack_from('>H', L0, q)[0]; old = base + 2 * w
        if old in posmap: struct.pack_into('>H', L, q, (posmap[old] - nb) // 2); n += 1
        elif run and w != 0: break
        q += 2
    return n, q


def fix_recs(L, L0, ta, te, base, posmap, lens, newbase=None, order='ao', run=False):
    """[값][오프셋](order='ao') 또는 [오프셋][값]('oa') 4바이트 기록 표. 값 윗바이트가 (글자 수−1)×8(가운데 맞춤)이면 새 길이로."""
    nb = base if newbase is None else newbase; n = 0; q = ta
    while q < te:
        x, y = struct.unpack_from('>HH', L0, q)
        at, w = (x, y) if order == 'ao' else (y, x)
        old = base + 2 * w
        if old not in posmap:
            if run: break
            q += 4; continue
        n0, n1 = lens[old]
        if n0 and at >> 8 == (n0 - 1) * 8: at = ((max(n1, 1) - 1) * 8 << 8) | (at & 0xFF)
        w2 = (posmap[old] - nb) // 2
        struct.pack_into('>HH', L, q, *((at, w2) if order == 'ao' else (w2, at))); n += 1; q += 4
    return n, q


def string_codes(L, a):
    v = []; i = a
    while True:
        c = struct.unpack_from('>H', L, i)[0]; v.append(c); i += 2
        if c == 0xFFF: return v


CHOICE_FIX = []


def build_ys1_text(L, trmap, amap):
    game = 'ys1'; inv = {v: k for k, v in ystext.charmap(game).items()}; m = ystext.charmap(game)
    L = bytearray(L)
    # ① 목록(실기 2026-10-03: 목록은 표가 줄마다 가리킨다 — 다시 깔고 표를 고친다)
    #   엔딩·저장 경고·오프닝 [0x79B1C,0x7A474) 기준 0x79B18: u16 표 0x7A474‥(엔딩) · u16 0x7A5E0(경고) · [오프셋][위치] 13칸 0x7A5E2(오프닝)
    #   시스템 [0x7B20A,0x7BBFE): u16 표 0x7D140‥0x7D200(아이템 이름 96) · [가운데 맞춤][오프셋] 0x7D2C8‥ · 0x7D3EE 1칸 (0x7D3F2·0x7D4CE·0x7D4D2 는 줄 «번호» 표 → 순서만 지키면 됨)
    L0 = bytes(L)
    out, pm, ln = relayout(L0, 0x79B1C, 0x7A474, trmap, game, amap, inv)
    L[0x79B1C:0x7A474] = fit_region(out, 0x79B1C, 0x7A474)
    n1, q = fix_u16(L, L0, 0x7A474, 0x7A52C, 0x79B18, pm, run=True); assert q <= 0x7A52C
    fix_u16(L, L0, 0x7A5E0, 0x7A5E2, 0x79B18, pm)
    n2, _ = fix_recs(L, L0, 0x7A5E2, 0x7A616, 0x79B18, pm, ln, order='oa'); assert n2 == 13, n2
    out, pm, ln = relayout(L0, 0x7B20A, 0x7BBFE, trmap, game, amap, inv)
    over = [(hex(k), x, y) for k, (x, y) in ln.items() if y > x]          # ★이름 칸은 원문 글자 수만큼만 그림(실기 2026-10-03)
    if over: raise SystemExit('⛔이스 I 시스템 목록이 원문 글자 수 초과 %d: %s' % (len(over), over[:5]))
    L[0x7B20A:0x7BBFE] = fit_region(out, 0x7B20A, 0x7BBFE)
    n3, _ = fix_u16(L, L0, 0x7D140, 0x7D200, 0x7B20A, pm); assert n3 == 96, n3
    n4, q = fix_recs(L, L0, 0x7D2C8, 0x7D3EE, 0x7B20A, pm, ln, run=True)
    n5, _ = fix_recs(L, L0, 0x7D3EE, 0x7D3F2, 0x7B20A, pm, ln); assert n5 == 1
    # 책 두 무리(히라가나판 0x7BBFE + 한자판 0x7C470) 합쳐 깔고: 한자판 기준 포인터 L 0x7D750 + 쪽 표 0x7D626(히라)·0x7D642(한자) 7칸씩
    A, M, E = 0x7BBFE, 0x7C470, 0x7CB20
    assert struct.unpack_from('>I', L0, 0x7D750)[0] == 0x200000 + M and struct.unpack_from('>I', L0, 0x7D758)[0] == 0x200000 + A
    out, pm, ln = relayout(L0, A, E, trmap, game, amap, inv, seps=(0xFFF,), join=False)
    L[A:E] = fit_region(out, A, E)
    NM = pm[M]; struct.pack_into('>I', L, 0x7D750, 0x200000 + NM)
    n6, _ = fix_recs(L, L0, 0x7D626, 0x7D642, A, pm, ln); n7, _ = fix_recs(L, L0, 0x7D642, 0x7D65E, M, pm, ln, newbase=NM)
    assert n6 == 7 and n7 == 7, (n6, n7)
    print('  이스 I 목록 표: 엔딩 %d · 오프닝 %d · 아이템 %d · 기록 %d · 책 %d+%d' % (n1, n2, n3, n4 + n5, n6, n7))
    # ② 묶음
    S, bl = model(game)
    blocks = bl[os.path.basename(YS1['file'])]
    strs = [s for s in S if s['kind'] != 'sys']
    v_all = u16s(bytes(L))
    plan = []        # (그룹표, [묶음 새 바이트…])
    newblk = {}
    for gi, (tab, _) in enumerate(YS1['groups']):
        gb = [b for b in blocks if (gi == 0 and b < YS1['groups'][0][0]) or (gi == 1 and YS1['groups'][0][0] < b < tab)]
        for k, B in enumerate(gb):
            E = gb[k + 1] if k + 1 < len(gb) else tab
            mine = sorted([s for s in strs if B <= s['a'] < E], key=lambda s: s['a'])
            T0 = mine[0]['a'] if mine else E
            # ★추출에서 빠진 문장(「・・・・」처럼 가나 없는 것)도 스크립트가 가리킨다 — 문장 구역을 FFF 로 전부 나눠 같이 옮긴다
            #   (안 하면 그 자리에 다른 문장이 깔려 엉뚱한 대사가 나온다: 실기 2026-10-03 술집 «무서워 관둔다» → 도니스 대사)
            known = {s['a'] for s in mine}; p = T0; vv = u16s(bytes(L[T0:E])); cur = []
            for c in vv:
                cur.append(c)
                if c == 0xFFF:
                    if p not in known:
                        if re.search('[ぁ-んァ-ヶ一-龥]', ystext.decode(cur[:-1], m)) and ystext.decode(cur[:-1], m) not in trmap:
                            print('  ⚠️이스 I 번역 없는 일본어 문장 0x%X: %s' % (p, ystext.decode(cur[:-1], m)[:30]))
                        mine.append(dict(no='?', file=os.path.basename(YS1['file']), a=p, e=p + 2 * len(cur),
                                         src=ystext.decode(cur[:-1], m), kind='extra', B=B, refs=[]))
                    p += 2 * len(cur); cur = []
            mine.sort(key=lambda s: s['a'])
            script = bytearray(L[B:T0])
            sv = u16s(bytes(script))
            # 참조 찾기(스크립트 부분, 명령 뒤 u16 = (문장−B)/2)
            refpos = collections.defaultdict(list)
            for s in mine:
                w = (s['a'] - B) // 2
                for i in range(1, len(sv)):
                    if sv[i] == w and sv[i - 1] in YS1['ops']:
                        refpos[s['a']].append(i)
            # 고정점(참조 없음) = 상대 위치 유지, 나머지는 빈 곳에 순서대로
            enc = {}
            for s in mine:
                tr = trmap.get(s['src'])
                enc[s['a']] = encode(game, tr, amap, inv) if tr is not None else string_codes(bytes(L), s['a'])
            area = [None] * ((E - T0) // 2)
            for s in mine:
                if not refpos[s['a']]:
                    o = (s['a'] - T0) // 2; c = enc[s['a']]; n_old = (s['e'] - s['a']) // 2
                    if len(c) > n_old:
                        raise SystemExit('⛔고정 문장 넘침 %s %d>%d' % (s['no'], len(c), n_old))
                    c = c[:-1] + [0xE08] * (n_old - len(c)) + [0xFFF]
                    area[o:o + n_old] = c
            pos = 0; newpos = {}
            for s in mine:
                if not refpos[s['a']]: continue
                c = enc[s['a']]
                while True:
                    if pos + len(c) > len(area):
                        area += [None] * (pos + len(c) - len(area))
                    if all(x is None for x in area[pos:pos + len(c)]): break
                    pos += 1
                area[pos:pos + len(c)] = c; newpos[s['a']] = pos; pos += len(c)
            for s in mine:
                if s['a'] in newpos:
                    w = (T0 - B) // 2 + newpos[s['a']]
                    for i in refpos[s['a']]: sv[i] = w
                # ★오리지널 모드 선택지(op 0x52): 인자 [문장][?][개수<<8|기본][선택지 줄 번호…] — 번역에서 줄 번호 다시 계산(커서 = 줄 번호×줄 간격)
                if 0x7D75C <= s['a'] < 0x84E9C and trmap.get(s['src']) is not None:
                    for i in refpos[s['a']]:
                        if sv[i - 1] != 0x52: continue
                        n = sv[i + 2] >> 8; old = sv[i + 3:i + 3 + n]
                        assert 1 <= n <= 5 and list(old) == sorted(old), (hex(s['a']), n, old)
                        lines = []; cur = []
                        for c in enc[s['a']][:-1]:
                            if c == 0xFFD: lines.append(cur); cur = []
                            else: cur.append(c)
                        lines.append(cur)
                        body = [[c for c in l if not (0xE00 <= c < 0x1000)] for l in lines]
                        spc = {0, amap.get(chr(PRIV + ord('　')))}          # 16px 빈칸(영문 줄 높이 맞춤)도 커서 자리 공백
                        cand = [k for k, l in enumerate(body) if len(l) >= 2 and l[0] in spc and l[1] not in spc]
                        if len(cand) < n: raise SystemExit('⛔오리지널 선택지 줄 부족 0x%X' % s['a'])
                        for k, ln in enumerate(cand[-n:]): sv[i + 3 + k] = ln
                        CHOICE_FIX.append((hex(s['a']), list(old), cand[-n:]))
            while area and area[-1] is None:            # 끝의 빈 칸은 잘라 묶음을 줄인다
                area.pop()
            area = [0xFFF if x is None else x for x in area]
            newblk[B] = pack16(sv) + pack16(area)
    return L, newblk, blocks


def layout_ys1(L, newblk, blocks):
    """묶음 무리를 다시 깔고 표 갱신. 넘치면 뒤 묶음을 다른 무리의 남는 끝으로 옮긴다"""
    L = bytearray(L)
    t1, t2 = YS1['groups'][0][0], YS1['groups'][1][0]
    g1 = [b for b in blocks if b < t1]; g2 = [b for b in blocks if t1 < b < t2]
    tabs = {t1: g1, t2: g2}
    newaddr = {}
    regions = {t1: [g1[0], t1], t2: [g2[0], t2]}
    moved = []
    # 무리 2 넘침 → 끝 묶음부터 무리 1 끝으로
    slack1 = t1 - g1[0] - sum(len(newblk[b]) for b in g1)
    while sum(len(newblk[b]) for b in g2) > t2 - g2[0]:
        over = sum(len(newblk[b]) for b in g2) - (t2 - g2[0])
        c = sorted([b for b in g2[1:] if len(newblk[b]) >= over and len(newblk[b]) <= slack1], key=lambda b: len(newblk[b]))
        if not c:
            c = sorted([b for b in g2[1:] if len(newblk[b]) <= slack1], key=lambda b: -len(newblk[b]))
        if not c:
            raise SystemExit('⛔옮길 묶음 없음(넘침 %d, 남는 곳 %d)' % (over, slack1))
        moved.append(c[0]); g2.remove(c[0]); slack1 -= len(newblk[c[0]])
    for tab, gb in ((t1, g1), (t2, g2)):
        p = regions[tab][0]
        for b in gb:
            L[p:p + len(newblk[b])] = newblk[b]; newaddr[b] = p; p += len(newblk[b])
        regions[tab].append(p)
    p = regions[t1][2]
    for b in moved:
        if p + len(newblk[b]) > t1:
            raise SystemExit('⛔무리 1 끝에도 자리 없음')
        L[p:p + len(newblk[b])] = newblk[b]; newaddr[b] = p; p += len(newblk[b])
    regions[t1][2] = p
    for tab in (t1, t2):
        a, e, used = regions[tab]
        L[used:e] = bytes(e - used)               # 남는 곳 0
    # 표 갱신
    for tab in (t1, t2):
        i = tab
        while True:
            q = struct.unpack_from('>I', L, i)[0]
            if not 0x200000 <= q < 0x300000: break
            old = q - 0x200000
            struct.pack_into('>I', L, i, newaddr[old] + 0x200000); i += 4
    return bytes(L), newaddr, moved


# ── 글꼴(2bpp 아틀라스, 값 1 글자 · 3 그림자 +1,+1) ───────────────────────────────
APOS = {'ys1': [(0x30, 0xE0, 0x8F5D4), (0xE0, 0xE0 + 524, 0x921D4)],
        'sun': [(0x30, 0xE0, 0x2BA50), (0xE0, 0xE0 + 419, 0x2D310)]}
GFONT = {'ys1': ('Galmuri14', 16), 'sun': ('Galmuri11', 12)}
SHADOW = {'ys1': True, 'sun': False}


def glyph_mask(ch, font, cell):
    from drs_gfx import line_mask
    if ch == "'":
        m = np.zeros((cell, cell), np.uint8); m[1:5, 6:8] = 1; return m
    if ord(ch) >= PRIV:
        c0 = chr(ord(ch) - PRIV)
        ch = '"' if c0 == '”' else chr(ord(c0) - 0xFEE0) if 0xFF01 <= ord(c0) <= 0xFF5E else c0
    g = line_mask(font, ch, space=0, gap=0)
    out = np.zeros((cell, cell), np.uint8)
    h, w = g.shape; y0 = max(0, (cell - 1 - h) // 2); x0 = max(0, (cell - 1 - w) // 2)
    out[y0:y0 + h, x0:x0 + w] = g[:cell - 1 - y0, :cell - 1 - x0]
    return out


def write_font(game, L, amap):
    L = bytearray(L); font, cell = GFONT[game]; bpr = cell * 16 // 4
    for ch, code in amap.items():
        for lo, hi, off in APOS[game]:
            if lo <= code < hi:
                idx = code - lo; break
        else:
            raise SystemExit('⛔칸 위치 모름 %X' % code)
        m = glyph_mask(ch, font, cell)
        g = np.zeros((cell, cell), np.uint8)
        sh = np.zeros_like(m); sh[1:, 1:] = m[:-1, :-1]
        if SHADOW[game]: g[(sh == 1) & (m == 0)] = 3
        g[m == 1] = 1
        r, c = divmod(idx, 16)
        for y in range(cell):
            base = off + (r * cell + y) * bpr + c * cell // 4
            row = 0
            for x in range(cell):
                row = (row << 2) | int(g[y, x])
            L[base:base + cell // 4] = row.to_bytes(cell // 4, 'big')
    return bytes(L)


# ── 이스 I 전체(빌드에서 부름) ─────────────────────────────────────────────────
YS1_ALLOWED = [(0xA0E80, 0xA0E82), (0xA0E89, 0xA0E8A), (0xA0E91, 0xA0E92), (0xA0E99, 0xA0E9A), (0x79B1C, 0x7CB20), (0x7D140, 0x7D200), (0x7D2C8, 0x7D3F2), (0x7D626, 0x7D65E), (0x7D750, 0x7D75C), (0x7D75C, 0x8E988), (0x8F5D4, 0x9A5D4)]


def ys1_house_chars(trmap, m):
    """오리지널 집 안 창(004C FF03 — 세트 3: 영문 10×12) 문장의 숫자·영문·부호(코드 0x00‥2F)를 «16px 전용 칸»(PRIV 글자)으로.
    세트 3 영문 칸은 상태창·인벤토리가 같이 써서 못 바꾼다(실기 2026-10-04) → 이 창 문장만 한글 아틀라스 빈칸의 16px 글자를 쓴다."""
    inv = {v: k for k, v in m.items()}
    win = ystrans.ys1_windows(); pos = {}
    for r in ystrans.load_rows('ys1'): pos.setdefault(r['src'], r['pos'])
    out = dict(trmap); n = 0
    for src, tr in trmap.items():
        w = win.get(pos.get(src, ''))
        if w is None or w >> 8 != 0xFF or (w & 0xFF) < 2: continue
        res = []; i = 0
        while i < len(tr):
            mm = re.match(r'\{FFB\}.|\{[0-9A-F]{3,4}\}|\\[np]', tr[i:])
            if mm: res.append(mm.group(0)); i += len(mm.group(0)); continue
            ch = tr[i]; i += 1
            c2 = FW.get(ch, ch)
            if 'A' <= c2 <= 'Z': c2 = chr(ord(c2) - 0x41 + 0xFF21)
            if 'a' <= c2 <= 'z': c2 = chr(ord(c2) - 0x61 + 0xFF41)
            # ★영문·숫자·－ 는 원래 작은 글꼴 그대로(조판 폭 W 도 0.7칸으로 잰다) — 16px 로 바꾸면 「SHORT-SWORD」가 9칸 창을 넘침(실기 2026-10-04)
            if ch not in ' 　' and c2 in inv and inv[c2] < 0x30 and not re.match(r'[Ａ-Ｚａ-ｚ０-９－]', c2):
                res.append(chr(PRIV + ord(c2))); n += 1
            else:
                res.append(ch)
        # ★16px 글자가 하나도 없는 줄(작은 영문뿐)은 줄 간격이 줄어 윗줄과 겹친다(실기 2026-10-04 「나간다」↔「SHORT-SWORD」)
        #   → 그 줄의 공백(커서 자리·들여쓰기)을 16px 빈칸(PRIV 공백)으로 바꿔 줄 높이를 맞춘다. 공백도 없으면 빌드 중단.
        lines = re.split(r'(\\[np])', ''.join(res))
        for k in range(0, len(lines), 2):
            body = re.sub(r'\{FFB\}.|\{[0-9A-F]{3,4}\}', '', lines[k])
            if not body or any('가' <= c <= '힣' or ord(c) >= PRIV for c in body): continue
            if not re.search(r'[A-Za-zＡ-Ｚａ-ｚ0-9０-９]', body): continue
            if '　' not in body and ' ' not in body:
                raise SystemExit('⛔이스 I 집 안 창: 16px 글자 없는 영문 줄에 공백이 없음 %r' % lines[k])
            lines[k] = re.sub(r'(\{FFB\}.|\{[0-9A-F]{3,4}\})|[ 　]', lambda mm: mm.group(1) or chr(PRIV + ord('　')), lines[k]); n += 1
        out[src] = ''.join(lines)
    print('  이스 I 집 안 창 16px 전용 글자 %d개 바꿈' % n)
    return out


def build_ys1(L0):
    """원본 L → 한글 L (문장·묶음·글꼴). 바뀐 바이트가 허용 범위 밖이면 중단"""
    trmap, probs = ystrans.translations('ys1')
    m = ystext.charmap('ys1')
    hira = ystext.decode(string_codes(L0, 0x7BBFE)[:-1], m)          # 히라가나판 「ハダル」(번역 TSV 에 빠짐)
    kanji = ystext.decode(string_codes(L0, 0x7C470)[:-1], m)
    if hira not in trmap and kanji in trmap:
        trmap[hira] = trmap[kanji]
    # ⛔ys1_house_chars(16px 전용 글자) 안 씀 — 집 안 창을 글꼴 세트 2 로 연다(아래 FF03→FF02)
    amap = alloc('ys1', trmap)
    L, nb, bl = build_ys1_text(L0, trmap, amap)
    L, na, moved = layout_ys1(L, nb, bl)
    L = write_font('ys1', L, amap)
    # ★오리지널 모드 = 글꼴 세트 2(표 X L 0xA0E70: 세트마다 [영문·가나·한자 글꼴 표 칸] 8B). 원래 [3,4,2] = 영문·가나 12×12 + 한자 16px
    #   → 한글은 음절 518개라 12px 가나 칸(160)에 못 넣음 → 세트 2 를 보통 모드와 같은 [0,1,2](16px)로 (실기 2026-10-03, 사용자 «16px»)
    L = bytearray(L); assert L[0xA0E80:0xA0E83] == bytes([3, 4, 2]); L[0xA0E80:0xA0E82] = bytes([5, 1])   # 영문 = 5번 12×16(리메이크 초상화 창과 같은 글꼴) — 0번(16×16)이면 SHORT-SWORD 가 창을 넘고(실기 2026-10-04), 12×12 면 줄 간격이 어긋남
    # ⛔세트 3·4·5 영문 칸(10×12·8×12·8×8)은 원래대로 — 보통 모드 상태창·인벤토리 이름표·세이브 정보가 이 작은 글꼴을 쓴다(16px 로 바꿨다가 겹침, 실기 2026-10-04)
    for q in (0xA0E89, 0xA0E91, 0xA0E99):            # 세트 3·4·5(오리지널 모드 집 안 창 등 — 실기 2026-10-03) 가나 10×12(7번) → 16px(1번)
        assert L[q] == 7; L[q] = 1
    # ★오리지널 집 안 창 = 스크립트 004C FF03(창 FF · 글꼴 세트 3). 세트 3 은 영문이 10×12 라 «줄 간격 14px»로 따로 놓여 한글(18px) 줄과 어긋난다
    #   (실기 2026-10-04: 「500 GOLD」가 윗줄에 그려짐·「SHORT-SWORD」가 「나간다」와 겹침) → 이 창만 세트 2([0,1,2] 전부 16px 높이)로 연다. 원본 9곳.
    vv = struct.unpack('>%dH' % (len(L) // 2), bytes(L)); nf = 0
    for i in range(0x7D75C // 2, 0x8E988 // 2 - 1):
        if vv[i] == 0x4C and vv[i + 1] == 0xFF03:
            struct.pack_into('>H', L, 2 * i + 2, 0xFF02); nf += 1
    if nf != 9: raise SystemExit('⛔이스 I 집 안 창 004C FF03 개수 %d ≠ 9' % nf)
    L = bytes(L)
    a = np.frombuffer(L0, np.uint8); b = np.frombuffer(L, np.uint8)
    diff = np.nonzero(a != b)[0]
    bad = [i for i in diff if not any(x <= i < y for x, y in YS1_ALLOWED)]
    if bad:
        raise SystemExit('⛔이스 I 허용 범위 밖 변경 0x%X' % bad[0])
    return L, dict(syllables=len(amap), moved=[hex(x) for x in moved], changed=len(diff))


# ── 아스테카 ──────────────────────────────────────────────────────────────────
# 묶음 12개(표 L 0x2AEA0, u32 절대) = [공통 100문장][2워드][3문장][스크립트][방 문장]. 참조 = op 43/56/6D 뒤 u16 = (문장−B)/2,
# 앞쪽(주소 증가)으로만 0x1FFFE B 까지. 같은 문장은 «뒤쪽 묶음에 둔 사본»을 공유해 공간을 번다(뒤 묶음부터 배치).
SUN = dict(file='fc2/SUN_0SUNL.BIN', ops={0x43, 0x56, 0x6D}, end=0x2A994, sys=(0x2A994, 0x2AE9E),
           sysptr=[0x2B238, 0x2B240, 0x2B248, 0x2B250, 0x2B258, 0x2B260, 0x758B4], subptr=[(0x758A8, 0x2ADF2)])
SUN_ALLOWED = [(0x5EA2, 0x2AE9E), (0x2AFF2, 0x2B232), (0x2B238, 0x2B264), (0x758A8, 0x758B8), (0x2B390, 0x2D310 + 0x6C0 * 40)]


def sys_codes(L, a, e, trmap, game, amap, inv):
    """FFD 로 나뉜 목록 → (번역 코드 목록, 원래 FFD 위치→새 위치 대응)"""
    v = u16s(L[a:e]); m = ystext.charmap(game); out = []; cur = []; posmap = {}
    i0 = 0
    for k, c in enumerate(v):
        cur.append(c)
        if c in (0xFFD, 0xFFF):
            src = ystext.decode(cur[:-1], m); tr = trmap.get(src)
            body = encode(game, tr, amap, inv)[:-1] if tr is not None else cur[:-1]
            out += body; posmap[a + 2 * k] = len(out); out.append(c); cur = []
    out += cur
    return out, posmap


def counted_run(v, B, lim):
    """묶음 시작부터 FFF 로 끝나는 문장이 이어지는 구간(엔진이 개수로 세어 찾는 앞 구역) → [(시작, 끝)]"""
    i = B // 2; out = []
    while True:
        j = i
        while v[j] != 0xFFF and (v[j] < lim or 0xE00 <= v[j] <= 0xFFE): j += 1
        if v[j] != 0xFFF: return out
        out.append((i * 2, (j + 1) * 2)); i = j + 1


def build_sun_text(L0, trmap, amap):
    """참조된 문장 + 바로 뒤에 붙은 참조 없는 문장들 = 한 사슬(엔진이 «다음 문장»으로 넘어감) → 사슬째 옮긴다.
    앞 구역(개수로 세는 104문장)은 내용·순서 그대로 두되, 참조된 사슬은 따로 복사본을 둔다(앞 구역 자리는 비우지 않음).
    방 구역 사슬은 빈 곳 아무 데나(같은 사슬은 닿는 범위 안이면 공유), 앞에 참조 없는 고아 문장은 제자리."""
    game = 'sun'; inv = {v: k for k, v in ystext.charmap(game).items()}; m = ystext.charmap(game); lim = ystext.limit(game)
    L = bytearray(L0)
    S, bl = model(game)
    banks = sorted(bl['SUN_0SUNL.BIN']); ends = banks[1:] + [SUN['end']]
    v = u16s(bytes(L)); newv = list(v)
    def enc(codes):
        src = ystext.decode(codes[:-1], m)
        return tuple(encode(game, trmap[src], amap, inv)) if src in trmap else tuple(codes)
    info = []
    for B, E in zip(banks, ends):
        run = counted_run(v, B, lim); T1 = run[-1][1]
        rooms = sorted([s for s in S if s['file'] == 'SUN_0SUNL.BIN' and s['kind'] != 'sys' and T1 <= s['a'] < E], key=lambda s: s['a'])
        items = list(run) + [(s['a'], s['e']) for s in rooms]
        span = set(range(B // 2, T1 // 2))
        for s in rooms: span.update(range(s['a'] // 2, s['e'] // 2))
        refs = collections.defaultdict(list)
        targets = {(x - B) // 2: x for x, y in items}
        for i in range(B // 2 + 1, E // 2):
            if i in span or (i - 1) in span: continue
            if v[i - 1] in SUN['ops'] and v[i] in targets:
                refs[targets[v[i]]].append(i)
        # 사슬 만들기
        chains = []; orphans = []; cur = None
        for x, y in items:
            if refs[x]:
                cur = [(x, y)]; chains.append(cur)
            elif cur is not None and cur[-1][1] == x:
                cur.append((x, y))
            else:
                cur = None
                if x >= T1: orphans.append((x, y))
        info.append(dict(B=B, E=E, run=run, T1=T1, rooms=rooms, refs=refs, chains=chains, orphans=orphans))
    free = {}
    stat = collections.Counter()
    for bk in info:
        p = bk['B'] // 2
        for x, y in bk['run']:                                     # 앞 구역: 개수는 지키고, 참조된 문장은 빈 문장(사슬 사본이 따로 감)
            c = (0xFFF,) if bk['refs'][x] else enc(v[x // 2:y // 2]); newv[p:p + len(c)] = list(c); p += len(c)
        for i in range(p, bk['T1'] // 2): free[i] = True
        if p > bk['T1'] // 2: raise SystemExit('⛔앞 구역 넘침 0x%X' % bk['B'])
        stat['run_free'] += bk['T1'] // 2 - p
        for s in bk['rooms']:
            for i in range(s['a'] // 2, s['e'] // 2): free[i] = True
        for x, y in bk['orphans']:
            c = list(enc(v[x // 2:y // 2])); n_old = (y - x) // 2
            if len(c) > n_old:
                print('⛔고아 넘침', hex(x), len(c), n_old, ystext.decode(v[x // 2:y // 2 - 1], m)); continue
            c = c[:-1] + [0xE08] * (n_old - len(c)) + [0xFFF]
            newv[x // 2:y // 2] = c
            for i in range(x // 2, y // 2): free[i] = False
            stat['orphan'] += 1
    sa, se = SUN['sys']
    for i in range(sa // 2, se // 2): free[i] = True
    def place(c, lo, hi):
        run = 0; start = None
        for i in range(lo, hi):
            if free.get(i):
                if run == 0: start = i
                run += 1
                if run == len(c):
                    for k in range(len(c)): newv[start + k] = c[k]; free[start + k] = False
                    return start
            else:
                run = 0
        return None
    copies = {}
    for bk in reversed(info):
        B = bk['B']
        for ch in sorted(bk['chains'], key=lambda ch: -sum(y - x for x, y in ch)):
            c = tuple(w for x, y in ch for w in enc(v[x // 2:y // 2]))
            lo, hi = B // 2, (B + 0x1FFFE) // 2
            pos = next((q for q in copies.get(c, []) if lo <= q <= hi), None)
            if pos is None:
                pos = place(c, B // 2, bk['E'] // 2)
                if pos is None: pos = place(c, bk['E'] // 2, min(hi, se // 2))
                if pos is None: raise SystemExit('⛔아스테카 자리 없음 0x%X (묶음 0x%X, %d 단어)' % (ch[0][0], B, len(c)))
                copies.setdefault(c, []).append(pos); stat['new'] += 1
            else:
                stat['shared'] += 1
            for i in bk['refs'][ch[0][0]]:
                newv[i] = pos - B // 2
            stat['chained'] += len(ch) - 1
    sysv, pm, ln = relayout(bytes(L0), sa, se, trmap, game, amap, inv)
    over = [(hex(k), a, b) for k, (a, b) in ln.items() if b > a]      # ★라벨 칸은 원문 글자 수만큼만 그림(실기 2026-10-03 방향 겹침)
    if over: raise SystemExit('⛔아스테카 시스템 목록이 원문 글자 수 초과 %d: %s' % (len(over), over[:5]))
    pos = place(sysv, 0x5EA2 // 2, se // 2)
    if pos is None: raise SystemExit('⛔시스템 목록 둘 곳 없음(%d 단어)' % len(sysv))
    stat['sys_at'] = hex(pos * 2)
    for i, f in free.items():
        if f: newv[i] = 0xFFF
    stat['free_left'] = sum(1 for f in free.values() if f)
    L = bytearray(pack16(newv)) + L[len(newv) * 2:]
    for q in SUN['sysptr']:
        assert struct.unpack_from('>I', L0, q)[0] == 0x200000 + sa
        struct.pack_into('>I', L, q, 0x200000 + pos * 2)
    for q, old in SUN['subptr']:                    # 줄 앞 FFD 를 가리킴 → 새 다음 줄 시작 −2
        assert struct.unpack_from('>I', L0, q)[0] == 0x200000 + old
        struct.pack_into('>I', L, q, 0x200000 + pos * 2 + (pm[old + 2] - sa) - 2)
    # ★[가운데 맞춤][오프셋] 기록 표 144칸 L 0x2AFF2‥0x2B232(지명·명령·아이템·조사 대상 — 실기 «녀원»·«기다» 원인)
    pm2 = {k: pos * 2 + (v - sa) for k, v in pm.items()}
    n, q = fix_recs(L, L0, 0x2AFF2, 0x2B232, sa, pm2, ln, newbase=pos * 2)
    if n != 144: raise SystemExit('⛔아스테카 기록 표 %d/144' % n)
    stat['recs'] = n
    return bytes(L), stat


def build_sun(L0):
    trmap, probs = ystrans.translations('sun')
    amap = alloc('sun', trmap)
    L, stat = build_sun_text(L0, trmap, amap)
    L = write_font('sun', L, amap)
    a = np.frombuffer(L0, np.uint8); b = np.frombuffer(L, np.uint8)
    diff = np.nonzero(a != b)[0]
    bad = [i for i in diff if not any(x <= i < y for x, y in SUN_ALLOWED)]
    if bad:
        raise SystemExit('⛔아스테카 허용 범위 밖 변경 0x%X' % bad[0])
    return L, dict(syllables=len(amap), placed=dict(stat), changed=len(diff))


# ── 이스 II (2026-10-03) ────────────────────────────────────────────────────────
# 글자: 보통 벌(L 가나 0x2E208 · 한자 0x30E08, 634) + 굵은 둘째 벌(마물 모습 대사, 가나 0x3B208 · 한자 0x3DE08, 384).
#   굵은 벌·한자 없는(어느 벌인지 모르는) 문자열이 쓰는 음절은 코드 < 0x260 에 몰아 두 아틀라스에 같이 그린다.
# 공백: E10·E08 = «멈춤»(줄 머리 E10 이 화면에서 들여쓰기 안 됨, 스샷 이스2/1) → 공백 = 0x000(16px), 남는 칸 메우기 = E08.
# 배치:
#   ① DAT01‥04 묶음 [스크립트][문장들] — 묶음마다 문장을 원래 순서대로 다시 깔고 op 4E/4F/50 피연산자(= (문장−묶음)/2) 고침.
#      묶음 시작은 그대로(넘치면 뒤 묶음을 밀고 L 0x46BF0 맵 표 갱신). DAT 전체 구역(첫 묶음‥마지막 문장 끝) 안에서만.
#   ② L 아이템 설명·책·NPC 문장 0x29946‥0x2C126 = u16 표 L 0x2C75E‥0x2C838 (값 = (주소−0x29946)/2, 줄 머리 가리키는 칸 포함) → 다시 깔고 표 고침.
#   ③ L 시스템 목록 0x45BE2‥0x467DC(FFD 줄) = u16 표 0x467E4‥0x46888 + [가운데 맞춤 u16][u16] 표 0x46918‥0x46A5A
#      (가운데 맞춤 윗바이트 = (글자 수−1)×8 — 원래 그 꼴인 칸만 새 길이로) → 다시 깔고 두 표 고침.
#   ④ 음악 곡명 0x290F0‥0x2944C(끝 포인터 L 0x2F30) = 순서 영역, 남는 칸은 마지막 줄에 E08.
#   ⑤ 그 밖(메뉴 0x297BA 등) = 제자리(원래 길이 안, E08 채움).
YS2_OPS = {0x4E, 0x4F, 0x50}
YS2_DATS = ['DAT01.BIN', 'DAT02.BIN', 'DAT03.BIN', 'DAT04.BIN']
YS2_MAPTAB = (0x46BF0, 65)
YS2_ITEM = (0x29946, 0x2C126, 0x2C75E, 0x2C838)          # 문장 구역 시작·끝, u16 표 시작·끝
YS2_SYS = (0x45BE2, 0x467DC, (0x467E4, 0x46888), (0x46918, 0x46A58))
YS2_MUSIC = (0x290F0, 0x2944C)
YS2_BOLDLIM = 0xE0 + 384
YS2_MIDREFS = {('DAT01.BIN', 0x9002), ('DAT03.BIN', 0x9E9C)}
APOS['ys2'] = [(0x30, 0xE0, 0x2E208), (0xE0, 0xE0 + 634, 0x30E08)]
APOS['ys2b'] = [(0x30, 0xE0, 0x3B208), (0xE0, YS2_BOLDLIM, 0x3DE08)]
GFONT['ys2'] = GFONT['ys2b'] = ('Galmuri14', 16)
SHADOW['ys2'] = SHADOW['ys2b'] = True
YS2_L_ALLOWED = [(0x290F0, 0x2944C), (0x297BA, 0x297EC), (0x29946, 0x2C126), (0x2C75E, 0x2C838),
                 (0x2E208, 0x30E08 + 40 * 1024), (0x3B208, 0x3DE08 + 24 * 1024),
                 (0x45BE2, 0x467DC), (0x467E4, 0x46888), (0x46918, 0x46A58), (0x46BF0, 0x46BF0 + 130)]


def ys2_rows():
    """work/text/ys2.tsv → {(파일, 시작): (번호, 끝, 원문)} · 벌 판정 {번호: N/B/-}"""
    import ys2bold
    rows = [l.rstrip('\n').split('\t') for l in open(os.path.join(ROOT, 'work', 'text', 'ys2.tsv'), encoding='utf-8')][1:]
    return {(r[1], int(r[2], 16)): (r[0], int(r[3], 16), r[4]) for r in rows}, ys2bold.fontset()


def encode_ys2(s, amap, bold, rawargs=()):
    """이스 II 인코딩. bold = 굵은 벌 문자열(부호 코드가 다름). rawargs = 원문 {FFB} 인자 코드(차례대로)"""
    m = ystext.charmap('ys2b' if bold else 'ys2'); inv = {}
    for k, v in sorted(m.items(), reverse=True): inv[v] = k        # 같은 글자 여러 코드면 작은 코드
    args = list(rawargs); out = []; i = 0
    mN = ystext.charmap('ys2'); argmap = {mN.get(c, ''): c for c in rawargs}     # 쪽 나눌 때 되풀이한 {FFB}x → 원문 인자 코드
    while i < len(s):
        mm = re.match(r'\{([0-9A-F]{3,4})\}', s[i:])
        if mm:
            c = int(mm.group(1), 16); out.append(c); i += len(mm.group(0))
            if c in ARG_CMDS:
                out.append(argmap[s[i]] if s[i] in argmap else (args[0] if args else inv[s[i]])); i += 1
            continue
        if s.startswith(NL, i): out.append(0xFFD); i += 2; continue
        if s.startswith(PG, i): out.append(0xFFE); i += 2; continue
        ch = s[i]; i += 1
        if ch in amap: out.append(amap[ch]); continue
        if ch in ' 　': out.append(0x000); continue
        ch = {'―': 'ー', '—': 'ー', '~': '～', '〜': '～', '·': '・', '"': '”', '“': '”'}.get(ch, ch)
        if bold:
            ch = {'!': '！', '?': '？', '.': '。', '．': '。', ',': '，', '〓': '？', '㈱': '！'}.get(ch, ch)   # 〓㈱ = 보통 벌로 읽은 DB/DC
        ch2 = FW.get(ch, ch)
        if 'A' <= ch2 <= 'Z': ch2 = chr(ord(ch2) - 0x41 + 0xFF21)
        if 'a' <= ch2 <= 'z': ch2 = chr(ord(ch2) - 0x61 + 0xFF41)
        if ch2 in inv and (inv[ch2] < 0x30 or 0xD0 <= inv[ch2] < 0xE0):
            out.append(inv[ch2]); continue
        raise SystemExit('⛔이스 II 인코딩 못 하는 글자 %r (굵은 벌 %s) in %r' % (ch, bold, s[:40]))
    return out + [0xFFF]


def ys2_items(L0, D0, trmap, rowmap, fs):
    """번역 대상 문자열 전부 → [(구역, 파일, 시작, 끝, 원문코드, 번역, 굵은벌?, 한자없음?)]"""
    m = ystext.charmap('ys2'); out = []
    def add(kind, f, a, cs):
        src = ystext.decode(cs[:-1], m)
        r = rowmap.get((f, a)); k = fs.get(r[0], 'N') if r else ('B' if any(c in (0xDB, 0xDC) for c in cs) else '-')   # 추출에서 빠진 문장: ？！(DB/DC)면 굵은 벌, 아니면 두 벌 다
        out.append(dict(kind=kind, file=f, a=a, e=a + 2 * len(cs), raw=cs, src=src, tr=trmap.get(src), bold=(k == 'B'), both=(k in ('B', '-'))))
    def fff_split(d, a, e):
        v = u16s(d[a:e]); cur = []; p = a; res = []
        for c in v:
            cur.append(c)
            if c == 0xFFF: res.append((p, cur)); p += 2 * len(cur); cur = []
        assert not cur, '구역 끝이 FFF 아님 0x%X' % e
        return res
    # DAT 묶음
    blocks = {os.path.basename(f): b for f, b in ysrefs.blocks('ys2').items()}
    areas = {}
    for f in YS2_DATS:
        d = D0[f]; bs = blocks[f]; fa = sorted(a for (ff, a) in rowmap if ff == f)
        last = [a for a in fa if a > bs[-1]]; E = bs[-1]
        for a in last:
            if E == bs[-1] or a - E < 0x400: E = max(E, rowmap[(f, a)][1])
        ends = bs[1:] + [E]; areas[f] = []
        for B, E in zip(bs, ends):
            T0 = min(a for a in fa if B < a < E)
            areas[f].append((B, T0, E))
            for a, cs in fff_split(d, T0, E): add('dat', f, a, cs)
    # L 표 구역
    base, end, _, _ = YS2_ITEM
    for a, cs in fff_split(L0, base, end): add('item', 'YS2_0YS2L.BIN', a, cs)
    # 시스템 목록 = FFD 줄
    a0, e0 = YS2_SYS[0], YS2_SYS[1]; v = u16s(L0[a0:e0]); cur = []; p = a0
    for c in v:
        cur.append(c)
        if c in (0xFFD, 0xFFF):
            src = ystext.decode(cur[:-1], m)
            out.append(dict(kind='sys', file='YS2_0YS2L.BIN', a=p, e=p + 2 * len(cur), raw=cur, src=src, tr=trmap.get(src), bold=False, both=False))
            p += 2 * len(cur); cur = []
    # 음악·메뉴·그 밖(제자리)
    a0, e0 = YS2_MUSIC; v = u16s(L0[a0:e0]); cur = []; p = a0
    for c in v:
        cur.append(c)
        if c in (0xFFD, 0xFFF):
            src = ystext.decode(cur[:-1], m)
            out.append(dict(kind='music', file='YS2_0YS2L.BIN', a=p, e=p + 2 * len(cur), raw=cur, src=src, tr=trmap.get(src), bold=False, both=False))
            p += 2 * len(cur); cur = []
    done = {(x['file'], x['a']) for x in out}
    for (f, a), (no, e, src) in rowmap.items():
        if (f, a) in done or no[3] == 's' or src not in trmap: continue
        if f == 'YS2_0YS2L.BIN':
            if any(x <= a < y for x, y in (YS2_ITEM[:2], YS2_SYS[:2], YS2_MUSIC)): continue
            d = L0
        else:
            if any(B <= a < E for B, T0, E in areas[f]): continue
            d = D0[f]
        cs = string_codes(d, a)
        add('fixed', f, a, cs)
    return out, areas


def ys2_alloc(items):
    syl = collections.Counter(); con = set()
    for it in items:
        if it['tr'] is None: continue
        for ch in re.sub(r'\{FFB\}.', '', re.sub(r'\{[0-9A-F]+\}', lambda x: x.group(0) if x.group(0) == '{FFB}' else '', it['tr'])):
            if '가' <= ch <= '힣' or ch in SPECIAL:
                syl[ch] += 1
                if it['both']: con.add(ch)
    sl = list(range(0x30, 0xD0)) + list(range(0xE0, ystext.limit('ys2')))
    order = sorted(con, key=lambda c: (-syl[c], c)) + sorted(set(syl) - con, key=lambda c: (-syl[c], c))
    if len(order) > len(sl): raise SystemExit('⛔이스 II 글자 칸 부족: 필요 %d · 칸 %d' % (len(order), len(sl)))
    amap = {ch: sl[i] for i, ch in enumerate(order)}
    over = [c for c in con if amap[c] >= YS2_BOLDLIM]
    if over: raise SystemExit('⛔굵은 벌 칸 부족: 두 벌 음절 %d > %d' % (len(con), 160 + 384))
    return amap, len(con)


def ys2_enc(it, amap):
    """번역 있으면 인코딩(원문 {FFB} 인자 그대로), 없으면 원문 코드"""
    if it['tr'] is None: return list(it['raw'])
    rawargs = [it['raw'][k + 1] for k in range(len(it['raw']) - 1) if it['raw'][k] == 0xFFB]
    return encode_ys2(it['tr'], amap, it['bold'], rawargs)


def build_ys2_text(L0, D0, trmap, amap, items, areas):
    L = bytearray(L0); D = {f: bytearray(b) for f, b in D0.items()}; stat = collections.Counter()
    enc = {(it['file'], it['a']): ys2_enc(it, amap) for it in items}
    # ① DAT 묶음
    R = collections.defaultdict(list)
    for f, B, p, op, S in ysrefs.refs('ys2'):
        R[(os.path.basename(f), B)].append((p, S))
    moved = {}
    for f in YS2_DATS:
        d = D[f]; mine = sorted([it for it in items if it['file'] == f and it['kind'] == 'dat'], key=lambda x: x['a'])
        blk = []
        for B, T0, E in areas[f]:
            ss = [it for it in mine if T0 <= it['a'] < E]
            refset = {S for p, S in R[(f, B)]}
            newpos = {}; body = []; seen = {}
            for k, it in enumerate(ss):
                c = tuple(enc[(f, it['a'])])
                nxt = ss[k + 1]['a'] if k + 1 < len(ss) else None
                if c in seen and it['a'] in refset and (nxt is None or nxt in refset):
                    newpos[it['a']] = seen[c]; stat['shared'] += 1; continue      # 같은 문장 자리 공유(뒤로 이어지는 사슬 아님)
                newpos[it['a']] = T0 + 2 * len(body); seen.setdefault(c, newpos[it['a']]); body += list(c)
            blk.append([B, T0, E, ss, newpos, body])
        # 넘치면 뒤 묶음을 민다(맵 표 갱신)
        A0, AE = areas[f][0][0], areas[f][-1][2]
        if all(T0 + 2 * len(body) <= E for B, T0, E, ss, np_, body in blk):
            shift = {B: B for B, *_ in blk}
        else:
            need = sum((T0 - B) + 2 * len(body) for B, T0, E, ss, np_, body in blk)
            if A0 + need > AE: raise SystemExit('⛔%s 묶음 구역 넘침 %d > %d' % (f, need, AE - A0))
            shift = {}; p = A0
            for b in blk:
                shift[b[0]] = p; p += (b[1] - b[0]) + 2 * len(b[5])
            stat['dat_shift_' + f] = sum(1 for B in shift if shift[B] != B)
        new = bytearray(d)
        script_all = {}
        for B, T0, E, ss, newpos, body in blk:
            NB = shift[B]; sc = bytearray(d[B:T0])
            for p, S in R[(f, B)]:
                if S in newpos:
                    w = (newpos[S] - T0 + (T0 - B)) // 2
                    struct.pack_into('>H', sc, p - B, w); stat['refs'] += 1
                elif T0 <= S < E and (f, S) in YS2_MIDREFS:
                    stat['midref_kept'] += 1               # 문장 가운데 = 우연 일치(work/text/ys2_midrefs.tsv) — 손대지 않음
                elif T0 <= S < E:
                    raise SystemExit('⛔%s 참조가 문장 시작 아님 0x%X' % (f, S))
            script_all[NB] = bytes(sc) + pack16(body)
        cur = A0
        for NB in sorted(script_all):
            new[NB:NB + len(script_all[NB])] = script_all[NB]; cur = NB + len(script_all[NB])
        # 남는 곳 = FFF
        used = set()
        for NB, b in script_all.items(): used.update(range(NB, NB + len(b)))
        for i in range(A0, AE, 2):
            if i not in used: struct.pack_into('>H', new, i, 0xFFF)
        D[f] = new
        for B in shift:
            if shift[B] != B: moved[(f, B)] = shift[B]
    if moved:
        tab, n = YS2_MAPTAB; owner = {}
        for f in YS2_DATS:
            for B, T0, E in areas[f]: owner[B] = f
        for k in range(n):
            q = tab + 2 * k; B = struct.unpack_from('>H', L, q)[0]
            if (owner.get(B), B) in moved: struct.pack_into('>H', L, q, moved[(owner[B], B)])
    # ② L 아이템 설명 구역 + u16 표
    base, end, tab, tabend = YS2_ITEM
    its = sorted([it for it in items if it['kind'] == 'item'], key=lambda x: x['a'])
    rowmapno = {a: no for (f, a), (no, e, src) in ys2_rows()[0].items() if f == 'YS2_0YS2L.BIN'}
    posmap = {}; body = []; seen = {}
    for it in its:
        c = enc[('YS2_0YS2L.BIN', it['a'])]
        ol = [k for k, x in enumerate(it['raw']) if x == 0xFFD]; nl = [k for k, x in enumerate(c) if x == 0xFFD]
        if tuple(c) in seen and it['a'] != base:                  # 표로만 찾는 문장 → 같은 문장은 자리 공유
            s0 = seen[tuple(c)]; posmap[it['a']] = s0
            for j, k in enumerate(ol):
                if j < len(nl): posmap[it['a'] + 2 * (k + 1)] = s0 + 2 * (nl[j] + 1)
            stat['item_shared'] += 1; continue
        seen[tuple(c)] = base + 2 * len(body)
        posmap[it['a']] = base + 2 * len(body)
        for j, k in enumerate(ol):                                # 줄 머리(표가 줄을 가리킴: 순간 이동 목록)
            if j < len(nl): posmap[it['a'] + 2 * (k + 1)] = base + 2 * (len(body) + nl[j] + 1)
        body += c
    if base + 2 * len(body) > end:
        over = sorted(its, key=lambda it: len(it['raw']) - len(enc[('YS2_0YS2L.BIN', it['a'])]))[:15]
        for it in over: print('   +%d' % (len(enc[('YS2_0YS2L.BIN', it['a'])]) - len(it['raw'])), rowmapno.get(it['a'], '?'), (it['tr'] or '')[:50])
        raise SystemExit('⛔아이템 설명 구역 넘침 %d > %d' % (2 * len(body), end - base))
    stat['item_free'] = end - base - 2 * len(body)
    L[base:end] = pack16(body + [0xFFF] * ((end - base) // 2 - len(body)))
    for q in range(tab, tabend, 2):
        w = struct.unpack_from('>H', L0, q)[0]; a = base + 2 * w
        if a not in posmap: raise SystemExit('⛔아이템 표 0x%X 가 문장/줄 머리 아님 0x%X' % (q, a))
        struct.pack_into('>H', L, q, (posmap[a] - base) // 2)
    # ③ 시스템 목록
    a0, e0, (t1a, t1e), (t2a, t2e) = YS2_SYS
    ss = sorted([it for it in items if it['kind'] == 'sys'], key=lambda x: x['a'])
    posmap = {}; glyphs = {}; body = []
    for it in ss:
        c = enc[('YS2_0YS2L.BIN', it['a'])][:-1]
        if 0xFFD in c or 0xFFE in c: raise SystemExit('⛔시스템 목록 번역에 줄바꿈: %s' % it['tr'])
        posmap[it['a']] = a0 + 2 * len(body)
        glyphs[it['a']] = (sum(1 for x in it['raw'][:-1] if x < 0xE00), sum(1 for x in c if x < 0xE00))
        if glyphs[it['a']][1] > glyphs[it['a']][0]: raise SystemExit('⛔이스 II 시스템 목록이 원문 글자 수 초과: %s → %s' % (it['src'], it['tr']))
        body += c + [it['raw'][-1]]
    if a0 + 2 * len(body) > e0: raise SystemExit('⛔시스템 목록 넘침 %d > %d' % (2 * len(body), e0 - a0))
    stat['sys_free'] = e0 - a0 - 2 * len(body)
    pad = (e0 - a0) // 2 - len(body)
    body = body + [0xFFF] * pad                             # 표가 줄마다 가리킴 → 남는 칸은 끝줄 뒤
    L[a0:e0] = pack16(body)
    for q in range(t1a, t1e, 2):
        w = struct.unpack_from('>H', L0, q)[0]; struct.pack_into('>H', L, q, (posmap[a0 + 2 * w] - a0) // 2)
    for q in range(t2a, t2e, 4):
        at, w = struct.unpack_from('>HH', L0, q); a = a0 + 2 * w
        n0, n1 = glyphs[a]
        if at >> 8 == (n0 - 1) * 8: at = (((n1 - 1) * 8) << 8) | (at & 0xFF); stat['centered'] += 1
        struct.pack_into('>HH', L, q, at, (posmap[a] - a0) // 2)
    # ④ 음악 곡명(순서 영역)
    a0, e0 = YS2_MUSIC
    ms = sorted([it for it in items if it['kind'] == 'music'], key=lambda x: x['a'])
    body = []
    for it in ms: body += enc[('YS2_0YS2L.BIN', it['a'])][:-1] + [it['raw'][-1]]
    if a0 + 2 * len(body) > e0: raise SystemExit('⛔음악 목록 넘침')
    body = body[:-1] + [0x000] * ((e0 - a0) // 2 - len(body)) + body[-1:]   # 끝 포인터까지 읽는 목록 → 끝줄 뒤 공백(E08 은 글자로 그려질 수 있음)
    L[a0:e0] = pack16(body)
    # ⑤ 제자리
    for it in items:
        if it['kind'] != 'fixed': continue
        c = enc[(it['file'], it['a'])]; n = len(it['raw'])
        if len(c) > n: raise SystemExit('⛔제자리 문장 넘침 %s 0x%X %d>%d %s' % (it['file'], it['a'], len(c), n, it['tr']))
        c = c[:-1] + [0xE08] * (n - len(c)) + [0xFFF]
        tgt = L if it['file'] == 'YS2_0YS2L.BIN' else D[it['file']]
        tgt[it['a']:it['a'] + 2 * n] = pack16(c); stat['fixed'] += 1
    return bytes(L), {f: bytes(b) for f, b in D.items()}, stat, moved


def build_ys2(L0, D0):
    """원본 L + DAT01‥04 → 한글판. 검산: 참조 전수(새 위치 문장 = 번역 인코딩), 허용 범위 밖 변경 0"""
    trmap, probs = ystrans.translations('ys2')
    if probs: raise SystemExit('⛔이스 II 번역 문제 %d: %s' % (len(probs), probs[:3]))
    rowmap, fs = ys2_rows()
    items, areas = ys2_items(L0, D0, trmap, rowmap, fs)
    amap, ncon = ys2_alloc(items)
    L, D, stat, moved = build_ys2_text(L0, D0, trmap, amap, items, areas)
    L = write_font('ys2', L, amap)
    L = write_font('ys2b', L, {ch: c for ch, c in amap.items() if c < YS2_BOLDLIM})
    # 검산 ① 참조: 새 피연산자가 가리키는 문장 = 그 문장 번역 인코딩
    enc = {(it['file'], it['a']): ys2_enc(it, amap) for it in items}
    bad = 0; n = 0
    for f, B, p, op, S in ysrefs.refs('ys2'):
        f = os.path.basename(f)
        if (f, S) not in enc: continue
        NB = moved.get((f, B), B); w = struct.unpack_from('>H', D[f], NB + (p - B))[0]
        got = string_codes(D[f], NB + 2 * w); n += 1
        if got != enc[(f, S)]: bad += 1
    if bad: raise SystemExit('⛔참조 검산 틀림 %d/%d' % (bad, n))
    # 검산 ② 아이템 표
    base, end, tab, tabend = YS2_ITEM
    for q in range(tab, tabend, 2):
        a = base + 2 * struct.unpack_from('>H', L, q)[0]; assert a < end
    # 검산 ③ 허용 범위
    a = np.frombuffer(L0, np.uint8); b = np.frombuffer(L, np.uint8); diff = np.nonzero(a != b)[0]
    badL = [i for i in diff if not any(x <= i < y for x, y in YS2_L_ALLOWED)]
    if badL: raise SystemExit('⛔이스 II L 허용 범위 밖 변경 0x%X' % badL[0])
    for f in YS2_DATS:
        A0, AE = areas[f][0][0], areas[f][-1][2]
        x = np.frombuffer(D0[f], np.uint8); y = np.frombuffer(D[f], np.uint8); df = np.nonzero(x != y)[0]
        fixed = [(it['a'], it['e']) for it in items if it['file'] == f and it['kind'] == 'fixed']
        bd = [i for i in df if not (A0 <= i < AE or any(p <= i < q for p, q in fixed))]
        if bd: raise SystemExit('⛔%s 허용 범위 밖 변경 0x%X' % (f, bd[0]))
    ntr = sum(1 for it in items if it['tr'] is not None)
    jp = [(it['file'], hex(it['a']), it['src'][:20]) for it in items if it['tr'] is None and re.search('[ぁ-んァ-ヶ一-龥]', it['src'])]
    if jp: print('  ⚠️이스 II 번역 없는 일본어 문장 %d(가나·한자 칸은 한글이라 깨져 보임): %s' % (len(jp), jp[:8]))
    return L, D, dict(syllables=len(amap), both=ncon, strings=len(items), translated=ntr, refs_checked=n, moved=len(moved), **stat)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    g, cmd = sys.argv[1], sys.argv[2]
    if cmd == 'budget': budget(g)
    if g == 'ys2' and cmd == 'dry':
        L0 = open(os.path.join(ystext.DISC, 'fc2', 'YS2_0YS2L.BIN'), 'rb').read()
        D0 = {f: open(os.path.join(ystext.DISC, 'fc2', 'ys2', f), 'rb').read() for f in YS2_DATS}
        L, D, st = build_ys2(L0, D0); print(st)
