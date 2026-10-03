# -*- coding: utf-8 -*-
r"""SJIS 문자열 훑기 — 파일마다 «2바이트 SJIS 가 n 자 이상 이어지는 덩어리» 수·글자 수·영역·표본
  python tools/sjisscan.py [최소글자=4] [파일...]   (기본: work/disc/*/* 전부)
"""
import glob, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)


def is_lead(b):
    return 0x81 <= b <= 0x9F or 0xE0 <= b <= 0xEF


def runs(d, minc=4):
    out = []; i = 0; n = len(d)
    while i < n - 1:
        j = i; c = 0; kana = 0
        while j < n - 1:
            b, t = d[j], d[j + 1]
            if is_lead(b) and 0x40 <= t <= 0xFC and t != 0x7F:
                c += 1; kana += (b == 0x82 and t >= 0x9F) or (b == 0x83 and t <= 0x96); j += 2
            elif 0x20 <= b < 0x7F and c:
                j += 1
            else:
                break
        if c >= minc and kana:
            out.append((i, j, c))
            i = j
        else:
            i += 1
    return out


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    minc = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 4
    files = [a for a in sys.argv[1:] if not a.isdigit()] or sorted(glob.glob(os.path.join(ROOT, 'work', 'disc', '*', '*')))
    for p in files:
        d = open(p, 'rb').read(); r = runs(d, minc)
        if not r:
            print('%-28s 0' % os.path.relpath(p, os.path.join(ROOT, 'work', 'disc'))); continue
        tot = sum(c for _, _, c in r)
        print('%-28s 덩어리 %5d · 글자 %7d · 0x%X‥0x%X' % (os.path.relpath(p, os.path.join(ROOT, 'work', 'disc')), len(r), tot, r[0][0], r[-1][1]))
        for a, b, c in r[:3] + r[len(r) // 2:len(r) // 2 + 2]:
            print('    0x%06X %s' % (a, d[a:b].decode('cp932', 'replace')[:50]))


if __name__ == '__main__':
    main()
