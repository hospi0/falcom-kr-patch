# -*- coding: utf-8 -*-
r"""팔콤 클래식 1편 배포 묶음 — dist/FalcomClassics_KR_<VER>/ : 트랙 01 xdelta + xdelta.exe + readme.txt(CP949) + 한글패치_적용.bat + zip
  (다크 세이비어 tools/make_dist.py 를 옮김) 검증: 원본 트랙 01 → xdelta 적용 → md5 = 빌드 결과(work/out/fc1) md5.
  python tools/make_dist.py   (먼저 python tools/build_fc1.py --install)
  python tools/make_dist.py fc2 → 2편 dist/FalcomClassics2_KR_<VER>/ (트랙 1, 먼저 build_fc2.py --install) — 2편은 별도 저장소 hospi0/falcom2-kr-patch
"""
import hashlib, os, shutil, subprocess, sys, zipfile
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import disc

VER = 'v0.9'
VER2 = 'v0.91'                        # 2편 (2026-10-04 에필로그 자막)
XDELTA = r'C:\claude\utils\xdelta.exe'
NAME = 'FalcomClassics_KR_' + VER
TITLE = '팔콤 클래식 (세가 새턴 일본판) 한글 패치 ' + VER
ROMNAME = 'Falcom Classics (Japan) (Disc 1) (Game Disc)'
TRACKS = 18
TNO = '01'
GAME = 'fc1'
FC2 = dict(NAME='FalcomClassics2_KR_' + VER2, TITLE='팔콤 클래식 II (세가 새턴 일본판) 한글 패치 ' + VER2,
           ROMNAME='Falcom Classics II (Japan)', TRACKS=2, TNO='1', GAME='fc2')


def md5(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''):
            h.update(b)
    return h.hexdigest().upper()


HEAD = """{tracks}개의 트랙으로 이루어진 {rom} 의
트랙 {tno}번에 패치하시면 됩니다.

원본md5 : {o}
패치md5 : {d}

입니다.
"""

BODY = """

[ 적용 방법 ]

  1) 원본 트랙 {tno} 파일을 이 폴더에 복사
       "{bin}"
  2) 한글패치_적용.bat 실행 → 이름 끝에 [KR] 이 붙은 파일이 만들어집니다
  3) 만든 파일 이름을 원본 트랙 {tno} 이름으로 바꿔 넣고, 나머지 트랙과 cue 는 그대로 쓰세요
     (트랙 {tno} 크기는 그대로라 cue 는 고칠 필요 없습니다)

  직접 적용:
    xdelta.exe -d -s "원본 트랙 {tno}" "{patch}" "결과 파일"
  (Delta Patcher 같은 xdelta3 GUI 도구로 적용해도 됩니다. 원본이 다르면 xdelta 가 적용을 거부합니다.)


[ 바뀌는 것 ]

{changes}
"""

CHANGES1 = """  - 이스 I : 대사 전부(보통 모드·오리지널 모드), 아이템·시스템 메시지, 책, 오프닝·엔딩 문장, 그림 글자
  - 제나두 : 대사·시스템 메시지, 그림 글자
  - 드래곤 슬레이어 : 그림 글자
  - 타이틀 메뉴"""

CHANGES2 = """  - 이스 II : 대사 전부, 아이템·시스템 메시지, 그림 글자(장비·아이템 제목, 저장 화면·확인창), 오프닝·중간 동영상 자막
  - 태양의 신전 아스테카 II : 대사 전부, 시스템 메시지, 그림 글자(저장 버튼·팝업·클리어 타임 화면), 에필로그 동영상 자막
  - 타이틀 메뉴"""

TAIL = """

[ 알려진 점 ]

  - 영문으로 된 장비·아이템 이름(SHORT-SWORD 등)은 원본 그대로 두었습니다.
  - 아직 끝까지 실기로 통독하지 못했습니다. 이상한 곳이 있으면 알려 주세요.
"""

BAT = r"""@echo off
chcp 949 >nul
set "XD=%~dp0xdelta.exe"
if not exist "%~dp0{bin}" (
  echo   [오류] 원본 트랙 {tno} 파일을 이 폴더에 넣어 주세요 - readme 참고.
  pause & exit /b 1
)
"%XD%" -d -f -s "%~dp0{bin}" "%~dp0{patch}" "%~dp0{kbin}"
if errorlevel 1 (
  echo   [오류] 패치 실패 - 원본이 다를 수 있습니다 - readme 의 원본md5 확인.
  pause & exit /b 1
)
echo   완료: "{kbin}"
pause
"""


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    if sys.argv[1:] == ['fc2']:
        globals().update(FC2)
    d = os.path.join(ROOT, 'dist', NAME)
    if os.path.isdir(d):
        shutil.rmtree(d)                                  # 옛 묶음(옛 xdelta) 남기지 않음
    os.makedirs(d)
    src = disc.TRACK[GAME]; b = os.path.basename(src)
    out = os.path.join(ROOT, 'work', 'out', GAME, b)
    patch = NAME + '.xdelta'; pp = os.path.join(d, patch)
    subprocess.run([XDELTA, '-e', '-9', '-f', '-B', str(1 << 29), '-s', src, out, pp], check=True)
    chk = os.path.join(d, '_check.bin')
    subprocess.run([XDELTA, '-d', '-f', '-B', str(1 << 29), '-s', src, pp, chk], check=True)
    o, want, got = md5(src), md5(out), md5(chk)
    os.remove(chk)
    assert got == want, ('패치 적용 결과가 빌드와 다름', got, want)
    kbin = ROMNAME + ' (Track %s) [KR].bin' % TNO
    shutil.copy2(XDELTA, os.path.join(d, 'xdelta.exe'))
    readme = (TITLE + '\n' + '=' * 60 + '\n\n' + HEAD.format(tracks=TRACKS, rom=ROMNAME, o=o, d=want, tno=TNO)
              + BODY.format(bin=b, patch=patch, tno=TNO, changes=CHANGES2 if GAME == 'fc2' else CHANGES1) + TAIL)
    open(os.path.join(d, 'readme.txt'), 'wb').write(readme.replace('\n', '\r\n').encode('cp949'))
    open(os.path.join(d, '한글패치_적용.bat'), 'wb').write(
        BAT.format(bin=b, patch=patch, kbin=kbin, tno=TNO).replace('\n', '\r\n').encode('cp949'))
    shutil.copy2(os.path.join(d, 'readme.txt'), os.path.join(ROOT, 'dist', 'readme.txt' if GAME == 'fc1' else 'readme_fc2.txt'))
    zp = os.path.join(ROOT, 'dist', NAME + '.zip')
    with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in sorted(os.listdir(d)):
            z.write(os.path.join(d, f), NAME + '/' + f)
    print('원본md5 %s → 패치md5 %s · %s %d B' % (o, want, patch, os.path.getsize(pp)))
    print('✅', d, '·', os.path.basename(zp), os.path.getsize(zp))
    for f in sorted(os.listdir(d)):
        print('  %-40s %12d' % (f, os.path.getsize(os.path.join(d, f))))


if __name__ == '__main__':
    main()
