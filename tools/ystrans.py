# -*- coding: utf-8 -*-
r"""번역 적재 (이스 I·II·아스테카·제나두 공통, 2026-10-03)
  my files/번역/<게임>_*.tsv (번호·위치·개수·원문·번역; 칸 안 실제 줄바꿈은 \n 으로 이어 붙임)
  → work/tr_fix/<게임>.tsv 고침(번호·고칠 부분·바꿀 내용) 적용
  → 상자 폭(CAP 칸, 반각 공백 0.5) 넘는 페이지는 낱말 단위로 다시 접기(원문 페이지 줄 수 안에서만)
  → 부호 뒤 공백 1칸 삭제(전프로젝트 규칙) → 남은 넘침·글꼴에 없는 글자 검사
  python tools/ystrans.py <게임>   → 검사 결과
"""
import collections, glob, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
NL = chr(92) + 'n'; PG = chr(92) + 'p'
CTL = re.compile(r'(\{[0-9A-F]+\})')
CAP = {'ys1': 16, 'ys2': 16, 'sun': 24, 'zana': 16}
BOXLINES = {'ys1': 0, 'ys2': 0, 'sun': 2, 'zana': 0}   # 다시 접을 때 페이지 줄 수 상한(원문 줄 수와 큰 쪽)
def _zana_cap(no):
    n = int(no)
    if n <= 6: return 13                    # 시스템 메시지 창(실기 스샷: 세이브 불가 창 13칸)
    if 159 <= n <= 203: return 20           # 오프닝·엔딩 세로 글 화면(실기 스샷: 21칸에서 넘침)
    if n >= 247: return 21                  # 제작진
    return 16


ROWCAP = {'zana': _zana_cap}
LINECAP = {'zana': lambda no: 7 <= int(no) <= 158}   # 가게·도장·아이템: 줄마다 원문 그 줄 길이까지(도장·가게 창이 글 위에 겹침, 실기 스샷) — 자동 접기 안 함
SPW = {'zana': 1.0, 'ys1': 1.0, 'ys2': 1.0, 'sun': 1.0}                       # 이스 II: 공백 = 전각 0x000(16px) — E10/E08 은 «멈춤»(실기 스샷: 줄 머리 E10 이 들여쓰기 안 됨)                                   # 제나두는 반각 공백 코드가 없어 빈 칸(12px) = 1칸
PUNCT = set(',.!?:;)]}\'"~、。，．！？：；）］｝」』】〉》”’…‥・·～〜♪♥')


def load_rows(g):
    rows = []
    for f in sorted(glob.glob(os.path.join(ROOT, 'my files', '번역', g + '_*.tsv'))):
        raw = open(f, encoding='utf-8-sig').read().replace('\r\n', '\n')
        cur = None
        for l in raw.split('\n')[1:]:
            if re.match(r'^\d{4}\t', l):
                if cur is not None: rows.append(cur)
                cur = l
            elif l.strip() == '':
                continue
            else:
                cur = (cur or '') + NL + l
        if cur is not None: rows.append(cur)
    out = []
    for r in rows:
        f = r.split('\t')
        while len(f) < 5: f.append('')
        out.append({'no': f[0], 'pos': f[1], 'src': f[3], 'tr': f[4]})
    ov = load_override(g)
    for r in out:
        if r['no'] in ov:
            t = ov[r['no']]
            # ★번호 착각 막기(2026-10-04: 자물쇠 문장으로 알고 «0128 잠겨있다»를 넣었는데 0128 은 다른 대사 — 라바 층에서 «잠겨있다» 제보).
            #   오버라이드 번호 = 번역 파일 번호(추출 번호 ys1NNNN 과 다를 수 있음). 3줄 이상 대사를 1/4 길이 미만으로 덮으면 중단.
            n_old = r['tr'].count(NL) + r['tr'].count(PG) + 1
            if t != '=원문' and r['tr'] and n_old >= 3 and len(t) * 4 < len(r['tr']):
                raise SystemExit('⛔오버라이드 %s %s 가 원래 번역보다 너무 짧음(번호 착각?) — 원문 %r → %r' % (g, r['no'], r['src'][:30], t[:20]))
            if t == '=원문':
                r['tr'] = r['src']
            else:                                   # {FFB} 뒤 인자 = 원문 인자 차례대로(원래 코드값)
                args = re.findall(r'\{FFB\}(.)', r['src']); it = iter(args)
                t = re.sub(r'\{FFB\}', lambda m: '{FFB}' + next(it), t)
                r['tr'] = t
    return out


def load_override(g):
    """work/tr_override/<게임>.tsv (번호\t번역) — 받은 번역을 통째로 바꿈(이스 II 굵은 벌 대사 재번역 등)"""
    p = os.path.join(ROOT, 'work', 'tr_override', g + '.tsv'); ov = {}
    if os.path.exists(p):
        for l in open(p, encoding='utf-8'):
            if l.startswith('#') or not l.strip(): continue
            f = l.rstrip('\n').split('\t')
            ov[f[0]] = f[1]
    return ov


