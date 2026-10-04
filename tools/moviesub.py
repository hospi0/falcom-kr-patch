# -*- coding: utf-8 -*-
r"""이스 II 동영상 자막 굽기 (2026-10-04, 유나 리믹스 tools/moviesub.py·movenc.py 를 옮김)
  자막 표: work/movie/subs.tsv — 영상 · 시작 · 끝 · 원문 · 번역(«\n» = 한 자막 안 줄바꿈) · 비고
  영상: FILM(Cinepak) 288×192 · 10fps · 띠 1개 · «모든 프레임이 키 프레임» → 자막이 덮인 프레임만 한 장씩 다시 굽는다.
  시간: 표의 [시작, 끝] 을 쓰되 읽을 시간(글자×0.15초 + 0.8초, 최소 1.2초)보다 짧으면 다음 자막 앞까지 늘림.
  글씨: 나눔고딕 Bold 14px 흰색 + 검은 1px 테두리, 화면 아래 가운데(줄 간격 17px), 부호 뒤 공백 1칸 삭제.
  굽기: ffmpeg cinepak(띠 1개, 전부 키)로 global_quality 사다리를 한 번에 굽고 → 프레임마다 «원본 프레임 바이트(+앞에서 남긴 몫)» 안에
        드는 가장 좋은 판을 고른다 → 새턴식 변환(tools/filmcpk.py) → work/movie/kr/<영상>(원본 크기로 0 채움, 디스크 제자리).
  영상 크기·줄 간격·일본어 띠 = SPEC(기본 288×192). 띠가 있으면 그 행 아래를 모든 프레임에서 검게 지우고 쓴다(SUN_EPILOGUE).
  디스크: YS2/MOV01 = SUN/YS2OP.CAK(같은 파일) · YS2/MOV02 · SUN/EPILOGUE.CAK — tools/build_fc2.py 가 work/movie/kr/ 에 있으면 넣는다.
  미리보기: work/movie/kr/<영상>_kr.mp4
  python tools/moviesub.py [영상 …]   (없으면 표의 영상 전부)
"""
import glob, os, re, shutil, subprocess, sys
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import filmcpk

FFBIN = r'C:\claude\utils\ffmpeg-9.0.1-essentials_build\bin'
FONT = r'C:\claude\utils\font\nanum-gothic\NanumGothicBold.ttf'
PX, W, H, FPS = 14, 288, 192, 10
TSV = os.path.join(ROOT, 'work', 'movie', 'subs.tsv')
SRC = os.path.join(ROOT, 'work', 'movie', 'fc2')
OUT = os.path.join(ROOT, 'work', 'movie', 'kr')
DISC = {'YS2_MOV01': ['YS2/MOV01', 'SUN/YS2OP.CAK'], 'YS2_MOV02': ['YS2/MOV02'], 'SUN_EPILOGUE.CAK': ['SUN/EPILOGUE.CAK']}
# 영상별 판: 크기 · 줄 간격 · 일본어 자막 띠(행 시작 — 이 행부터 아래를 모든 프레임에서 검게 지운다, 없으면 None)
SPEC = {'SUN_EPILOGUE.CAK': dict(w=272, h=176, lh=14, band=127, bot=10)}      # 2026-10-04 태양의 신전 에필로그, 일본어가 띠에 구워져 있음


def spec(name):
    return dict(dict(w=W, h=H, lh=17, band=None, bot=12), **SPEC.get(name, {}))
PUNCT_SP = re.compile(r'([,.!?:;)\]}\'"~、。，．！？：；）］｝」』】〉》”’…‥・·～〜♪♥]) (?! )')
BORROW = 65536                        # 프레임 사이에 빌려 쓸 수 있는 바이트(2026-10-04 오프닝 0:30 «이스의 책을…» 뭉개짐)
LADDER = (0, 1000, 2000, 4000, 7000, 12000, 20000, 35000, 60000, 100000, 200000)   # ★-q:v 는 cinepak 에 거의 안 먹음 → global_quality(λ)


def secs(t):
    m, s = t.split(':')
    return int(m) * 60 + float(s)


