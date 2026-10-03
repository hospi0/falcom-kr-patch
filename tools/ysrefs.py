# -*- coding: utf-8 -*-
r"""대사 «참조» 조사 — 스크립트 묶음 안의 문장 참조 명령(op, 워드 오프셋)을 모은다 (2026-10-03)

세 게임 공통 방식: 문장 주소 = 묶음 시작 + 2 × (op 뒤 u16).
  이스 I   : 묶음 표 u32 절대(L 0x84E9C · 0x8E8F4), op 0050/0051/0052
  이스 II  : DAT0x 안 묶음(0x0036 머리, 맵→묶음 u16 표 L 0x46BF0), op 004E/004F/0050
  아스테카 : 묶음 표 u32 절대(L 0x2AEA0), 묶음 = [문장들][스크립트], op 0043/0056/006D
  python tools/ysrefs.py   → 게임별 참조 문장 수 · 스캔 추출과 대조
"""
import bisect, os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import ystext

OPS = {'ys1': {0x50, 0x51, 0x52}, 'ys2': {0x4E, 0x4F, 0x50}, 'sun': {0x43, 0x56, 0x6D}}
PTR_TABLES = {'ys1': [('fc1/YS1_0YS1L.BIN', 0x84E9C), ('fc1/YS1_0YS1L.BIN', 0x8E8F4)],
              'sun': [('fc2/SUN_0SUNL.BIN', 0x2AEA0)]}


def u16s(d):
    n = len(d) // 2
    return struct.unpack('>%dH' % n, d[:2 * n])


def ptr_table(d, at):
    out = []
    while True:
        p = struct.unpack_from('>I', d, at)[0]
        if not 0x200000 <= p < 0x300000:
            return out
        out.append(p - 0x200000); at += 4


def blocks(game):
    """→ {파일: [묶음 시작…]} (파일 오프셋, 오름차순)"""
    res = {}
    if game == 'ys2':
        for f in ystext.FILES['ys2'][1:]:
            v = u16s(open(os.path.join(ystext.DISC, f), 'rb').read())
            res[f] = [i * 2 for i in range(2, len(v)) if v[i] == 0x36 and (v[i - 1] == 0xFFF or v[i - 2] == 0x7FFF)]
    else:
        for f, at in PTR_TABLES[game]:
            d = open(os.path.join(ystext.DISC, f), 'rb').read()
            res.setdefault(f, set()).update(ptr_table(d, at))
        res = {f: sorted(s) for f, s in res.items()}
    return res


def refs(game):
    """→ [(파일, 묶음, 참조 위치, op, 문장 시작)]"""
    out = []
    lim = ystext.limit(game)
    spans = {}
    for f, a, e, cs in ystext.strings(game):
        if ystext.is_text(cs, ystext.charmap(game)):
            spans.setdefault(f, []).append((a, e))
    for f, bs in blocks(game).items():
        d = open(os.path.join(ystext.DISC, f), 'rb').read(); v = u16s(d)
        sp = sorted(spans.get(f, [])); sa = [a for a, e in sp]
        def in_text(p):
            k = bisect.bisect_right(sa, p) - 1
            return k >= 0 and p < sp[k][1]
        for k, B in enumerate(bs):
            tabs = [at for ff, at in PTR_TABLES.get(game, []) if ff == f and at > B]
            if k + 1 < len(bs):
                E = bs[k + 1]
            elif tabs:                  # 묶음 표가 마지막 묶음 바로 뒤에 온다
                E = min(tabs)
            else:                       # 마지막 묶음 = 뒤로 이어진 문장 구역 끝까지(스크립트 포함, 0x400 넘는 빈틈에서 끊음)
                E = B
                for a, e in sp:
                    if a < B:
                        continue
                    if E == B or a - E < 0x400:
                        E = max(E, e)
                    elif a > E + 0x400:
                        break
            for i in range(B // 2 + 1, E // 2):
                if v[i - 1] in OPS[game] and not in_text(i * 2 - 2):
                    S = B + 2 * v[i]
                    if B <= S < E and (S == B or v[S // 2 - 1] == 0xFFF or v[S // 2 - 1] < lim) and S // 2 != i:
                        j = S // 2
                        while j < len(v) and j - S // 2 < 400 and (v[j] < lim or 0xE00 <= v[j] <= 0xFFE):
                            j += 1
                        if j < len(v) and v[j] == 0xFFF and j > S // 2:
                            out.append((f, B, i * 2, v[i - 1], S))
    return out


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    for g in ('ys1', 'ys2', 'sun'):
        R = refs(g)
        starts = {(f, S) for f, _, _, _, S in R}
        scan = {(f, a) for f, a, e, cs in ystext.strings(g)}
        print(g, '묶음', sum(len(b) for b in blocks(g).values()), '참조', len(R), '문장', len(starts),
              '· 스캔에도 있음', len(starts & scan), '· 참조만', len(starts - scan))


if __name__ == '__main__':
    main()
