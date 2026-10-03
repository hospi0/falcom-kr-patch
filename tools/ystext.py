# -*- coding: utf-8 -*-
r"""이스 I·이스 II·아스테카 대사 — 문자열 찾기 · 코드↔글자 · TSV 추출 (2026-10-03)

코드(u16 BE): 0x00‥2F 기호·숫자·영대문자 / 30‥7F 히라가나 / 80‥CF 가타카나 / D0‥DF 부호 / E0‥ 한자(게임별, work/kanji_<게임>.tsv)
제어: 0xE00+n = n px 띄움(E10 전각·E08 반각) · 0xFxx 명령 · 0xFFD 줄 · 0xFFE 페이지 · 0xFFF 끝
  python tools/ystext.py            → work/text/<게임>.tsv (파일 오프셋 끝 원문)
"""
import os, re, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
DISC = os.path.join(ROOT, 'work', 'disc')

NKANJI = {'ys1': 524, 'ys2': 634, 'ys2b': 384, 'sun': 419}
FILES = {
    'ys1': ['fc1/YS1_0YS1L.BIN'],
    'ys2': ['fc2/YS2_0YS2L.BIN'] + ['fc2/ys2/DAT0%d.BIN' % i for i in range(1, 5)],
    'sun': ['fc2/SUN_0SUNL.BIN', 'fc2/SUN_1SUNH.BIN'],
}
FILES['ys2b'] = FILES['ys2']

T0 = ['　', '０', '１', '２', '３', '４', '５', '６', '７', '８', '９', '＝', '－', '，', '．', '”'] + \
     [chr(0xFF21 + i) for i in range(26)] + ['？', '！', '（', '）', '／', '：']
HIRA = [chr(c) for c in range(0x3041, 0x3094) if chr(c) not in 'ゎゐゑ']
KATA = [chr(c) for c in range(0x30A1, 0x30F4) if chr(c) not in 'ヮヰヱヴ']
D0 = ['ヴ', 'ー', '、', '。', '…', '・', '「', '」', '『', '』', '～', '〓', '㈱', '々', 'ヵ', 'ヶ']
assert len(T0) == 48 and len(HIRA) == 80 and len(KATA) == 80
SUN_E0 = [chr(0xFF41 + i) for i in range(16)] + [chr(0xFF51 + i) for i in range(10)] + ['～', '×', '〓', '両', '量', '炉']
# ⚠️아스테카 2C = 「()」 한 칸(괄호 쌍 그림), 2D 빈칸 / DA‥DC 빈칸 — 쓰임 확인 전


def kanji_table(game):
    p = os.path.join(ROOT, 'work', 'kanji_%s.tsv' % game)
    t = {}
    if os.path.exists(p):
        for line in open(p, encoding='utf-8'):
            f = line.rstrip('\n').split('\t')
            if len(f) >= 2 and f[0][:1] != '#' and f[1]:
                t[int(f[0], 16)] = f[1]
    return t


def charmap(game):
    m = {}
    for i, c in enumerate(T0 + HIRA + KATA + D0):
        m[i] = c
    if game == 'sun':
        for i, c in enumerate(SUN_E0):
            m[0xE0 + i] = c
        m[0x2C] = '()'
    if game == 'ys2b':                         # 굵은 둘째 벌: 기호 칸이 조금 다름(00 빈칸·01‥0A 숫자는 같고 0B‥0F ＝，－（）, D0 표 DB ？ DC ！ DE Ｎ DF ”) — 영문자·．없음
        m.update({0x0B: '＝', 0x0C: '，', 0x0D: '－', 0x0E: '（', 0x0F: '）', 0xDB: '？', 0xDC: '！', 0xDE: 'Ｎ', 0xDF: '”'})
        for k in range(0x10, 0x30): m.pop(k, None)
    m.update(kanji_table(game))
    return m


def limit(game):
    return 0xE0 + NKANJI[game]


def scan(d, lim):
    """FFF 로 끝나는 연속 구간(글자 < lim · 0xE00‥FFE)을 찾는다. → [(시작, 끝(FFF 다음))]"""
    n = len(d) // 2
    v = struct.unpack('>%dH' % n, d[:n * 2])
    i = 0; out = []
    while i < n:
        j = i; txt = 0
        while j < n and (v[j] < lim or 0xE00 <= v[j] <= 0xFFE):
            if 0x30 <= v[j] < 0xD2 or 0xE0 <= v[j] < lim:
                txt += 1
            j += 1
        if j < n and v[j] == 0xFFF and txt >= 1 and j - i >= 2:
            out.append((i * 2, j * 2 + 2))
        i = j + 1
    return out


