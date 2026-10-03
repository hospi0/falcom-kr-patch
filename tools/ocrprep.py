# -*- coding: utf-8 -*-
r"""한자 칸 판독용 OCR 그림 — 대사 줄을 게임 글꼴(잉크 = 값 1·2)로 흰 바탕에 크게 그린다.
  python tools/ocrprep.py ys2 [배율=4]   → work/ocr/<게임>_<배율>/img_*.png + layout.json
  powershell -ExecutionPolicy Bypass -File tools\winocr.ps1 -Dir work\ocr\<게임>_<배율>
"""
import json, os, sys
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import ysfont, ystext


def lines_of(game):
    lim = ystext.limit(game); seen = set(); out = []
    for f, a, e, cs in ystext.strings(game):
        cur = []
        for c in cs + [0xFFF]:
            if c >= 0xE00:
                if c == 0xE10:
                    cur.append(0); continue
                if any(0xE0 <= x < lim for x in cur) and tuple(cur) not in seen:
                    seen.add(tuple(cur)); out.append(cur)
                cur = []
            else:
                cur.append(c)
    return out


def main():
    game = sys.argv[1]; S = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    d, gs, tab = ysfont.load(game)
    D = os.path.join(ROOT, 'work', 'ocr', '%s_%d' % (game, S)); os.makedirs(D, exist_ok=True)
    gl = {}
    def G(c):
        if c not in gl:
            g = ysfont.code_glyph(d, gs, tab, c)
            gl[c] = None if g is None else ((g == 1) | (g == 2))
        return gl[c]
    lines = lines_of(game)
    pitch = gs * S + 2 * S; lh = gs * S + 6 * S; x0 = 4 * S; PER = 40
    lay = {'pitch': pitch, 'x0': x0, 'lineh': lh, 'glyph': gs * S, 'images': []}
    for k in range(0, len(lines), PER):
        chunk = lines[k:k + PER]
        W = x0 * 2 + pitch * max(len(l) for l in chunk); H = lh * len(chunk) + 8 * S
        im = np.ones((H, W), np.uint8) * 255; info = []
        for li, l in enumerate(chunk):
            y = 4 * S + li * lh
            for j, c in enumerate(l):
                g = G(c)
                if g is None:
                    continue
                big = np.kron(g, np.ones((S, S), bool))
                x = x0 + j * pitch
                im[y:y + gs * S, x:x + gs * S][big] = 0
            info.append({'y': y, 'cells': l})
        name = 'img_%03d.png' % (k // PER)
        Image.fromarray(im).save(os.path.join(D, name))
        lay['images'].append({'img': name, 'lines': info})
    json.dump(lay, open(os.path.join(D, 'layout.json'), 'w'))
    print(game, len(lines), '줄 →', len(lay['images']), '장', D)


if __name__ == '__main__':
    main()