def rows():
    out = {}
    for ln in open(TSV, encoding='utf-8'):
        if ln.startswith('#') or not ln.strip():
            continue
        c = ln.rstrip('\n').split('\t')
        lines = [PUNCT_SP.sub(r'\1', p.strip()) for p in c[4].split('\\n')]
        out.setdefault(c[0], []).append((secs(c[1]), secs(c[2]), lines))
    return out


def events(rs, dur):
    ev = []
    for k, (s, e, lines) in enumerate(rs):
        nxt = rs[k + 1][0] if k + 1 < len(rs) else dur
        need = max(sum(len(p) for p in lines) * 0.15 + 0.8, 1.2)
        end = min(max(e, s + need), nxt - 0.05, dur - 0.05)
        ev.append((s, end, lines))
    return ev


def plate(lines, F, sp):
    w, h, lh = sp['w'], sp['h'], sp['lh']
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    for ln in lines:
        assert d.textlength(ln, font=F) <= w - 12, ('줄 넘침', ln)
    y = h - sp['bot'] - (len(lines) - 1) * lh
    if sp['band'] is not None:
        assert y - 8 >= sp['band'], ('띠 넘침', lines)
    for ln in lines:
        d.text((w / 2, y), ln, font=F, anchor='mm', fill=(255, 255, 255), stroke_width=1, stroke_fill=(0, 0, 0)); y += lh
    px = im.load()
    for yy in range(h):
        for xx in range(w):
            r, g, b, a = px[xx, yy]
            px[xx, yy] = (r, g, b, 255) if a >= 128 else (0, 0, 0, 0)     # 반투명 없이(cinepak 에서 번짐 줄임)
    return im


def frames(name):
    fr = os.path.join(ROOT, 'work', 'movie', 'frames', name.lower())
    if not glob.glob(os.path.join(fr, 'f*.png')):
        os.makedirs(fr, exist_ok=True)
        subprocess.run([os.path.join(FFBIN, 'ffmpeg.exe'), '-v', 'error', '-y', '-i', os.path.join(SRC, name),
                        '-fps_mode', 'passthrough', os.path.join(fr, 'f%04d.png')], check=True)
    return fr


def encode_all(paths, q, tmp):
    """paths(프레임 png) 를 한 번에 cinepak(띠 1개·전부 키) → 새턴식 프레임 목록"""
    for f in glob.glob(os.path.join(tmp, '*')):
        os.remove(f)
    for i, p in enumerate(paths):
        shutil.copyfile(p, os.path.join(tmp, 'g%05d.png' % (i + 1)))
    avi = os.path.join(tmp, 'o.avi')
    subprocess.run([os.path.join(FFBIN, 'ffmpeg.exe'), '-v', 'error', '-y', '-framerate', str(FPS), '-i', os.path.join(tmp, 'g%05d.png'),
                    '-c:v', 'cinepak', '-min_strips', '1', '-max_strips', '1', '-max_extra_cb_iterations', '4', '-g', '1']
                   + (['-global_quality', str(q)] if q else []) + [avi], check=True)
    pk = filmcpk.avi_packets(open(avi, 'rb').read())
    assert len(pk) == len(paths), (len(pk), len(paths))
    return [filmcpk.to_saturn(p, True) for p in pk]


