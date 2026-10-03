# -*- coding: utf-8 -*-
r"""이스 II 굵은 둘째 벌(마물 모습일 때 대사) 판정·바른 원문 (2026-10-03)
  ★문자열마다 보통 벌(ys2)·굵은 벌(ys2b) 중 어느 쪽으로 그려지는지 = 두 글자표로 풀어 «글자 2-gram 언어 모형»(이스 I·아스테카 원문 + 확신 높은 것 되먹임) 점수가 높은 쪽.
     DB/DC(굵은 벌 ？！, 보통 벌엔 빈칸·㈱)가 들면 무조건 굵은 벌. 손 판정 = work/ys2_fontset.tsv 의 «수동».
  python tools/ys2bold.py classify   → work/ys2_fontset.tsv (번호·N/B/-·차이)
  python tools/ys2bold.py review     → work/ys2b_review.tsv (번역 TSV 번호·종류(암호/검토)·바른 원문·지금 번역)
"""
import collections, math, os, re, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import ystext, ystrans

MANUAL = {'ys20470': 'N', 'ys20374': 'B'}


def codes(r):
    f, a, e = r[1], int(r[2], 16), int(r[3], 16)
    p = os.path.join(ROOT, 'work', 'disc', 'fc2', 'YS2_0YS2L.BIN' if 'YS2L' in f else os.path.join('ys2', f))
    d = open(p, 'rb').read()
    return list(struct.unpack('>%dH' % ((e - a) // 2), d[a:e]))


def rows():
    return [l.rstrip('\n').split('\t') for l in open(os.path.join(ROOT, 'work', 'text', 'ys2.tsv'), encoding='utf-8')][1:]


def classify():
    ref = []
    for g in ('ys1', 'sun'):
        for l in open(os.path.join(ROOT, 'work', 'text', g + '.tsv'), encoding='utf-8'):
            x = l.split('\t')
            if len(x) > 4: ref.append(x[4])
    mN = ystext.charmap('ys2'); mB = ystext.charmap('ys2b')
    data = [(r[0], codes(r)) for r in rows()]

    def model(texts):
        uni = collections.Counter(); bi = collections.Counter()
        for t in texts:
            t = '^' + t + '$'; uni.update(t); bi.update(t[i:i + 2] for i in range(len(t) - 1))
        return uni, bi

    def score(t, uni, bi):
        t = '^' + t + '$'
        return sum(math.log((bi[t[i:i + 2]] + 0.1) / (uni[t[i]] + 600)) for i in range(len(t) - 1))
    corpus = list(ref)
    for _ in range(3):
        uni, bi = model(corpus); cls = {}; new = []
        for no, cs in data:
            K = [c for c in cs if 0xE0 <= c < 0xE00]
            bang = any(c in (0xDB, 0xDC) for c in cs)
            tn = ystext.decode(cs, mN); tb = ystext.decode(cs, mB)
            if not K:
                cls[no] = ('B' if bang else '-', 0.0); continue
            if any(c >= 0xE0 + 384 for c in K):
                cls[no] = ('N', 99.0); new.append(tn); continue
            m = (score(tb, uni, bi) - score(tn, uni, bi)) / len(K)
            k = 'B' if (m > 0 or bang) else 'N'; cls[no] = (k, m)
            if abs(m) > 2 or bang: new.append(tb if k == 'B' else tn)
        corpus = ref + new
    with open(os.path.join(ROOT, 'work', 'ys2_fontset.tsv'), 'w', encoding='utf-8') as f:
        f.write('#번호\t벌(N 보통·B 굵은·- 한자 없음)\t차이\n')
        for no, (k, m) in cls.items():
            f.write('%s\t%s\t%s\n' % (no, MANUAL.get(no, k), '수동' if no in MANUAL else '%.2f' % m))
    print(collections.Counter(MANUAL.get(no, k) for no, (k, m) in cls.items()))


def fontset():
    return {l.split('\t')[0]: l.split('\t')[1] for l in open(os.path.join(ROOT, 'work', 'ys2_fontset.tsv'), encoding='utf-8') if not l.startswith('#')}


def rare(c):
    b = c.encode('cp949'); return not (0xB0 <= b[0] <= 0xC8 and b[1] >= 0xA1)


def cipher(t):
    return sum(1 for c in t if '가' <= c <= '힣' and rare(c)) >= 3


def review():
    cls = fontset(); R = {r[0]: r for r in rows()}; mB = ystext.charmap('ys2b')
    src2 = collections.defaultdict(list)
    for no, r in R.items(): src2[r[4]].append(no)
    out = []
    for r in ystrans.load_rows('ys2'):
        nos = src2.get(r['src'], [])
        isB = any(cls.get(n) == 'B' for n in nos); ci = cipher(r['tr'])
        if not (ci or (isB and re.search(r'[一-龥]', r['src']))): continue
        good = ystext.decode(codes(R[nos[0]]), mB) if isB else r['src']
        out.append((r['no'], '암호' if ci else '검토', good, '' if ci else r['tr']))
    with open(os.path.join(ROOT, 'work', 'ys2b_review.tsv'), 'w', encoding='utf-8') as f:
        f.write('번호\t종류\t바른 원문(굵은 벌)\t지금 번역\n')
        for x in out: f.write('\t'.join(x) + '\n')
    print(len(out), collections.Counter(x[1] for x in out))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    {'classify': classify, 'review': review}[sys.argv[1]]()
