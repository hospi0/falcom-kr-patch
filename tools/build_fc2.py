# -*- coding: utf-8 -*-
r"""팔콤 클래식 2편 디스크 빌더 (2026-10-03) — 트랙 1 에 제자리 교체
  ① 메인 메뉴 SUN/0FC2L.BIN (tools/menu2_gfx.py)
  ② 그림 글자 (tools/gfx_kr.py)
  ③ 아스테카 대사·시스템 목록·글꼴 SUN/0SUNL.BIN (tools/ysbuild.build_sun, 번역 = my files/번역/sun_*.tsv + work/tr_fix/sun.tsv)
  ④ 이스 II 대사·아이템 설명·시스템 목록·글꼴 YS2/0YS2L.BIN + YS2/DAT01‥04.BIN (tools/ysbuild.build_ys2)
  python tools/build_fc2.py              → 미리보기(work/menu2_preview.png, my files/그래픽/)
  python tools/build_fc2.py --write      → work/out/fc2/ 트랙 1
  python tools/build_fc2.py --install    → + F: 설치
"""
import hashlib, os, shutil, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import disc, iso, menu2_gfx, gfx_kr, ysbuild
from build_fc1 import sheet

OUT = os.path.join(ROOT, 'work', 'out', 'fc2')
TRACK1 = os.path.basename(disc.TRACK['fc2'])
F_DIR = r'F:\hospi\roms\ss roms\Falcom Classics II (Japan)'


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    a = sys.argv[1:]
    L0 = disc.read('fc2', 'SUN/0FC2L.BIN')
    L1, _, pairs = menu2_gfx.patch_l(L0)
    sheet(pairs, os.path.join(ROOT, 'work', 'menu2_preview.png'),
          os.path.join(ROOT, 'my files', '그래픽', '03_2편메뉴_글자그림(줄마다 위원본_아래한글).png'))
    G, p2 = gfx_kr.build_fc2(lambda n: disc.read('fc2', n))
    for n, b in G.items():
        print('  %s 바뀐 바이트 %d' % (n, gfx_kr.check(n, disc.read('fc2', n), b)))
    print('2편 메뉴 %d장 · 이스 II·아스테카 그림 %d장 + 클리어 타임' % (len(pairs), len(p2)))
    G['SUN/0SUNL.BIN'], si = ysbuild.build_sun(disc.read('fc2', 'SUN/0SUNL.BIN'))
    print('아스테카 본문', si)
    D0 = {f: disc.read('fc2', 'YS2/' + f) for f in ysbuild.YS2_DATS}
    L2, D2, yi = ysbuild.build_ys2(disc.read('fc2', 'YS2/0YS2L.BIN'), D0)
    G['YS2/0YS2L.BIN'] = L2
    for f, b in D2.items(): G['YS2/' + f] = b
    print('이스 II 본문', yi)
    # ⑤ 동영상 자막(tools/moviesub.py 가 구운 work/movie/kr/<영상>, 원본 크기 그대로 — 제자리)
    import moviesub
    for name, paths in moviesub.DISC.items():
        p = os.path.join(moviesub.OUT, name)
        if not os.path.exists(p): continue
        b = open(p, 'rb').read()
        for n in paths:
            assert len(b) == len(disc.read('fc2', n)), ('동영상 크기 다름', n)
            G[n] = b
        print('  동영상 자막 %s → %s' % (name, ', '.join(paths)))
    if '--write' in a or '--install' in a:
        os.makedirs(OUT, exist_ok=True)
        dst = os.path.join(OUT, TRACK1); shutil.copyfile(disc.TRACK['fc2'], dst)
        iso.patch_sub(dst, {'SUN/0FC2L.BIN': L1, **G})
        print('트랙 1', dst, hashlib.md5(open(dst, 'rb').read()).hexdigest())
        if '--install' in a:
            shutil.copyfile(dst, os.path.join(F_DIR, TRACK1)); print('F: 설치', F_DIR)


if __name__ == '__main__':
    main()