def burn(name, ev, log):
    fr = frames(name)
    nf = len(glob.glob(os.path.join(fr, 'f*.png')))
    kr = os.path.join(fr, 'kr'); os.makedirs(kr, exist_ok=True)
    for f in glob.glob(os.path.join(kr, 'f*.png')):
        os.remove(f)
    F = ImageFont.truetype(FONT, PX); sp = spec(name); y0 = sp['band']
    pls = {}; changed = []
    for a, b, lines in ev:
        pl = plate(lines, F, sp)
        for f in range(nf):
            if a <= f / FPS < b:
                pls[f] = pl
    for f in range(nf):
        im = Image.open(os.path.join(fr, 'f%04d.png' % (f + 1))).convert('RGBA')
        erase = y0 is not None and max(im.crop((0, y0 + 2, im.width, im.height)).convert('L').getdata()) > 40   # 일본어 잉크(옅어지는 중 포함)
        if f not in pls and not erase:
            continue
        if y0 is not None:
            im.paste((0, 0, 0, 255), (0, y0, im.width, im.height))
        if f in pls:
            im.alpha_composite(pls[f])
        im.convert('RGB').save(os.path.join(kr, 'f%04d.png' % (f + 1))); changed.append(f)
    src = os.path.join(SRC, name); size = os.path.getsize(src)
    film = filmcpk.read(open(src, 'rb').read())
    vid = [i for i, e in enumerate(film['stab']) if e[2] != 0xFFFFFFFF]
    assert len(vid) == nf, (len(vid), nf)
    assert all(not film['stab'][i][2] & 0x80000000 for i in vid), '키 아닌 프레임이 있음'
    tmp = os.path.join(ROOT, 'work', 'movie', '_enc'); os.makedirs(tmp, exist_ok=True)
    paths = [os.path.join(kr, 'f%04d.png' % (f + 1)) for f in changed]
    cand = {q: encode_all(paths, q, tmp) for q in LADDER}               # q → 새턴식 프레임 목록(changed 순서)
    log('  gq 사다리 %d단 굽기 끝' % len(LADDER))
    budget = [len(film['chunks'][vid[f]]) for f in changed]
    lv = [0] * len(changed)                                              # 모두 최고 화질에서 시작
    size_at = lambda k: len(cand[LADDER[lv[k]]][k])
    while True:                                                          # 앞당겨 쓴 몫 > BORROW 이거나 끝에서 넘치면 → 그 앞 가장 큰 프레임을 한 단 낮춘다
        over, bad = 0, None
        for k in range(len(changed)):
            over += size_at(k) - budget[k]
            if over > BORROW:
                bad = k; break
        if bad is None and over > 0:
            bad = len(changed) - 1
        if bad is None:
            break
        ks = [k for k in range(bad + 1) if lv[k] < len(LADDER) - 1]
        if not ks:
            raise SystemExit('⚠자리 부족 — 사다리 끝까지 낮춰도 넘침')
        lv[max(ks, key=size_at)] += 1
    chunks = list(film['chunks']); used = {}
    for k, f in enumerate(changed):
        q = LADDER[lv[k]]; chunks[vid[f]] = cand[q][k]; used[q] = used.get(q, 0) + 1
    assert all(len(c) % 4 == 0 for c in chunks), '4 바이트 정렬 아님'
    infos = [e[2] for e in film['stab']]
    data = filmcpk.write(film, chunks, infos)
    assert len(data) <= size, ('자리 초과', len(data), size)
    os.makedirs(OUT, exist_ok=True)
    dst = os.path.join(OUT, name)
    open(dst, 'wb').write(data + bytes(size - len(data)))
    log('%s 프레임 %d/%d 에 자막 · gq 분포 %s · %d B(원본 %d)' % (name, len(changed), nf, dict(sorted(used.items())), len(data), size))
    return dst


def preview(name):
    subprocess.run([os.path.join(FFBIN, 'ffmpeg.exe'), '-v', 'error', '-y', '-i', os.path.join(OUT, name),
                    '-vf', 'scale=%d:%d:flags=neighbor' % (spec(name)['w'] * 3, spec(name)['h'] * 3), '-c:v', 'libx264', '-crf', '16', '-pix_fmt', 'yuv420p',
                    '-c:a', 'aac', '-b:a', '192k', os.path.join(OUT, name + '_kr.mp4')], check=True)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    allr = rows()
    names = sys.argv[1:] or sorted(allr)
    log = lambda *a: print(*a, flush=True)
    for name in names:
        dur = len(glob.glob(os.path.join(frames(name), 'f*.png'))) / FPS
        ev = events(allr[name], dur)
        log('== %s 자막 %d개 (%.1f초)' % (name, len(ev), dur))
        for a, b, t in ev:
            log('   %6.2f‥%6.2f  %s' % (a, b, ' / '.join(t)))
        burn(name, ev, log)
        preview(name)


if __name__ == '__main__':
    main()
