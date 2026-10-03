# -*- coding: utf-8 -*-
r"""제나두 대사 (2026-10-03)
  글꼴 = ZANA/0ZANAL.BIN 2bpp 아틀라스: 폭 192px(12px×16글자), 칸 12×12, 원점 L 0xBB3A0, 864칸(0 = 공백, 1‥10 = 0‥9, 11 ! 12 ?, 16‥ A‥Z a‥z …)
  대사 = ZANA/1ZANAH.BIN 의 u16 BE = 아틀라스 번호 그대로, 0xFFD 줄 · 0xFFF 끝 (이스와 같은 엔진 계열). 1ZANAH.DEM 에 사본(+0x3CC).
  글자표 = work/kanji_zana.tsv (번호\t글자) — OCR(ocrprep_zana) + 눈 검토
  python tools/zanatext.py ocr      → work/ocr/zana_<배율>/ (그 뒤 winocr.ps1 → ocrvote_zana)
  python tools/zanatext.py extract  → work/text/zana.tsv
"""
import json, os, struct, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import ystext

L_PATH = os.path.join(ROOT, 'work', 'disc', 'fc1', 'zana', '0ZANAL.BIN')
H_PATH = os.path.join(ROOT, 'work', 'disc', 'fc1', 'zana', '1ZANAH.BIN')
ORIGIN = 0xBB3A0; ROWB = 576; NGLYPH = 864


def atlas():
    d = open(L_PATH, 'rb').read()
    a = np.frombuffer(d, np.uint8); p = np.stack([a >> 6, (a >> 4) & 3, (a >> 2) & 3, a & 3], 1).ravel()
    G = []
    for n in range(NGLYPH):
        r, c = divmod(n, 16); o = ORIGIN + r * ROWB
        G.append(p[o * 4:(o + ROWB) * 4].reshape(12, 192)[:, c * 12:c * 12 + 12])
    return np.array(G)


def strings():
    d = open(H_PATH, 'rb').read()
    for a, e in ystext.scan(d, NGLYPH):
        if not 0x92000 <= a < 0x96000:          # 대사 구역(H 0x92218‥0x95E4E) 밖은 우연 일치
            continue
        cs = ystext.codes(d, a, e)
        if sum(1 for c in cs if 0x60 <= c < NGLYPH) >= 3:
            yield a, e, cs


def charmap():
    m = {}
    p = os.path.join(ROOT, 'work', 'kanji_zana.tsv')
    if os.path.exists(p):
        for line in open(p, encoding='utf-8'):
            f = line.rstrip('\n').split('\t')
            if len(f) >= 2 and f[0][:1] != '#' and f[1]:
                m[int(f[0], 16)] = f[1]
    return m


def ocr(S=4):
    from PIL import Image
    G = atlas(); D = os.path.join(ROOT, 'work', 'ocr', 'zana_%d' % S); os.makedirs(D, exist_ok=True)
    lines = []; seen = set()
    for a, e, cs in strings():
        cur = []
        for c in cs + [0xFFF]:
            if c >= 0xE00:
                if len(cur) >= 2 and tuple(cur) not in seen:
                    seen.add(tuple(cur)); lines.append(cur)
                cur = []
            else:
                cur.append(c)
    pitch = 12 * S + 2 * S; lh = 12 * S + 6 * S; x0 = 4 * S; PER = 40
    lay = {'pitch': pitch, 'x0': x0, 'lineh': lh, 'glyph': 12 * S, 'images': []}
    for k in range(0, len(lines), PER):
        chunk = lines[k:k + PER]
        W = x0 * 2 + pitch * max(len(l) for l in chunk); H = lh * len(chunk) + 8 * S
        im = np.ones((H, W), np.uint8) * 255; info = []
        for li, l in enumerate(chunk):
            y = 4 * S + li * lh
            for j, c in enumerate(l):
                if c < NGLYPH:
                    big = np.kron(G[c] != 0, np.ones((S, S), bool)); x = x0 + j * pitch
                    im[y:y + 12 * S, x:x + 12 * S][big] = 0
            info.append({'y': y, 'cells': l})
        name = 'img_%03d.png' % (k // PER); Image.fromarray(im).save(os.path.join(D, name))
        lay['images'].append({'img': name, 'lines': info})
    json.dump(lay, open(os.path.join(D, 'layout.json'), 'w'))
    print(len(lines), '줄', D)


def extract():
    sys.stdout.reconfigure(encoding='utf-8')
    m = charmap(); n = 0
    os.makedirs(os.path.join(ROOT, 'work', 'text'), exist_ok=True)
    with open(os.path.join(ROOT, 'work', 'text', 'zana.tsv'), 'w', encoding='utf-8') as fo:
        fo.write('번호\t파일\t오프셋\t끝\t원문\t번역\n')
        for a, e, cs in strings():
            n += 1
            fo.write('zana%04d\t1ZANAH.BIN\t%X\t%X\t%s\t\n' % (n, a, e, ystext.decode(cs, m)))
    print('zana', n, '문자열')


if __name__ == '__main__':
    {'ocr': lambda: (ocr(4), ocr(3)), 'extract': extract}[sys.argv[1]]()
