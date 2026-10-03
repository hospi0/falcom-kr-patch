# -*- coding: utf-8 -*-
r"""한자 판정 눈 검토 시트 — 게임 글리프(크게) 옆에 판정 글자(MS 고딕), 확신 낮음 = 노란 바탕.
  python tools/kanjisheet.py ys2 [코드목록파일]  → work/review/<게임>_NN.png
"""
import os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import ysfont

COLS, ROWS = 12, 10


def main():
    game = sys.argv[1]
    d, gs, tab = ysfont.load(game)
    rows = [l.rstrip('\n').split('\t') for l in open(os.path.join(ROOT, 'work', 'kanji_%s.tsv' % game), encoding='utf-8') if l[:1] != '#']
    if len(sys.argv) > 2:
        want = {int(x, 16) for x in open(sys.argv[2]).read().split()}
        rows = [r for r in rows if int(r[0], 16) in want]
    F = ImageFont.truetype(r'C:\Windows\Fonts\msgothic.ttc', 40)
    S = 48 // gs * 1 if gs == 16 else 4
    S = 3 if gs == 16 else 4
    cw, ch = 120, 78
    out = os.path.join(ROOT, 'work', 'review'); os.makedirs(out, exist_ok=True)
    per = COLS * ROWS
    for p in range(0, len(rows), per):
        im = Image.new('RGB', (COLS * cw, ROWS * ch), (255, 255, 255)); dr = ImageDraw.Draw(im)
        for i, r in enumerate(rows[p:p + per]):
            x, y = (i % COLS) * cw, (i // COLS) * ch
            c = int(r[0], 16)
            lo = r[2] != 'fix' and (r[2] == '0' or float(r[2]) < 0.8)
            if lo:
                dr.rectangle((x, y, x + cw - 1, y + ch - 1), fill=(255, 240, 150))
            g = ysfont.code_glyph(d, gs, tab, c)
            a = np.where((g == 1) | (g == 2), 0, 255).astype(np.uint8)
            im.paste(Image.fromarray(a).resize((gs * S, gs * S), Image.NEAREST).convert('RGB'), (x + 4, y + 18))
            dr.text((x + 2, y + 1), r[0], fill=(200, 0, 0))
            dr.text((x + 62, y + 22), r[1] or '?', font=F, fill=(0, 0, 160))
            dr.line((x + cw - 1, y, x + cw - 1, y + ch), fill=(200, 200, 200))
            dr.line((x, y + ch - 1, x + cw, y + ch - 1), fill=(200, 200, 200))
        im.save(os.path.join(out, '%s_%02d.png' % (game, p // per)))
    print(game, len(rows), '칸 →', (len(rows) + per - 1) // per, '장')


if __name__ == '__main__':
    main()
