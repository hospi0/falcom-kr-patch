# -*- coding: utf-8 -*-
r"""팔콤 클래식 1편 디스크 빌더 (2026-10-03) — 트랙 01 에 그림 글자 제자리 교체
  ① 드래곤 슬레이어 DRS/0DRSL.BIN·0DRSL.DEM (tools/drs_gfx.py)
  ② 메인 메뉴 루트 `0` (tools/menu1_gfx.py)
  python tools/build_fc1.py              → 미리보기(work/fc1_preview.png, my files/그래픽/)
  python tools/build_fc1.py --write      → work/out/fc1/ 트랙 01
  python tools/build_fc1.py --install    → + F: 설치
"""
import hashlib, os, shutil, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import disc, iso, gfx_kr, drs_gfx, menu1_gfx, ysbuild, zana_hw, zanabuild, zana_gfx

OUT = os.path.join(ROOT, 'work', 'out', 'fc1')
TRACK01 = os.path.basename(disc.TRACK['fc1'])
F_DIR = r'F:\hospi\roms\ss roms\Falcom Classics (Japan) (Disc 1) (Game Disc)'


def sheet(pairs, path_work, path_mine):
    from PIL import Image
    pal = np.zeros((16, 3), np.uint8)
    for c in range(16):
        pal[c] = (c * 17,) * 3
    pal[1] = (250, 250, 250); pal[2] = (120, 120, 120); pal[4] = (110, 110, 140); pal[5] = (230, 230, 255); pal[15] = (255, 255, 255)
    rows = []
    for a, b, _ in pairs:
        w = a.shape[1]; pad = np.zeros((a.shape[0] * 2 + 6, 320, 3), np.uint8)
        pad[:a.shape[0], :w] = pal[a]; pad[a.shape[0] + 2:a.shape[0] * 2 + 2, :w] = pal[b]; rows.append(pad)
    img = Image.fromarray(np.vstack(rows)); img = img.resize((640, img.size[1] * 2), 0)
    img.save(path_work); os.makedirs(os.path.dirname(path_mine), exist_ok=True); img.save(path_mine)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    a = sys.argv[1:]
    L0 = disc.read('fc1', 'DRS/0DRSL.BIN'); D0 = disc.read('fc1', 'DRS/0DRSL.DEM')
    L1, reg, p1 = drs_gfx.patch_l(L0)
    D1 = bytearray(D0)
    for s, e in reg:
        assert D0[s:e] == L0[s:e], ('DEM 사본이 다른 구역', hex(s)); D1[s:e] = L1[s:e]
    M0 = disc.read('fc1', '0')
    M1, _, p2 = menu1_gfx.patch_0(M0)
    gd = os.path.join(ROOT, 'my files', '그래픽')
    sheet(p1, os.path.join(ROOT, 'work', 'drs_preview.png'), os.path.join(gd, '01_드래곤슬레이어_글자그림(줄마다 위원본_아래한글).png'))
    sheet(p2, os.path.join(ROOT, 'work', 'menu1_preview.png'), os.path.join(gd, '02_1편메뉴_글자그림(줄마다 위원본_아래한글).png'))
    G, p3 = gfx_kr.build_fc1(lambda n: disc.read('fc1', n))
    for n, b in G.items():
        print('  %s 바뀐 바이트 %d' % (n, gfx_kr.check(n, disc.read('fc1', n), b)))
    G['YS1/0YS1L.BIN'], info = ysbuild.build_ys1(G['YS1/0YS1L.BIN'])      # 이스 I 대사·글꼴(그림 라벨 위에)
    print('  이스 I 대사', info)
    H0 = disc.read('fc1', 'ZANA/1ZANAH.BIN'); D0z = disc.read('fc1', 'ZANA/1ZANAH.DEM')
    G['ZANA/1ZANAH.BIN'] = zana_hw.patch(H0); G['ZANA/1ZANAH.DEM'] = zana_hw.patch_dem(D0z)   # 제나두 아이템 이름 영문
    G['ZANA/1ZANAH.BIN'], G['ZANA/1ZANAH.DEM'], G['ZANA/0ZANAL.BIN'], G['ZANA/0ZANAL.DEM'], zi = zanabuild.build(
        G['ZANA/1ZANAH.BIN'], G['ZANA/1ZANAH.DEM'], disc.read('fc1', 'ZANA/0ZANAL.BIN'), disc.read('fc1', 'ZANA/0ZANAL.DEM'))   # 제나두 대사·글꼴
    print('  제나두 대사', zi)
    G['ZANA/0ZANAL.BIN'], G['ZANA/0ZANAL.DEM'], _, gi = zana_gfx.build(G['ZANA/0ZANAL.BIN'], G['ZANA/0ZANAL.DEM'])   # 제나두 그림 글자(메뉴 판·탭·저장·가게)
    print('  제나두 그림', gi)
    for n, o, b in (('1ZANAH.BIN', H0, G['ZANA/1ZANAH.BIN']), ('1ZANAH.DEM', D0z, G['ZANA/1ZANAH.DEM'])):
        print('  제나두 %s 바뀐 바이트 %d' % (n, sum(1 for i in range(len(o)) if o[i] != b[i])))
    print('드래곤 슬레이어 %d장 · 1편 메뉴 %d장 · 이스 I 그림 %d장' % (len(p1), len(p2), len(p3)))
    if '--write' in a or '--install' in a:
        os.makedirs(OUT, exist_ok=True)
        dst = os.path.join(OUT, TRACK01); shutil.copyfile(disc.TRACK['fc1'], dst)
        iso.patch_sub(dst, {'DRS/0DRSL.BIN': L1, 'DRS/0DRSL.DEM': bytes(D1), '0': M1, **G})
        print('트랙 01', dst, hashlib.md5(open(dst, 'rb').read()).hexdigest())
        if '--install' in a:
            shutil.copyfile(dst, os.path.join(F_DIR, TRACK01)); print('F: 설치', F_DIR)


if __name__ == '__main__':
    main()
