# -*- coding: utf-8 -*-
r"""OCR 표 → 한자 코드별 다수결 → work/kanji_<게임>.tsv (코드 · 글자 · 확신 · 득표)
  python tools/ocrvote.py ys2
· 칸 간격 고정 — 인식 글자의 가로 중심으로 칸을 짚는다(단어 상자는 글자 수로 균등 분할).
· work/kanji_<게임>_fix.tsv (코드\t글자) 는 늘 우선(눈 검토 결과).
"""
import collections, glob, json, os, sys, unicodedata
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import ystext


def nk(c):
    return unicodedata.normalize('NFKC', c)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    game = sys.argv[1]
    base = ystext.charmap(game)
    base = {k: v for k, v in base.items() if k < 0xE0 or (game == 'sun' and k < 0x100)}
    lim = ystext.limit(game)
    votes = collections.defaultdict(collections.Counter); ok = tot = 0
    for D in sorted(glob.glob(os.path.join(ROOT, 'work', 'ocr', game + '_*'))):
        L = json.load(open(os.path.join(D, 'layout.json')))
        pitch, x0, lh, gh = L['pitch'], L['x0'], L['lineh'], L['glyph']
        for im in L['images']:
            p = os.path.join(D, im['img'].replace('.png', '.txt'))
            if not os.path.exists(p):
                continue
            for row in open(p, encoding='utf-8-sig'):
                f = row.rstrip('\n').split('\t')
                if len(f) < 5:
                    continue
                t = f[0].replace(' ', '')
                if not t:
                    continue
                X, Y, W, H = map(float, f[1:5]); cy = Y + H / 2
                li = min(range(len(im['lines'])), key=lambda i: abs(im['lines'][i]['y'] + gh / 2 - cy))
                line = im['lines'][li]
                if abs(line['y'] + gh / 2 - cy) > lh / 2:
                    continue
                for i, ch in enumerate(t):
                    j = int((X + (i + 0.5) * W / len(t) - x0) // pitch)
                    if not 0 <= j < len(line['cells']):
                        continue
                    c = line['cells'][j]
                    if c in base:
                        tot += 1; ok += nk(ch) == nk(base[c])
                    elif 0xE0 <= c < lim:
                        votes[c][ch] += 1
    print('아는 칸(가나·기호) OCR 일치 %d/%d (%.1f%%)' % (ok, tot, 100 * ok / max(1, tot)))
    fix = {}
    fp = os.path.join(ROOT, 'work', 'kanji_%s_fix.tsv' % game)
    if os.path.exists(fp):
        for line in open(fp, encoding='utf-8'):
            f = line.rstrip('\n').split('\t')
            if len(f) >= 2 and f[0][:1] != '#':
                fix[int(f[0], 16)] = f[1]
    st = collections.Counter()
    with open(os.path.join(ROOT, 'work', 'kanji_%s.tsv' % game), 'w', encoding='utf-8') as fo:
        fo.write('#코드\t글자\t확신\t득표\n')
        for c in range(0xE0, lim):
            if game == 'sun' and c < 0x100:
                continue
            v = votes.get(c, collections.Counter()); n = sum(v.values())
            if c in fix:
                ch, conf = fix[c], 'fix'
            elif n:
                ch, k = v.most_common(1)[0]; conf = '%.2f' % (k / n)
            else:
                ch, conf = '', '0'
            st['fix' if conf == 'fix' else ('none' if not n else ('hi' if float(conf) >= 0.8 and n >= 3 else 'lo'))] += 1
            fo.write('%X\t%s\t%s\t%s\n' % (c, ch, conf, ' '.join('%s%d' % t for t in v.most_common(4))))
    print(game, dict(st))


if __name__ == '__main__':
    main()
