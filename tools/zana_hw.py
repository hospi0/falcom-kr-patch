# -*- coding: utf-8 -*-
r"""제나두 반각(1바이트) 아이템 이름 → 영문 표기 (2026-10-03 사용자 결정 «1» = 영문)
  ZANA/1ZANAH.BIN 이름 칸 20 B 고정(가타카나 표). 반각 글꼴(8×16)에 있는 글자만 쓴다: A‥Z a‥z 0‥9 + 공백 · ｰ(B0) · ・(A5).
  아이템 창 이름 폭 = 11자(이름 x=18 ‥ Exp x=106, 8px) — 원본 가장 긴 이름(ｸﾞﾚｰﾄｽﾚｲﾔｰ)도 11 B.
  '-' 는 ASCII 2D 대신 반각 ｰ(B0) 로 쓴다(원본 「Lv1ーS」 가 B0 — 화면 검증된 코드만).
  1ZANAH.DEM 에 같은 표가 있으면 같이 고친다.
  python tools/zana_hw.py   → 표 검사 + 바뀐 내용 출력
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)

W = 11
NAMES = [  # (H 오프셋, 원문(확인용), 영문)
    (0x90614, 'ナイフ', 'Knife'), (0x90628, 'ショートソード', 'Short Sword'), (0x9063C, 'スピア', 'Spear'),
    (0x90650, 'ハンドアックス', 'Hand Axe'), (0x90664, 'ロングソード', 'Long Sword'), (0x90678, 'バトルアックス', 'Battle Axe'),
    (0x9068C, 'バトルソード', 'BattleSword'), (0x906A0, 'モーニングスター', 'MorningStar'), (0x906B4, 'ランス', 'Lance'),
    (0x906C8, 'ハルバート', 'Halberd'), (0x906DC, 'グレートアックス', 'Great Axe'), (0x906F0, 'グレートスレイヤー', 'GreatSlayer'),
    (0x90704, 'ラッキーブレード', 'Lucky Blade'), (0x90718, 'ムラサメブレード', 'Murasame'), (0x9072C, 'マジックメイス', 'Magic Mace'),
    (0x90740, 'マジックスレイヤー', 'MagicSlayer'), (0x90754, 'ドラゴンスレイヤー', 'D-Slayer'),
    (0x908BC, 'ニードル', 'Needle'), (0x908D0, 'D・ニードル', 'D-Needle'), (0x908E4, 'マインド', 'Mind'),
    (0x908F8, 'ウォーター', 'Water'), (0x9090C, 'ファイア', 'Fire'), (0x90920, 'アールマインド', 'R-Mind'),
    (0x90934, 'サンダー', 'Thunder'), (0x90948, 'ポイズン', 'Poison'), (0x9095C, 'D・ウォーター', 'D-Water'),
    (0x90970, 'D・ファイア', 'D-Fire'), (0x90984, 'ダーク', 'Dark'), (0x90998, 'D・サンダー', 'D-Thunder'),
    (0x909AC, 'ティルト', 'Tilt'), (0x909C0, 'D・ポイズン', 'D-Poison'), (0x909D4, 'D・ダーク', 'D-Dark'),
    (0x909E8, 'D・ティルト', 'D-Tilt'), (0x909FC, 'デス', 'Death'),
    (0x90B64, 'マント', 'Cloak'), (0x90B78, 'レザーアーマー', 'Leather'), (0x90B8C, 'ライトメイル', 'Light Mail'),
    (0x90BA0, 'ハードメイル', 'Hard Mail'), (0x90BB4, 'リングメイル', 'Ring Mail'), (0x90BC8, 'ウッドアーマー', 'Wood Armor'),
    (0x90BDC, 'チェインメイル', 'Chain Mail'), (0x90BF0, 'ウッドメイル', 'Wood Mail'), (0x90C04, '+2・レザーアーマー', '+2 Leather'),
    (0x90C18, 'ハーフプレート', 'Half Plate'), (0x90C2C, 'フルプレート', 'Full Plate'), (0x90C40, 'ハイレザーアーマー', 'Hi-Leather'),
    (0x90C54, 'リフレックス', 'Reflex'), (0x90C68, '+2・リングメイル', '+2 RingMail'), (0x90C7C, '+2・フルプレート', '+2FullPlate'),
    (0x90C90, '+2・リフレックス', '+2 Reflex'), (0x90CA4, 'バトルスーツ', 'Battle Suit'),
    (0x90E0C, 'グローブ', 'Gloves'), (0x90E20, 'スモールシールド', 'SmallShield'), (0x90E34, 'ラージシールド', 'LargeShield'),
] + [(0x90E48 + 0x28 * (k - 1) + 0x14 * j, 'Lv%dー%sシールド' % (k, 'SL'[j]), 'Lv%d%s-Shield' % (k, 'SL'[j]))
     for k in range(1, 8) for j in range(2)] + [
    (0x910B4, 'スペクタクルズ', 'Spectacles'), (0x910C8, 'レッド・ポーション', 'Red Potion'), (0x910DC, 'ランプ', 'Lamp'),
    (0x910F0, 'ブラック・オニキス', 'Black Onyx'), (0x91104, 'ファイアクリスタル', 'FireCrystal'), (0x91118, 'マトック', 'Mattock'),
    (0x9112C, 'アワーグラス', 'Hourglass'), (0x91140, 'ウイング・ブーツ', 'Wing Boots'), (0x91154, 'マントル', 'Mantle'),
    (0x91168, 'デーモンズ・リング', 'Demons Ring'), (0x9117C, 'バランス', 'Balance'), (0x91190, 'キーペンダント', 'Key Pendant'),
    (0x911A4, 'キャンドル', 'Candle'), (0x911B8, 'ルビー', 'Ruby'), (0x911CC, 'ブラウンポーション', 'BrownPotion'),
    (0x911E0, 'ミラー', 'Mirror'), (0x911F4, 'ボトル', 'Bottle'),
    (0x9199C, 'クラウン', 'Crown'), (0x919B0, 'キー', 'Key'), (0x919C4, 'エクリサー', 'Elixir'), (0x919D8, 'マッシュルーム', 'Mushroom'),
    (0x919EC, 'ポイズン', 'Poison'), (0x91A00, 'ハンマー', 'Hammer'), (0x91A14, 'ペンダント', 'Pendant'),
    (0x91A28, 'ホーリーバイブル', 'Holy Bible'), (0x91A3C, 'ブーツ', 'Boots'), (0x91A50, 'グローブ', 'Gloves'),
    (0x91A64, 'ロッド', 'Rod'), (0x91A78, 'クリスタル', 'Crystal'),
]
OK = set(b'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+ ')


def enc(s):
    out = bytearray()
    for ch in s:
        if ch == '-':
            out.append(0xB0)                    # 반각 ｰ (화면 검증된 코드)
        elif ch == '・':
            out.append(0xA5)
        else:
            b = ch.encode('ascii'); assert b[0] in OK, ('반각 글꼴에 없는 글자', s, ch); out += b
    return bytes(out)


def patch(H):
    import unicodedata
    out = bytearray(H)
    for o, jp, en in NAMES:
        cur = unicodedata.normalize('NFKC', H[o:o + 20].split(b'\0')[0].decode('cp932'))
        assert cur == unicodedata.normalize('NFKC', jp), ('원문 다름', hex(o), cur, jp)
        b = enc(en); assert len(b) <= W, ('11자 넘침', en)
        out[o:o + 20] = b + bytes(20 - len(b))
    return bytes(out)


DEM_DELTA = 0x3CC                                # 1ZANAH.DEM 의 같은 표 = H + 0x3CC


def patch_dem(D):
    H_like = bytearray(D)
    for o, jp, en in NAMES:
        q = o + DEM_DELTA; b = enc(en)
        H_like[q:q + 20] = b + bytes(20 - len(b))
    return bytes(H_like)


def regions():
    return [(o, o + 20) for o, _, _ in NAMES]


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    H = open(os.path.join(ROOT, 'work', 'disc', 'fc1', 'zana', '1ZANAH.BIN'), 'rb').read()
    D = open(os.path.join(ROOT, 'work', 'disc', 'fc1', 'zana', '1ZANAH.DEM'), 'rb').read()
    H1 = patch(H)
    print(len(NAMES), '개 이름 →', sum(1 for i in range(len(H)) if H[i] != H1[i]), '바이트 바뀜')
    blk = H[0x90614:0x91A8C]; j = D.find(blk)
    print('DEM 사본 위치', hex(j) if j >= 0 else '없음(다름)')
