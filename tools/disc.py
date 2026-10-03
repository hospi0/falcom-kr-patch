# -*- coding: utf-8 -*-
r"""팔콤 클래식 I·II (새턴 JP) 원본 디스크 — 파일 목록·읽기, work/disc/<디스크>/ 에 «불변 사본» 꺼내기 (2026-10-03)
  FC1 = 트랙 01(MODE1) : DRS(드래곤 슬레이어) · ZANA(재너두) · YS1(이스) + 루트 메뉴
  FC2 = 트랙 1(MODE1)  : YS2(이스 II) · SUN(아스테카 II 태양의 신전?) + 루트 로더
  python tools/disc.py   → 게임별 L/H 이미지와 로더를 work/disc/ 로
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, r'C:\claude\project\darksavior-kr-patch\tools')
sys.path.append(r'C:\claude\project\anearth-kr-patch\tools')      # cdmode1 (iso.py 가 씀)
import iso

TRACK = {
    'fc1': r'C:\claude\roms\ss\완료\Falcom Classics (Japan) (Disc 1) (Game Disc)\Falcom Classics (Japan) (Disc 1) (Game Disc) (Track 01).bin',
    'fc2': r'C:\claude\roms\ss\Falcom Classics II (Japan)\Falcom Classics II (Japan) (Track 1).bin',
}
DISC = os.path.join(ROOT, 'work', 'disc')
WANT = {
    'fc1': ['0', 'ALLENDL.BIN', 'ALLENDH.BIN', 'DRS/0DRSL.BIN', 'DRS/1DRSH.BIN', 'DRS/LLOADER3.BIN',
            'ZANA/0ZANAL.BIN', 'ZANA/1ZANAH.BIN', 'YS1/0YS1L.BIN', 'YS1/1YS1H.BIN'],
    'fc2': ['0', '0FC2LOAD.BIN', '0YS2LOAD.BIN', '0SUNLOAD.BIN', 'YS2/0YS2L.BIN', 'YS2/1YS2H.BIN',
            'SUN/0SUNL.BIN', 'SUN/1SUNH.BIN', 'SUN/0FC2L.BIN', 'SUN/1FC2H.BIN'],
}
_tree = {}


def listing(d):
    if d not in _tree:
        with open(TRACK[d], 'rb') as fh:
            _tree[d] = iso.tree(fh)
    return _tree[d]


def read(d, name):
    l, s, _, _ = listing(d)[name]
    with open(TRACK[d], 'rb') as fh:
        return iso.read_user(fh, l, (s + 2047) // 2048)[:s]


def local(d, name):
    return open(os.path.join(DISC, d, name.replace('/', '_')), 'rb').read()


def main():
    for d, names in WANT.items():
        os.makedirs(os.path.join(DISC, d), exist_ok=True)
        for nm in names:
            p = os.path.join(DISC, d, nm.replace('/', '_'))
            if not os.path.exists(p):
                open(p, 'wb').write(read(d, nm))
            print(d, nm, os.path.getsize(p))


if __name__ == '__main__':
    main()
