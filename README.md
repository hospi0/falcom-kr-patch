# 팔콤 클래식 (새턴 JP) 한글화

## 내려받기
- 최신 **v0.9** — [릴리즈](https://github.com/hospi0/falcom-kr-patch/releases/latest)에서 `FalcomClassics_KR_v0.9.zip`
- 대상: `Falcom Classics (Japan) (Disc 1) (Game Disc)` 트랙 01 (트랙 18개)
- 원본md5 `287ADC660E0D65E5AE3600157DB6C9D5` → 패치md5 `ACAD85FCF05B7F6F18D4BEF5BC29F406`
- 이스 I(보통·오리지널 모드) · 제나두 · 드래곤 슬레이어(그림 글자) · 타이틀 메뉴

## 작업 저장소

- 인계·빌드 절차: **`docs/00_이어하기.md`** 부터.
- 원문 추출: `work/text/*.tsv` · 고친 번역: `work/tr_override` · `work/tr_fix` · `work/tr_add` · 용어 통일 `work/terms.tsv`
- 빌드 `python tools/build_fc1.py --install` → 배포 묶음 `python tools/make_dist.py`
- 팔콤 클래식 II(이스 II·아스테카)는 작업 중(같은 도구 `tools/build_fc2.py`).
- ROM·빌드 결과물은 들어 있지 않다.