def codes(d, a, e):
    return list(struct.unpack('>%dH' % ((e - a) // 2), d[a:e]))


def decode(cs, m, unk='〔%X〕'):
    s = []
    for c in cs:
        if c == 0xFFF:
            break
        if c == 0xFFD:
            s.append('\\n')
        elif c == 0xFFE:
            s.append('\\p')
        elif c == 0xE10:
            s.append('　')
        elif c == 0xE08:
            s.append(' ')
        elif c >= 0xE00:
            s.append('{%X}' % c)
        else:
            s.append(m.get(c, unk % c))
    return ''.join(s)


OKC = {0xFE0, 0xFE2, 0xFE3, 0xFE4, 0xFE5, 0xFE6, 0xFF0, 0xFF1, 0xFF2, 0xFF3, 0xFF4, 0xFFB, 0xFFD, 0xFFE, 0xE08, 0xE10}
_RUN = re.compile(r'[ぁ-んァ-ヶー一-龥々、。・？！]{3,}|[Ａ-Ｚ]{4,}')


def is_text(cs, m):
    """잡음 걸러내기: 모르는 제어(0xE00‥) 가 없고, 글자 3자 이상 연속(또는 영대문자 4자)."""
    if any(c >= 0xE00 and c != 0xFFF and c not in OKC for c in cs):
        return False
    return bool(_RUN.search(decode(cs, m)))


# 시스템 목록 = FFD 로 이어진 줄 목록(스크립트 참조 아님). (파일, 시작, 끝, 이름) — 끝 = 다음 데이터 시작
SYSLISTS = {
    'ys1': [('fc1/YS1_0YS1L.BIN', 0x79B1C, 0x7A274, '엔딩'),
            ('fc1/YS1_0YS1L.BIN', 0x7A274, 0x7A330, '저장경고'),
            ('fc1/YS1_0YS1L.BIN', 0x7A330, 0x7A474, '오프닝'),
            ('fc1/YS1_0YS1L.BIN', 0x7A616, 0x7A6D8, '메뉴'),
            ('fc1/YS1_0YS1L.BIN', 0x7B20A, 0x7BBFE, '시스템')],
    'ys2': [('fc2/YS2_0YS2L.BIN', 0x290F0, 0x2944C, '음악'),      # 음악 감상 곡명(영어) + 인물 3
            ('fc2/YS2_0YS2L.BIN', 0x45BE2, 0x467DA, '시스템')],   # 장비·마법·아이템·상태창·지명·저장
    'sun': [('fc2/SUN_0SUNL.BIN', 0x2A998, 0x2AE9C, '시스템')],   # 저장·메뉴·지명·명령·아이템·조사 대상·저주 메시지
}


def sys_entries(game):
    """→ [(파일, 시작, 끝, 이름, 코드들)] 줄 하나씩(FFD/FFF 로 끊음)"""
    out = []
    for f, a, b, name in SYSLISTS.get(game, []):
        d = open(os.path.join(DISC, f), 'rb').read()
        cs = codes(d, a, b); cur = []; st = a
        for k, c in enumerate(cs):
            if c in (0xFFD, 0xFFF):
                out.append((f, st, a + 2 * k, name, cur)); cur = []; st = a + 2 * (k + 1)
            else:
                cur.append(c)
        if cur:
            out.append((f, st, b, name, cur))
    return out


def strings(game):
    for f in FILES[game]:
        d = open(os.path.join(DISC, f), 'rb').read()
        for a, e in scan(d, limit(game)):
            yield f, a, e, codes(d, a, e)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    os.makedirs(os.path.join(ROOT, 'work', 'text'), exist_ok=True)
    import ysrefs
    for g in FILES:
        m = charmap(g); n = 0; trim = 0; sus = []
        ref = {}; dat = {f: open(os.path.join(DISC, f), 'rb').read() for f in FILES[g]}
        for f, B, p, op, S in ysrefs.refs(g):
            ref.setdefault(f, set()).add(S)
        with open(os.path.join(ROOT, 'work', 'text', g + '.tsv'), 'w', encoding='utf-8') as fo:
            fo.write('번호\t파일\t오프셋\t끝\t원문\t번역\n')
            sysr = [(f, a, b) for f, a, b, _ in SYSLISTS.get(g, [])]
            for f, a, e, cs in strings(g):
                if any(f == sf and a < sb and e > sa for sf, sa, sb in sysr):
                    continue                    # 시스템 목록은 아래에서 줄 단위로
                rs = sorted(S for S in ref.get(f, ()) if a < S < e)
                while rs:
                    pre = cs[:(rs[0] - a) // 2]
                    bad = any(c >= 0xE00 and c not in OKC for c in pre)
                    if not (bad or a not in ref.get(f, ()) and (len(pre) <= 3 or dat[f][a - 2:a] != b'\x0f\xff')):
                        break
                    # 스캔 시작 앞이 FFF 가 아님 = 앞부분은 글자처럼 보이는 스크립트 바이트 → 참조 위치가 진짜 시작
                    cs = cs[(rs[0] - a) // 2:]; a = rs[0]; trim += 1; rs = rs[1:]
                for S in rs:
                    sus.append('%s\t%X\t%s|%s' % (os.path.basename(f), S, decode(cs[:(S - a) // 2], m)[-12:], decode(cs[(S - a) // 2:], m)[:16]))
                bad = [k for k, c in enumerate(cs) if c >= 0xE00 and c != 0xFFF and c not in OKC]
                if bad and not is_text(cs, m):          # 모르는 제어 = 앞 데이터 → 그 뒤부터 문장
                    k = bad[-1] + 1; cs = cs[k:]; a += 2 * k
                    if len(re.findall(r'[ぁ-んァ-ヶ]', decode(cs, m))) < 3:
                        continue
                if not is_text(cs, m):
                    continue
                n += 1
                fo.write('%s%04d\t%s\t%X\t%X\t%s\t\n' % (g, n, os.path.basename(f), a, e, decode(cs, m)))
            ns = 0
            for f, a, e, name, cs in sys_entries(g):
                ns += 1
                fo.write('%ss%03d\t%s\t%X\t%X\t%s\t\n' % (g, ns, os.path.basename(f), a, e, decode(cs, m) or '　'))
        with open(os.path.join(ROOT, 'work', 'text', g + '_midrefs.tsv'), 'w', encoding='utf-8') as fo:
            fo.write('# 문장 «가운데»를 가리키는 참조(가짜 일치 의심 — 되넣기 전 실기/코드로 확인)\n' + '\n'.join(sus) + '\n')
        print(g, n, '문자열 · 앞 찌꺼기 자름', trim, '· 가운데 참조', len(sus))
        write_user_tsv(g)


OUT = os.path.join(ROOT, 'my files', 'tsv')
HEAD = '번호\t위치\t개수\t원문\t번역\n'
LIMIT = 29 * 1024                   # ★파일 하나 29KB 이하(줄 수 아님)


def write_user_tsv(g):
    """번역용 사본 — 같은 원문은 한 줄(개수 = 나오는 횟수, 빌더는 원문으로 찾는다), 29KB 단위 분할."""
    os.makedirs(OUT, exist_ok=True)
    rows = [l.rstrip('\n').split('\t') for l in open(os.path.join(ROOT, 'work', 'text', g + '.tsv'), encoding='utf-8')][1:]
    first = {}; cnt = {}
    for r in rows:
        if not re.search(r'[ぁ-んァ-ヶ一-龥々]', r[4]):
            continue                    # ⛔영어·숫자만인 줄은 번역 안 함(사용자 2026-10-03) — 빌더는 원문 유지
        cnt[r[4]] = cnt.get(r[4], 0) + 1
        first.setdefault(r[4], r)
    lines = ['%04d\t%s:%s\t%d\t%s\t\n' % (k + 1, r[1], r[2], cnt[t], t) for k, (t, r) in enumerate(first.items())]
    for f in os.listdir(OUT):
        if re.match(g + r'_\d{3}\.tsv$', f):
            os.remove(os.path.join(OUT, f))
    files = []; cur = []; size = len(HEAD.encode('utf-8'))
    for ln in lines:
        b = len(ln.encode('utf-8'))
        if cur and size + b > LIMIT:
            files.append(cur); cur = []; size = len(HEAD.encode('utf-8'))
        cur.append(ln); size += b
    if cur:
        files.append(cur)
    for k, fl in enumerate(files):
        with open(os.path.join(OUT, '%s_%03d.tsv' % (g, k + 1)), 'w', encoding='utf-8', newline='\n') as f:
            f.write(HEAD + ''.join(fl))
    print('  번역용', len(lines), '줄 →', len(files), '파일')


if __name__ == '__main__':
    main()
