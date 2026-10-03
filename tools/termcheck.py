# -*- coding: utf-8 -*-
r"""용어 통일 검사 (2026-10-03)
  원문 용어(가타카나 3자 이상 · 시스템 목록 항목 · 한자 낱말)마다, 그 용어가 든 번역 줄들에서 «가장 많이 함께 나오는 한글 낱말»을 대표 번역으로 보고
  대표 번역이 없는 줄을 보고한다. 게임 사이(이스 I↔II)도 같은 용어면 함께 본다.
  python tools/termcheck.py [게임…]   → work/termcheck.txt
"""
import collections, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import ystrans

KATA = re.compile(r'[ァ-ヶー・]{3,}')
HAN = re.compile(r'[가-힣]+')


def ngrams(t):
    s = ''.join(HAN.findall(t.replace(' ', '')))
    out = set()
    for w in HAN.findall(t):
        for n in range(2, min(8, len(w)) + 1):
            for i in range(len(w) - n + 1): out.add(w[i:i + n])
    return out


def terms(rows):
    c = collections.Counter()
    for r in rows:
        for k in set(KATA.findall(r['src'])): c[k.strip('・ー')] += 1
    return [k for k, n in c.items() if n >= 2 and len(k) >= 3]


def check(games, extra=()):
    rows = []
    for g in games:
        for r in ystrans.load_rows(g):
            if r['tr'].strip(): r['g'] = g; rows.append(r)
    T = sorted(set(terms(rows)) | set(extra), key=len, reverse=True)
    out = []
    for t in T:
        R = [r for r in rows if t in r['src']]
        if len(R) < 2: continue
        cnt = collections.Counter()
        for r in R: cnt.update(ngrams(r['tr']))
        best = max(cnt, key=lambda k: (cnt[k], len(k))) if cnt else None
        if not best: continue
        miss = [r for r in R if best not in r['tr'].replace(' ', '') and best not in r['tr']]
        if miss:
            out.append((t, best, cnt[best], len(R), [(r['g'], r['no'], r['tr'][:50]) for r in miss]))
    return out


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    gs = sys.argv[1:] or ['ys1', 'ys2', 'sun', 'zana']
    res = check(gs)
    with open(os.path.join(ROOT, 'work', 'termcheck.txt'), 'w', encoding='utf-8') as f:
        for t, b, n, m, miss in res:
            f.write('%s  «%s» %d/%d\n' % (t, b, n, m))
            for x in miss: f.write('    %s %s %s\n' % x)
    print(len(res), '용어 불일치 → work/termcheck.txt')
