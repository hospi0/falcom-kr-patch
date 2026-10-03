# -*- coding: utf-8 -*-
r"""제나두 OCR 표 → 번호별 다수결 → work/kanji_zana.tsv (눈 검토 고침 work/kanji_zana_fix.tsv 우선)"""
import collections, glob, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
votes = collections.defaultdict(collections.Counter)
for D in glob.glob(os.path.join(ROOT, 'work', 'ocr', 'zana_*')):
    L = json.load(open(os.path.join(D, 'layout.json')))
    for im in L['images']:
        p = os.path.join(D, im['img'].replace('.png', '.txt'))
        for row in open(p, encoding='utf-8-sig'):
            f = row.rstrip('\n').split('\t')
            if len(f) < 5 or not f[0].replace(' ', ''): continue
            t = f[0].replace(' ', ''); X, Y, W, H = map(float, f[1:5]); cy = Y + H / 2
            li = min(range(len(im['lines'])), key=lambda i: abs(im['lines'][i]['y'] + L['glyph'] / 2 - cy))
            line = im['lines'][li]
            if abs(line['y'] + L['glyph'] / 2 - cy) > L['lineh'] / 2: continue
            for i, ch in enumerate(t):
                j = int((X + (i + 0.5) * W / len(t) - L['x0']) // L['pitch'])
                if 0 <= j < len(line['cells']): votes[line['cells'][j]][ch] += 1
fix = {}
fp = os.path.join(ROOT, 'work', 'kanji_zana_fix.tsv')
if os.path.exists(fp):
    for line in open(fp, encoding='utf-8'):
        f = line.rstrip('\n').split('\t')
        if len(f) >= 2 and f[0][:1] != '#': fix[int(f[0], 16)] = f[1]
st = collections.Counter()
with open(os.path.join(ROOT, 'work', 'kanji_zana.tsv'), 'w', encoding='utf-8') as fo:
    fo.write('#번호\t글자\t확신\t득표\n')
    for c in range(864):
        v = votes.get(c, collections.Counter()); n = sum(v.values())
        if c in fix: ch, conf = fix[c], 'fix'
        elif n: ch, k = v.most_common(1)[0]; conf = '%.2f' % (k / n)
        else: ch, conf = '', '0'
        st['fix' if conf == 'fix' else ('none' if not n else ('hi' if float(conf) >= .8 and n >= 3 else 'lo'))] += 1
        fo.write('%X\t%s\t%s\t%s\n' % (c, ch, conf, ' '.join('%s%d' % t for t in v.most_common(4))))
print(dict(st))