def load_fix(g):
    p = os.path.join(ROOT, 'work', 'tr_fix', g + '.tsv'); fx = {}
    if os.path.exists(p):
        for l in open(p, encoding='utf-8'):
            if l.startswith('#') or not l.strip(): continue
            f = l.rstrip('\n').split('\t')
            fx.setdefault(f[0], []).append((f[1], f[2]))
    return fx


def load_terms(g):
    """work/terms.tsv 용어 통일 규칙 → [(조건, 제외, 틀린, 바른)]"""
    p = os.path.join(ROOT, 'work', 'terms.tsv'); out = []
    if os.path.exists(p):
        for l in open(p, encoding='utf-8'):
            if l.startswith('#') or not l.strip(): continue
            f = l.rstrip('\n').split('\t')
            if f[0] != g: continue
            cond, _, excl = f[1].partition('!')
            out.append((cond, excl, f[2], f[3]))
    return out


def apply_terms(terms, src, tr):
    for cond, excl, a, b in terms:
        if cond in src and not (excl and excl in src):
            tr = tr.replace(a, b)
    return tr


SP = [0.5]
FWSP = [1.0]                                    # 전각 공백 폭(이스 II: 0x000 공백은 ≈0.6칸 — 실측 2026-10-04 기드 가게 85px 글자 · 52px 공백)
LAT = [1.0]                                     # 영문·숫자 폭(이스 I: 11px/16px — 실기 스샷 가게 창 «SHORT»)


def W(s):
    s = re.sub(r'\{FFB\}.', '', s)      # {FFB} 뒤 인자(초상화 번호)는 글자가 아님
    s = CTL.sub('', s)
    return sum(SP[0] if c == ' ' else FWSP[0] if c == '　' else LAT[0] if re.match(r'[A-Za-zＡ-Ｚａ-ｚ0-9０-９\-－]', c) else 1 for c in s)


def wrap_page(page, lim, punct_break=False):
    """낱말 단위로 다시 접기. ★빈 줄(공백·제어만)은 문단 경계로 그대로 둔다 — 합치면 「?　　음,」처럼 공백 덩어리가 된다(실기 2026-10-03)."""
    head = re.match(r'^((?:\{[0-9A-F]+\})*)', page).group(1)
    body = page[len(head):]
    paras = [[]]; blanks = []
    for l in body.split(NL):
        if CTL.sub('', l).strip(' 　') == '':
            paras.append(l); paras.append([])                  # 빈 줄 = 그대로
        elif l.startswith('{FF0}') or l.startswith('{E10}'):  # {FF0} = 이름표 줄 끝 → 앞 줄(이름)과 합치지 않는다(레아 「레아 처음」) · {E10} = 원문 줄 머리 들여쓰기 자리(새 문장) — 앞 줄에 붙이지 않음(기드 「인가.이놈은」 2026-10-04)
            paras.append([l])
        else:
            paras[-1].append(l)
    res = []
    for pa in paras:
        if isinstance(pa, str): res.append(pa); continue
        if not pa: continue
        w = _wrap_words(' '.join(pa), lim, punct_break)
        if w is None: return None
        res += w
    if res: res[0] = head + res[0]
    return res


def _wrap_words(body, lim, punct_break):
    toks = []                                       # (낱말, 앞에 공백?)
    for t in body.split(' '):
        if t == '' or t.strip('　') == '': continue
        if punct_break:                             # 부호 뒤(공백 없음)·강조 끝 {FE4} 뒤도 끊을 자리
            t2 = re.sub(r'([、。，．！？…・,.!?])(?![、。，．！？…・,.!?」』）)]|$)', '\\1\x00', t).replace('{FE4}', '{FE4}\x00')
            parts = [x for x in t2.split('\x00') if x] or [t]
        else:
            parts = [t]
        for k, x in enumerate(parts): toks.append((x, k == 0))
    out = []; cur = ''
    for t, sp in toks:
        if punct_break and cur and cur[-1] in PUNCT: sp = False          # 부호 뒤 공백 금지
        cand = t if cur == '' else cur + (' ' if sp else '') + t
        if W(cand) <= lim:
            cur = cand
        else:
            if cur: out.append(cur)
            if W(t) > lim: return None
            cur = t
    if cur: out.append(cur)
    return out


CUR = {'pos': '', 'src': '', 'gap': 0}
_ALLTR = {}
YS1_ORIG = (0x7D75C, 0x84E9C)                   # 이스 I 오리지널 모드 문장 묶음(16px 로 바꾼 216×54 창 = 13칸·3줄)


_CH = []


def ys1_choices():
    """이스 I 선택지 문장 = 스크립트 op 0x52 가 가리키는 문장 → {'YS1_0YS1L.BIN:오프셋'}"""
    if not _CH:
        import sys as _s; _s.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import ysrefs
        _CH.append({'%s:%X' % (os.path.basename(f), S) for f, B, p, op, S in ysrefs.refs('ys1') if op == 0x52})
    return _CH[0]


_WIN = []


def ys1_windows():
    """이스 I 문장 → 창(스크립트 004C 첫 인자: 윗바이트 = 창 종류 00 필드·01 오리지널 필드·FF 초상화 옆/집 안, 아랫바이트 = 글꼴 세트).
    대사 참조(op 50/51/52) 앞에서 같은 묶음 안 가장 가까운 004C 를 찾는다(실기 2026-10-04: 창을 원문 글자 수로 짐작했다가 「자물쇠가 걸려/있다」 등)."""
    if not _WIN:
        import sys as _s, struct
        _s.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import ysrefs
        L = open(os.path.join(ROOT, 'work', 'disc', 'fc1', 'YS1_0YS1L.BIN'), 'rb').read()
        v = struct.unpack('>%dH' % (len(L) // 2), L); w = {}
        for f, B, p, op, S in ysrefs.refs('ys1'):
            k = p // 2 - 2
            while k > B // 2:
                if v[k] == 0x4C and (v[k + 1] >> 8) in (0x00, 0x01, 0xFF) and (v[k + 1] & 0xFF) <= 5:
                    if not (op != 0x52 and v[k + 3] == 0x52): break     # 004C 바로 뒤가 선택지(op 52) = 선택지 상자 창 → 대사 창 아님(사라 「예/아니오」 실기 2026-10-04)
                k -= 1
            if k > B // 2: w.setdefault('YS1_0YS1L.BIN:%X' % S, v[k + 1])
        _WIN.append(w)
    return _WIN[0]


def _ys1_page(srcpage):
    """이스 I 쪽별 창 = 스크립트 004C 창 종류(ys1_windows). 음수 줄 수 = 원문 줄 수와 상관없이 이 줄 수까지(넘치면 쪽 나눔).
    00xx 필드 창 16칸·3줄(원문이 더 많으면 그만큼) · FF00/FF01 초상화 옆 창 9칸·6줄(원문 6‥7) · 0102 오리지널 필드 13칸·3줄 · FF03 오리지널 집 안 9칸·8줄"""
    nl = len(srcpage.split(NL))
    w = ys1_windows().get(CUR['pos'])
    if w is not None:
        hi, fs = w >> 8, w & 0xFF
        if hi == 0xFF: return (9.75, -8) if fs >= 2 else (9, -max(6, nl))   # 집 안 창 = 줄 머리부터 157px(원문 「　SILVER-ARMOR」 13×12px 가 들어감) → 한글 9자·12px 영문 13자
        # ★필드 창(00xx·01xx)은 «원문 문장 전체의 가장 긴 줄·가장 많은 줄» 크기로 미리 정해진 상자(실기 2026-10-04: 열쇠 사용 상자 7칸에서 「를」이 접힘,
        #   자물쇠 상자 1줄) → 그 폭·줄 수를 넘지 않게 접고, 넘치면 쪽을 나눈다
        sl = [CTL.sub('', re.sub(r'\{FFB\}.', '', l)) for pg in CUR['src'].split(PG) for l in pg.split(NL)]
        cw = max([len(l) for l in sl] + [1]); cl = max(len(pg.split(NL)) for pg in CUR['src'].split(PG))
        return min(13 if (hi == 0x01 or fs == 2) else 16, cw), -cl
    f, _, a = CUR['pos'].partition(':')
    if f == 'YS1_0YS1L.BIN' and a and YS1_ORIG[0] <= int(a, 16) < YS1_ORIG[1]:
        return 9, -3
    ls = [CTL.sub('', l) for l in srcpage.split(NL)]
    return (16, 3) if max(len(l) for l in ls) >= 11 else (9, 6)


def _ys2_page(info, ffb, srcpage=''):
    """이스 II 쪽별 창 폭(스샷 2026-10-03 + 원문 폭 분포). info = 원문 그 쪽 줄들 [(머리, 폭)] — 폭은 0x000 공백 포함·멈춤 제외.
    필드 창 16칸·3줄(멈춤 빼면 원문 최대 16) · 초상화({FFB} 머리) 10칸(원문 벼랑 10→11) · 원문 9칸 이하 = 집 안 오른쪽 창 9칸(스샷 실측) ·
    원문 10‥11칸 = 가게 창 등 크기 미확인 → 원문 폭 그대로(보수적)."""
    m = max(w for _, w in info)
    if ffb: return max(10, m), 3
    if m <= 9: return 9, 3
    # ★원문 10‥11칸 줄이 «끝 부호 매달기(、。？！…)·전각 영문(좁게 그려짐)» 때문이면 실제 창은 9칸(실기 2026-10-04 기드 가게:
    #   「질은 나쁘지 않아/.」·「가벼우니까/,」 — 우리 부호는 매달리지 않고 접힌다)
    def adj(l):
        l = CTL.sub('', re.sub(r'\{FFB\}.', '', l))
        if l and l[-1] in '、。，．？！…」〓㈱': l = l[:-1]
        return sum(0.7 if re.match(r'[Ａ-Ｚａ-ｚ０-９－]', c) else 1 for c in l)
    if srcpage and max(adj(l) for l in srcpage.split(NL)) <= 10: return 9, 3      # 줄 머리 공백(0x000)은 좁게 그려진다(실측 ≈0.6칸)
    if m <= 11: return m, 3
    return 16, 3


def _ys2_leads(pos):
    """원문 쪽·줄별 [(머리, 폭)]: 머리 ('sp', n) = 0x000 공백 n개(들여쓰기·커서 자리) · ('pause',) = E10/E08 멈춤 · None"""
    import struct, itertools
    f, a = pos.split(':'); a = int(a, 16)
    path = os.path.join(ROOT, 'work', 'disc', 'fc2', 'YS2_0YS2L.BIN' if f == 'YS2_0YS2L.BIN' else os.path.join('ys2', f))
    d = open(path, 'rb').read(); pages = [[]]; cur = []; i = a
    def lead(cs):
        if cs and cs[0] == 0: return ('sp', len(cs) - len(list(itertools.dropwhile(lambda c: c == 0, cs))))
        if cs and cs[0] in (0xE10, 0xE08): return ('pause',)
        return None
    while True:
        c = struct.unpack_from('>H', d, i)[0]; i += 2
        if c == 0xFFB: i += 2; continue
        if c in (0xFFD, 0xFFE, 0xFFF):
            pages[-1].append((lead(cur), sum(1 for x in cur if x < 0xE00))); cur = []
            if c == 0xFFE: pages.append([])
            if c == 0xFFF: return pages
            continue
        if 0xF00 <= c < 0xFFD and not cur: continue          # 줄 머리 명령은 건너뜀
        cur.append(c)


def ys2_spaces(tr, pos):
    """이스 II 공백: 줄 머리 = 원문 그 줄이 0x000 공백이면 같은 수의 전각 공백, 아니면 {E10}(멈춤 — 화면엔 안 보임).
    줄 안 = 공백 덩어리 하나 → 공백 하나(0x000), 전각 두 칸 이상(칸 맞춤)은 그대로. 줄 끝 공백 삭제."""
    leads = _ys2_leads(pos)
    out = []
    for pi, pg in enumerate(tr.split(PG)):
        ls = []
        for li, l in enumerate(pg.split(NL)):
            m = re.match(r'^((?:\{FFB\}.|\{[0-9A-F]+\})*)', l); head = m.group(1); body = l[len(head):]
            lead = re.match(r'^[ 　]+', body)
            body = re.sub(r'[ 　]+', lambda x: x.group(0) if x.group(0).count('　') >= 2 else ' ', body.strip(' 　'))
            if lead:
                o = leads[pi][li][0] if pi < len(leads) and li < len(leads[pi]) else None
                body = ('　' * o[1] if o and o[0] == 'sp' else '{E10}') + body
            ls.append(head + body)
        out.append(NL.join(ls))
    return PG.join(out)


PAGEBOX = {'ys1': _ys1_page}


def fit_ys2(tr, src, pos):
    """이스 II: 창 폭(_ys2_page)으로 접고, 창 줄 수(원문 그 쪽 줄 수와 창 기본 중 큰 쪽)를 넘으면 «쪽을 나눈다»(FFE = 버튼 대기).
    나눈 쪽 머리엔 {FFB}x(초상화)만 되풀이. 번역 쪽이 원문보다 많으면 원문 마지막 쪽의 창으로 잰다."""
    sp = src.split(PG); info = _ys2_leads(pos); res = []; bad = []
    for i, p in enumerate(tr.split(PG)):
        k0 = min(i, len(sp) - 1)
        lim, boxl = _ys2_page(info[k0], sp[k0].startswith('{FFB}'), sp[k0])
        maxl = max(len(info[k0]), boxl)
        if lim == 9 and len(info[k0]) > 3 and not sp[k0].startswith('{FFB}'): maxl = max(maxl, 8)   # 집·가게 오른쪽 창 = 9칸·8줄(실기 2026-10-04 기드 가게 8줄 보임). 원문 3줄 이하 쪽은 필드 창일 수 있어 그대로
        lines = p.split(NL)
        if re.match(r'^(?:\{FE0\})?\{FF1\}', src):                    # ★{FF1} 상자 = 원문 크기로 미리 정해진 상자(실기 2026-10-04: 「바노아의/집」·「생명의/약」)
            ow = max(w for pg in info for _, w in pg)
            if len(sp[k0].split(NL)) > 1 and all(CTL.sub('', l).startswith('　') for l in sp[k0].split(NL)[1:]):   # 선택 목록 — 접지 않음, 원문 폭 검사
                res.append(p); bad.extend(l for l in lines if W(l) > ow); continue
            if len(sp) == 1 and NL not in src:                         # 한 줄 상자(집·가게 이름·알림) — 원문 폭 한 줄에 «들어가야 함»(접으면 쪽이 갈림)
                res.append(p); bad.extend(l for l in lines if W(l) > ow); continue
        if any(l.startswith('{FF1}') for l in lines[1:]):           # 선택지 목록(줄마다 {FF1}) — 접지도 나누지도 않음, 폭만 검사(필드 창 16)
            res.append(p); bad.extend(l for l in lines if W(l) > max(lim, 16)); continue
        if all(W(l) <= lim for l in lines) and len(lines) <= maxl:
            res.append(p); continue
        w = lines if all(W(l) <= lim for l in lines) else wrap_page(p, lim, True)
        if w is None:
            res.append(p); bad.extend(l for l in lines if W(l) > lim); continue
        ffb = re.match(r'^(?:\{[0-9A-F]+\})*?(\{FFB\}.)', p)
        for k in range(0, len(w), maxl):
            chunk = w[k:k + maxl]
            if k and ffb: chunk[0] = ffb.group(1) + chunk[0]
            res.append(NL.join(chunk))
    return PG.join(res), bad


def fit(tr, src, lim, boxl=0, g=None):
    sp = src.split(PG); tp = tr.split(PG); res = []; bad = []
    lim0 = lim
    for i, p in enumerate(tp):
        lines = p.split(NL)
        lim = lim0
        sl = sp[i].split(NL) if i < len(sp) else []
        if g == 'ys1' and len(sl) >= 2 and all(l.startswith('　') for l in sl) and not sl[0].startswith('　　　') and '　' not in sl:     # 선택지 목록(줄마다 커서 자리 공백) — 접지 않음, 창 폭 = 원문 최대 줄
            cap = max(len(CTL.sub('', l)) for l in sl)
            res.append(p); bad.extend(l for l in lines if W(l) > cap)
            if len(lines) != len(sl): bad.append('선택지 줄 수 %d≠%d' % (len(lines), len(sl)))
            continue
        if g in PAGEBOX and i < len(sp):
            lim, boxl = PAGEBOX[g](sp[i])
        if g == 'ys1' and boxl == -3 and CUR['pos'] in ys1_choices():
            res.append(p); bad.extend(l for l in lines if W(l) > lim)     # 오리지널 모드 선택지(스크립트 op 0x52 가 부르는 문장) — 접지도 나누지도 않음
            if len(lines) > 8: bad.append('집 안 창 8줄 초과 %d' % len(lines))   # 144×142 창, 16px 줄 간격 18 → 8줄(실기 2026-10-03)
            continue
        if g == 'ys1' and lim == 9.75:
            # ★오리지널 집 안 창: 원문 앞쪽 «간격용 빈 줄»(12px 시절 배치)은 16px 에선 빈 공간만 커진다(실기 2026-10-04 「당신은 그런 걸」 위 빈 줄 4개)
            #   → 쪽 머리 빈 줄은 전부 빼고, 이름 줄({FE0} 머리) 아래 빈 줄은 1개만. 빈 줄 안의 제어 코드는 다음 줄 머리로 옮긴다.
            out, pend, seen, hdr, blank_run = [], '', False, False, 0
            for l in lines:
                ctl = ''.join(re.findall(r'\{[0-9A-F]+\}', l))
                if CTL.sub('', l).strip(' 　') == '' and not seen:
                    if hdr and blank_run == 0:
                        out.append(pend + l); pend = ''; blank_run = 1
                    else:
                        pend += ctl; CUR['gap'] += 1
                    continue
                if l.startswith('{FE0}') and not out and not hdr: hdr = True          # 이름 줄(쪽 첫 줄, {FE0} 머리)
                else: seen = True                                                    # 본문 시작 — 이 뒤 빈 줄은 문단 구분이라 그대로
                out.append(pend + l); pend = ''
            if pend: out.append(pend)
            lines = out; p = NL.join(lines)
        hard = boxl < 0
        if hard: boxl = -boxl
        if all(W(l) <= lim for l in lines) and not (hard and len(lines) > boxl):
            res.append(p); continue
        maxl = boxl if hard else max(len(sp[i].split(NL)) if i < len(sp) else len(lines), len(lines), boxl)
        w = (lines if all(W(l) <= lim for l in lines) else wrap_page(p, lim, g in ('ys2', 'ys1', 'sun')))
        if w is not None and g == 'ys1' and lim == 9.75 and len(w) > maxl:
            # ★오리지널 집 안 창: 원문은 12px·10줄 기준이라 이름 줄 아래 «간격용 빈 줄»을 둔다 → 16px 8줄에 넘치면 그 빈 줄부터 뺀다
            #   (화면 종류 규칙 — 사용자 2026-10-04 «ㄱ», 오리지널 선택지 간격 빈 줄과 같은 결정). 그래도 넘치면 아래에서 쪽 나눔
            k = next((j for j, l in enumerate(w) if '{FE2}' in l), None)
            j = (k or 0) - 1
            while len(w) > maxl and j >= 1 and CTL.sub('', w[j]).strip(' 　') == '':
                del w[j]; CUR['gap'] += 1; j -= 1
        if w is not None and len(w) <= maxl:
            res.append(NL.join(w))
        elif w is not None and g in ('ys1', 'sun'):                   # 이스 I: 줄 수 넘치면 쪽 나눔(FFE = 버튼 대기)
            ffb = re.match(r'^(?:\{[0-9A-F]+\})*?(\{FFB\}.)', p)
            if g == 'ys1' and lim == 9.75:                            # 집 안 창: 나눈 쪽이 빈 줄로 시작하지 않게(빈 줄은 쪽 경계에서 버림, 제어 코드는 다음 줄로)
                pages, cur, pend = [], [], ''
                for l in w:
                    if not cur and pages and CTL.sub('', l).strip(' 　') == '':
                        pend += ''.join(re.findall(r'\{[0-9A-F]+\}', l)); CUR['gap'] += 1; continue
                    cur.append(pend + l); pend = ''
                    if len(cur) == maxl: pages.append(cur); cur = []
                if cur or pend: pages.append(cur or [pend])
                res.extend(NL.join(c) for c in pages)
                continue
            for k in range(0, len(w), maxl):
                ch = w[k:k + maxl]
                if k and ffb: ch[0] = ffb.group(1) + ch[0]
                res.append(NL.join(ch))
        else:
            res.append(p); bad.extend(l for l in lines if W(l) > lim)
    return PG.join(res), bad



def _ys2_latin_names(tr):
    """이스 II 영문 장비 이름(원문 그대로)이 원문처럼 «－» 앞뒤 두 줄로 쪼개져 있으면 한 줄로 붙이고(사용자 2026-10-04 «무기 중간 -에서 무조건 줄바꿈»),
    이름+꼬리가 가게 창 9칸을 넘으면 꼬리를 띄어 쓸 수 있는 말로 바꿔 다음 줄로 넘긴다(조사만 혼자 줄 머리에 남지 않게):
    군./이군?/군?/요？/인가. → « 말이군./말이군?/말이죠？/말인가.» · 는/은(뒤에 값) → « 가격은»"""
    BS = chr(92)
    def lat(x): return re.search('[Ａ-Ｚ]', x) and not re.search('[가-힣ぁ-んァ-ヶ一-龥]', x)
    tr = re.sub(r'\{FE3\}([^{' + BS * 2 + r']+?)' + BS * 2 + r'n[ 　]+([^{' + BS * 2 + r']+?)\{FE4\}',
                lambda m: '{FE3}' + m.group(1).strip(' 　') + m.group(2).strip(' 　') + '{FE4}' if lat(m.group(1) + m.group(2)) else m.group(0), tr)
    TAIL = {'군.': ' 말이군.', '이군?': ' 말이군?', '군?': ' 말이군?', '요？': ' 말이죠？', '인가.': ' 말인가.', '는': ' 가격은', '은': ' 가격은', '는,': ' 가격은,'}
    def fix(m):
        name, tail = m.group(1), m.group(2)
        if not lat(name) or W(name) + W(tail) <= 9 or tail not in TAIL: return m.group(0)
        return '{FE3}' + name + '{FE4}' + TAIL[tail]
    return re.sub(r'\{FE3\}([^{' + BS * 2 + r']+)\{FE4\}([^ ' + BS * 2 + r'{]+)', fix, tr)

def restore_brackets(src, tr):
    """원문 『』「」 를 번역이 '…' / "…" 로 바꿔 놓았으면 원래 괄호로 되돌린다(원문 토큰 보존 — 사용자 규칙)"""
    for (o, c), q in ((('『', '』'), "'"), (('「', '」'), '"')):
        need = src.count(o) - tr.count(o)
        while need > 0:
            m = re.search(re.escape(q) + '([^' + re.escape(q) + ']+?)' + re.escape(q), tr)
            if not m: break
            tr = tr[:m.start()] + o + m.group(1) + c + tr[m.end():]; need -= 1
    return tr


def token_check(src, tr):
    """★원문 토큰 보존 검사(사용자 규칙 — 쓰는 순간 강제): 제어 코드 {FFx}/{FEx}·『』「」 괄호·빈 줄 수가 원문보다 줄면 안 된다
    ({FFB} 는 쪽 나눔 때 되풀이하므로 «원문 이상», 나머지 제어 코드는 «같음») → 틀린 항목 목록"""
    bad = []
    def ctl(s): return collections.Counter(re.findall(r'\{(F[0-9A-F]{2})\}', s))
    cs, ct = ctl(src), ctl(tr)
    for k in set(cs) | set(ct):
        if (ct[k] < cs[k]) if k == 'FFB' else (ct[k] != cs[k]): bad.append('제어 코드 {%s} %d≠%d' % (k, cs[k], ct[k]))
    for ch in '『』「」':
        if tr.count(ch) < src.count(ch): bad.append('괄호 %s %d>%d' % (ch, src.count(ch), tr.count(ch)))
    def blanks(s): return sum(1 for l in re.split(chr(92) + '[np]', s) if CTL.sub('', re.sub(r'\{FFB\}.', '', l)).strip(' 　') == '')
    if blanks(tr) < blanks(src): bad.append('빈 줄 %d>%d' % (blanks(src), blanks(tr)))
    return bad


def depunct(s):
    out = []; i = 0
    while i < len(s):
        out.append(s[i])
        if s[i] in PUNCT and i + 1 < len(s) and s[i + 1] == ' ' and not (i + 2 < len(s) and s[i + 2] == ' '):
            i += 2; continue
        i += 1
    return ''.join(out)


def translations(g, lim=None):
    """→ {원문: 번역}(고침·접기·부호 공백 처리 끝난 것), 문제 목록"""
    lim0 = lim or CAP[g]; fx = load_fix(g); terms = load_terms(g); res = {}; probs = []; SP[0] = SPW.get(g, 0.5); LAT[0] = 0.75 if g in ('ys1', 'ys2') else 1.0; FWSP[0] = 1.0  # ★이스 II 공백 0x000 = 16px 한 칸(2026-10-04 실기 레구스 대사: 글자 시작 간격으로 재면 정확히 1칸 — 옛 0.6칸은 잉크 틈을 잰 오측. 0.75 로 세면 16칸 넘쳐 엔진이 «부탁|이|있네» 로 되접음)
    for r in load_rows(g):
        lim = ROWCAP[g](r['no']) if g in ROWCAP and lim0 == CAP[g] else lim0
        src, tr = r['src'], r['tr']
        if not tr.strip() or '〔' in src or tr == src:
            continue
        if re.search(r'[ぁ-んァ-ヶ]', re.sub(r'\{FFB\}.', '', tr)) and not re.search(r'[가-힣]', tr):
            probs.append((r['no'], '데이터 줄로 보고 건너뜀', src[:20])); continue
        for a, b in fx.get(r['no'], []):
            if a not in tr:
                probs.append((r['no'], '고침 대상 없음', a)); continue
            tr = tr.replace(a, b)
        tr = apply_terms(terms, src, tr)                       # 용어 통일(work/terms.tsv)
        tr = restore_brackets(src, tr)                         # 원문 『』「」 되살리기
        tr = re.sub('(하달|토바|다비|메사|젠마|팩트|팍트)[ 　]?(?:의)?[ 　]?(?:장|서)(?=[에은는이을를과와도만로의]|[^가-힣]|$)', lambda m: m.group(1) + '의장', tr)   # 장 이름 «~의장» 통일(사용자 2026-10-03)
        tr = depunct(tr)
        tr = re.sub('・(?:[ 　]?・)+', lambda m: '…' * -(-m.group(0).count('・') // 3), tr)   # ・・・ → … 한 칸(사용자 2026-10-03)
        if re.search('[가-힣]', tr): tr = tr.replace('。', '.')      # 한국어 문장에 일본어 마침표 금지(실기 2026-10-04 「사용했다。」)
        if g == 'ys2':
            # ⛔영문 장비 이름은 번역하지 않는다(사용자 2026-10-04 「기드 가게도 영문으로」): 원문 {FE3}…{FE4} 가 영문뿐이면 원문 그대로(줄 쪼갬 포함),
            #   선택 목록({FF1} 줄마다 커서 공백)의 영문뿐인 줄도 원문 그대로
            _lat = lambda x: not re.search(r'[ぁ-んァ-ヶ一-龥]', x) and re.search(r'[Ａ-Ｚ]', x)
            _sseg = re.findall(r'\{FE3\}(.*?)\{FE4\}', src); _it = iter(_sseg)
            if len(_sseg) == len(re.findall(r'\{FE3\}(.*?)\{FE4\}', tr)):
                tr = re.sub(r'\{FE3\}(.*?)\{FE4\}', lambda mm: (lambda s0: '{FE3}' + (s0 if _lat(s0) else mm.group(1)) + '{FE4}')(next(_it)), tr)
            if src.startswith('{FF1}') and NL in src and PG not in src:
                _sl, _tl = src.split(NL), tr.split(NL)
                if len(_sl) == len(_tl):
                    tr = NL.join(s0 if k and _lat(s0) else t0 for k, (s0, t0) in enumerate(zip(_sl, _tl)))
            tr = ys2_spaces(tr, r['pos'])
            _f, _a = r['pos'].split(':')
            if _f == 'YS2_0YS2L.BIN' and 0x45BE2 <= int(_a, 16) < 0x467DC:   # 시스템 목록(획득 창 꼬리 등)은 E10 이 멈춤이 아니라 다음 글자를 먹는다(실기 2026-10-04 「바노아 편지 / 득」) → 진짜 공백
                tr = tr.replace('{E10}', '　')
                if re.fullmatch('[^　]　.+', src):            # ★획득 창 꼬리 「を　手に入れた。」 = [이름 줄에 붙는 1자][버려지는 1자 — 줄바꿈][둘째 줄]
                    tr = '　　' + tr.strip(' 　')          #   (실기 2026-10-04 「바노아 편지 / 득」: 둘째 자리 「획」이 버려짐) → 빈칸 두 개 뒤에 둘째 줄
            # 원문이 긴 영문 이름을 두 줄로 쪼갠 자리(「ＳＨＯＲＴ／　　　－ＳＷＯＲＤ」) — «한글» 이름이면 한 줄로 붙인다(실기 2026-10-04 「숏/　　소드인가」). 줄 머리 공백 처리 뒤에 해야 줄 번호가 안 어긋남
            tr = re.sub(r'\{FE3\}([^{\\]+?)\\n[ 　]+([^{\\]+?)\{FE4\}', lambda mm: mm.group(0) if not re.search('[가-힣]', mm.group(0)) else '{FE3}' + mm.group(1).strip(' 　') + (' ' if (mm.group(1).strip(' 　') + ' ' + mm.group(2).strip(' 　')) in _ALLTR.setdefault(g, chr(10).join(x['tr'] for x in load_rows(g))) else '') + mm.group(2).strip(' 　') + '{FE4}', tr)
            tr = _ys2_latin_names(tr)
        CUR['pos'] = r['pos']; CUR['src'] = src; CUR['gap'] = 0
        if g in LINECAP and LINECAP[g](r['no']):
            so, to = src.split(NL), tr.split(NL); bad = []
            if len(to) > len(so): bad.append('줄 수 %d>%d' % (len(to), len(so)))
            for i, l in enumerate(to):
                cap = max(4, len(so[i])) if i < len(so) else 0
                if W(l) > cap: bad.append('%s(%.0f>%d)' % (l, W(l), cap))
            for l in bad: probs.append((r['no'], '줄 폭', l))
        else:
            if g == 'ys2' and r['pos'].startswith('YS2_0YS2L.BIN:') and 0x45BE2 <= int(r['pos'].split(':')[1], 16) < 0x467DC:
                bad = []                                       # 시스템 목록 줄(이름 칸·메시지)은 접지 않는다 — 길이는 빌더가 원문 글자 수로 검사
            else:
                tr, bad = fit_ys2(tr, src, r['pos']) if g == 'ys2' else fit(tr, src, lim, BOXLINES[g], g)
        if not (g in LINECAP and LINECAP[g](r['no'])):
            for l in bad: probs.append((r['no'], '폭 넘침 %.1f' % W(l), l))
        orig_choice = g == 'ys1' and r['pos'] in ys1_choices() and YS1_ORIG[0] <= int(r['pos'].split(':')[1], 16) < YS1_ORIG[1]
        for b in token_check(src, tr):
            if orig_choice and b.startswith('빈 줄'): continue
            if b.startswith('빈 줄') and CUR['gap'] and (lambda x: x[0] - x[1])([int(v) for v in re.findall(r'\d+', b)]) <= CUR['gap']: continue   # 집 안 창 간격 빈 줄 뺀 만큼(위 fit)      # 오리지널 선택지 화면은 간격 빈 줄을 뺀다(사용자 결정 2026-10-03, 화면 종류 규칙)
            probs.append((r['no'], '원문 토큰', b))
        res[src] = tr
    pa = os.path.join(ROOT, 'work', 'tr_add', g + '.tsv')     # 추출 거름(가나 3자 미만)에 빠진 짧은 문장 — 내가 번역
    if os.path.exists(pa):
        for l in open(pa, encoding='utf-8'):
            if l.startswith('#') or not l.strip(): continue
            src, tr = l.rstrip('\n').split('\t')[:2]
            res.setdefault(src, depunct(apply_terms(terms, src, tr)))
    tok = [x for x in probs if x[1] == '원문 토큰']
    if tok and __name__ != '__main__':                 # ★원문 토큰(제어 코드·『』「」·빈 줄)이 빠진 번역은 빌드 금지(사용자 규칙 2026-10-03)
        raise SystemExit('⛔%s 원문 토큰 빠진 번역 %d: %s' % (g, len(tok), tok[:5]))
    return res, probs


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    g = sys.argv[1]
    t, p = translations(g)
    print(g, '번역', len(t), '문제', len(p))
    for x in p[:40]: print('  ', x)
