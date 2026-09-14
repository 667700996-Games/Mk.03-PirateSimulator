# 검은물결: 해적 군주

`검은물결: 해적 군주`는 브라우저에서 실행되는 싱글플레이 2.5D 해적 정착지 경영 시뮬레이션입니다. 폭풍 뒤 무인도에 남은 생존자들을 이끌어 지형에 건물을 배치하고, 실제 운반 경로를 가진 생산망을 조직하고, 함선을 건조해 군도 원정과 해안 방어를 수행합니다.

기존 프로젝트의 타이틀·선장 생성·Dark Pirate Maritime Command 디자인 시스템·해상 전투 자산은 보존했습니다. 플레이의 중심은 메뉴식 시설 구매에서 공간·물류·주민·산업·함대가 맞물리는 도시 시뮬레이션으로 전환했습니다.

전환 분석과 단계별 기술 계획은 [`docs/settlement-transition.md`](docs/settlement-transition.md), AAA 품질 검토와 적용 근거는 [`docs/aaa-implementation-report.md`](docs/aaa-implementation-report.md)에 있습니다.

## 실행

Node.js 22 이상이 필요합니다. 빌드·미리보기에는 Python 3.9 이상과 macOS/Linux/WSL의 POSIX 잠금도 필요합니다.

```bash
npm install
npm run dev
```

프로덕션 빌드:

```bash
npm run build
npm run preview
```

정적 결과물은 `build/` 링크로 제공됩니다. 빌드 중간 파일은 작업별로 격리해 종료 시 정리하며, 개발용 성공 패키지 최근 2회와 원문 로그 최근 10회(각 최대 1MiB)를 보관합니다. 출시본·기존 배포본·심볼은 별도 보존합니다. 실행 방법과 예외는 [빌드 정리 정책](docs/build-cleanup.md)을 참고하세요.

## 핵심 플레이 루프

1. 선장과 해적단을 만들고 난파선 자재와 16명의 생존자를 확인합니다.
2. 집수장, 벌목장, 창고와 어업소를 지형 조건에 맞게 배치합니다.
3. 운반자가 난파선·생산시설·창고·소비처 사이를 실제 경로로 이동합니다.
4. 직업 우선순위, 주거, 식수, 음식, 사기와 주민 계층을 관리합니다.
5. 원목→판자, 광석→괴, 곡물→밀가루→건빵 같은 다단계 생산망을 확장합니다.
6. 조선소에 판자·밧줄·돛·철 부품·함포를 운반하고 조선공으로 함선을 건조합니다.
7. 선박, 장교, 승조원, 보급품을 편성해 미탐사 해역·약탈·교역·구조 원정을 보냅니다.
8. 사건과 전투 선택을 해결하고 희귀 자원과 설계도를 정착지로 운반합니다.
9. 감시탑·해안 포대에 인력과 현장 탄약을 공급해 왕실 함대를 방어합니다.
10. 난파 생존부터 첫 약탈, 자유항 밀수, 경쟁 해적 추적, 왕실 암호문과 본거지 공성전까지 5장 연대기를 완수합니다.
11. 악명·번영·항해술·해적 연방과 정책을 조합해 도시의 장기 노선을 정합니다.

## 도시 조작

| 입력             | 기능                          |
| ---------------- | ----------------------------- |
| 마우스 클릭      | 타일·건물 선택 또는 건물 배치 |
| 마우스 드래그    | 도시 카메라 이동              |
| 마우스 휠        | 확대·축소                     |
| `R`              | 배치 중 건물 회전             |
| 방향키 / `Enter` | 키보드 건설 커서 이동 / 배치  |
| `Esc`            | 배치·이동 취소 또는 일시정지  |
| `Space`          | 시뮬레이션 일시정지/재개      |
| `1` / `2` / `3`  | 1배·2배·3배 속도              |
| `B`              | 건설 메뉴                     |
| `L`              | 물류 오버레이                 |
| `F`              | 함대와 원정                   |

건물을 선택하면 생산법, 현장 입력·출력 재고, 인력, 상태, 천연자원 잔량을 확인할 수 있습니다. 건설 우선순위 변경, 일시정지, 회전, 이동, 취소, 철거와 3단계 확장이 실제 상태 머신과 물류 요청에 연결됩니다.

## 실시간 해상 전술 조작

수리·건조된 기함(선체·돛 35% 이상, 선원 4명 이상)이 있으면 `해도 → 기함으로 전술 출격`을 선택할 수 있습니다. 전략 원정이 주축이며, 선장이 직접 개입하고 싶은 교전은 실시간 전술 화면에서 지휘합니다.

| 입력      | 기능                                  |
| --------- | ------------------------------------- |
| `W` / `S` | 돛 펼침 / 접기                        |
| `A` / `D` | 좌·우현 조타                          |
| `Q` / `E` | 좌·우현 포대 선택                     |
| `1`–`5`   | 일반탄·사슬탄·산탄·소이탄·관통탄 선택 |
| `Space`   | 선택 포대 일제사격                    |
| `F`       | 속도·거리·적선 상태가 맞을 때 승선    |
| 마우스 휠 | 전술 카메라 확대·축소                 |

터치 화면에서는 전용 조타·돛 버튼과 2열 포대·탄종 명령 패널을 제공합니다.

## 구현된 정착지 시스템

- 24×18 결정론적 섬 지도, 해안·암초·평지·숲·습지·동굴·경사·절벽·고지대·협곡·광맥과 4단계 고도
- 미탐사 지형과 자원을 감추는 전장의 안개, 작업자가 배치된 감시탑·신호탑·정보망의 시간당 정찰
- Phaser 3 아이소메트릭 렌더링, 절벽 측면, 파도, 해변 포말, 습지·동굴·협곡 실루엣, 날씨, 낮과 밤, 굴뚝 연기, 공사 가설물, 부두·포대 실루엣
- 수면·암초·해변·평지·숲·경사·절벽·고지대·동굴·협곡·습지·3종 광맥까지 15개 지형을 빠짐없이 연결한 프로젝트 전용 아이소메트릭 표면 아틀라스
- 초기 생존·항만 12종, 산업 9종, 주거·복지·군수·행정 9종, 물류·수직 기반시설·함대 12종, 생산·생활·공공·방어 16종을 합친 58개 전체 건물 타입의 전용 본체 프레임과 건물별 다중 아틀라스 라우팅
- 난파선 잔해를 제외한 57종 전체 건물은 2단계·3단계 전용 완성 본체 아틀라스를 사용한다. 핵심 11종은 천막·부두·포대 규모가, 산업 9종은 채굴 설비·경작 단수·용광로·작업 베이·가공 및 저장 설비가, 주거·복지·군수·행정 9종은 주거 동·의료 병동·방어 구조·행정 공간이, 물류·수직 기반시설·함대 12종은 하역 베이·교량·승강 구조·건선거·보급 및 주조 능력이, 생산·생활·서비스 8종은 작업실·안전 구획·공공 서비스 수용력이, 공공·훈련·방어·행정 8종은 관람석·훈련 구역·성벽·통신 및 회의 공간이 실제로 변한다. 레벨 4 이상 조선소·해안 포대는 3단계 본체와 추가 요새 장식을 결합
- 건설 비계·확장 도르래·2단계 보급 장식·3단계 요새 장식·피해 잔해·중단 현장을 실제 건물 외곽에 합성하는 6종 성장·상태 아틀라스
- 지형·고도·점유 면적·해금 조건을 검사하는 회전형 건물 배치
- 채집·가공·물류·주거·복지·함대·군사·행정·수직 기반시설 카테고리의 데이터 기반 건물 50종 이상
- 기초·가공·생활·군수·고급·특수 전리품을 포함한 자원 69종과 확장 가능한 생산법 카탈로그
- 출발지·도착지·예약 수량·A* 경로·운반자·픽업·배송 상태가 있는 실제 화물 작업과, 건물 점유·미탐사 구역·교량·혼잡·날씨를 반영하는 이동 비용
- 생산 입력 부족, 출력 포화, 운반 대기, 인력 부족, 천연자원 고갈을 구분하는 병목 상태
- 이름·계층·직업·집·직장·건강·사기·충성·피로·경험·욕구·행동·이동 경로를 가진 개별 주민, 8개 역할별 전·후면 3프레임 보행과 작업·전투 전용 3프레임 아틀라스, 좌우 반전을 결합한 네 대각선 방향, 프레임 독립 위치 보간과 13개 행동별 운반·생산·소방·훈련·승선·방어 동작 및 상태 표식
- 식사·음주·치료·휴식은 자원 소비 직후 끝나는 수치 효과가 아니라 서비스 시설 방문 예약, 실제 A* 이동, 현장 행동 시간, 직장·숙소 복귀로 이어진다. 방문 중에는 현장 생산·건설에서 빠지며, 원정 승조원은 정착지 이동·물류·소비 갱신에서 제외된다.
- 화면 밖 주민 갱신 축소와 최대 표시 수 제한을 이용한 주민 LOD
- 자동 노동 배치와 직업별 최소·최대 인원, 우선순위, 숙련자 우선 규칙
- 시간별 식수·식량 소비, 주거 배치, 사기·충성 변화, 계층 상승과 조건부 이주
- 의복·의료·오락·해적 문화·직업 장비를 실제 상품과 직원이 있는 서비스 건물에서 소비하는 전체 욕구 체계
- 화재 위험·화약고 이격·진압·손상 수리, 질병·반란·창고 포화를 위치로 안내하는 경고 체계
- 자원·현장 운송·조선공 작업 시간을 모두 요구하는 9개 등급의 함선 건조 대기열
- 목적·해역·함선·장교·승조원·보급·위험도·화물 한도를 가진 전략 원정
- 전투·날씨·발견·사회·위험의 12개 데이터 기반 항해 사건, 선택 결과, 피해, 귀환, 희귀 전리품 하역과 미탐사 해역 발견
- 사거리 기동, 풍각, 일반탄·사슬탄·산탄, 응급 수리, 승선과 후퇴를 지휘하는 턴제 원정 해전
- 9개 함선 등급 전용 아트, 풍향·관성·포대 사각·5종 탄약, 다문 일제사격, 피격·화재·침수·침몰과 승선이 연결된 선택적 실시간 기함 출격
- 실제 포대 작업자와 현장 대포알·화약, 90초 준비 제한, 영구 부상·전사·함선 손실을 사용하는 다단계 해안 방어전
- 악명·번영·항해술·해적 연방의 네 발전 축과, 생산·급여·배급·포로·교역·원정 결과를 실제로 변경하는 통치 정책
- 식량·물류·창고·인력·화재·방어 오버레이와 심각도별 경고
- 임무·세력·자유항·약탈·방어 보상과 비용을 도시의 한 번의 공간 재고에서 처리하는 단일 경제
- 인구·입체 물류·함대·군도 탐사·네 발전 축·본거지 방어를 묶은 7개 장기 목표와 해적 왕국 승리/계속 플레이
- 초반 핵심 시설 5개와 첫 약탈을 안내하는 0/6 온보딩, 보상 수령 시 다음 장이 이어지는 5장 검은물결 연대기

전략 원정과 정착지 경제가 주 플레이 흐름을 담당하며, 실시간 항해·포격·승선은 해도의 선택적 기함 출격으로 연결됩니다. 함선·선원 피해와 탄약 소모는 권위 있는 게임 상태에 즉시 반영됩니다.

## 기술 구조

```text
src/lib/
├── audio/                 # Web Audio 환경음과 효과음
├── components/            # 타이틀, 생성, 앱 셸, HUD, 내비게이션
├── domain/                # 기존 해상/전투/임무/세력 규칙과 전체 게임 시계
├── game/
│   ├── SettlementGame.ts  # Phaser 정착지 게임 생성
│   ├── SettlementScene.ts # 아이소메트릭 지도, 주민, 오버레이, 입력
│   └── SeaScene.ts        # 보존된 실시간 해상 전술 장면
├── persistence/           # IndexedDB 저장소, 검증, 버전 마이그레이션
├── screens/               # 도시, 주민, 조선소, 함대, 해도, 발전, 방어 UI
├── settlement/
│   ├── catalog.ts         # 자원·생산법·건물·주민 계층 데이터
│   ├── construction.ts    # 배치·이동·취소·확장 명령
│   ├── island.ts          # 지형 검사와 A* 경로 탐색
│   ├── logistics.ts       # 예약·픽업·배송 물류
│   ├── simulation.ts      # 건설·생산·욕구·정책·위험 일괄 시뮬레이션
│   ├── economyBridge.ts   # 임무·교역·세력과 공간 재고의 단일 경제 경계
│   ├── shipbuilding.ts    # 함선 건조
│   ├── expeditions.ts     # 전략 원정과 사건
│   └── progression.ts     # 발전 축과 정책
└── stores/                # 세션, 시계, 자동 저장
```

Svelte는 고밀도 관리 UI를 담당하고 Phaser는 공간 표현과 포인터 입력을 담당합니다. 권위 있는 게임 상태는 순수 TypeScript 도메인에만 있으며, Phaser 장면은 구조화 복제한 읽기 전용 스냅샷을 렌더링하고 명령을 Svelte 브리지로 반환합니다.

## 데이터와 저장

- 게임 상태: IndexedDB `blackwake-pirate-simulator` 데이터베이스 v2 (`saves`, `backups` 저장소)
- 설정·키 바인딩: `localStorage`
- 현재 저장 버전: `4`
- 이전 v1/v2/v3 저장은 로드 시 v4 정착지·포로·원정 목적 상태로 순차 마이그레이션
- 저장 범위: 섬·타일 자원, 건물·공사·재고·생산, 운송, 주민·직업·욕구, 함선·건조 대기열, 원정, 발전·정책, 위협·날씨·통계와 기존 세계 상태 전체
- 저장 시 FNV-1a 무결성 값을 기록하고 슬롯별 최신 3개 순환 복구 지점을 유지하며, 주 저장 손상 시 마지막 정상 지점으로 자동 복원
- 가져오기 파일은 8MB로 제한하고 수치 범위, ID 유일성, 건물·주거·운송·원정·활성 함선 교차 참조까지 검증
- 자동 저장: 상태를 바꾸는 주요 명령, 원정·전투·건설 이벤트, 5분 주기, 브라우저가 백그라운드로 전환될 때
- 동일 탭 재로딩에서는 `sessionStorage`의 활성 슬롯 표식으로 IndexedDB 저장을 즉시 복원하고, 선장 생성 중에는 입력 초안을 복구합니다. 명시적으로 타이틀로 돌아가거나 탭을 닫으면 임시 세션 표식은 유지하지 않습니다.
- 자동 저장은 알림을 쌓지 않으며 수동 저장만 명시적인 완료 피드백을 표시
- 설정에서 JSON 저장 내보내기·가져오기를 지원하며 중첩 주민·건물 데이터를 검증

데이터 정의의 주요 인터페이스는 `ResourceDefinition`, `RecipeDefinition`, `BuildingDefinition`, `Resident`, `TransportJob`, `ShipConstructionOrder`, `StrategicExpedition`, `SettlementSimulationState`입니다.

## 성능 전략

- 섬 생성과 보행 경로를 도메인 로직으로 분리하고 시뮬레이션을 초 단위 배치 처리
- 화면 밖 주민 미렌더링, 대규모 인구에서 보이는 주민 수 제한, 350명 초과 시 회전형 주민 갱신 배치
- 주민·건물·서비스·노동력 조회 인덱스로 반복 선형 검색을 제거하고 시뮬레이션 단계의 중복 구조화 복제를 축소
- 교량·계단·경사로·화물 승강기를 반영하는 최대 500개 A* 경로 LRU 캐시와 적중 통계
- 완결된 운송 작업 정리, 운송 중 재고 예약으로 중복 작업 방지
- 정적 지형과 동적 건물·주민·오버레이 레이어 분리
- 날씨 서명 기반 재생성과 동적 Phaser tween 정리로 장시간 누적 방지
- 건물·오버레이 더티 서명, 주민 표시 객체 풀, 품질 단계별 주민·날씨·파도 밀도 제어
- 주민 보행은 정지용 별도 텍스처를 중복 적재하지 않고 3프레임 아틀라스의 중립 자세를 공유하며, 주민별 위상 분산과 화면 안 객체만의 프레임 교체로 동시 보행의 기계적인 반복과 불필요한 갱신을 줄임
- 초기 생존자 8명의 실제 작업 상태에는 전·후면 작업 아틀라스 2,238,568바이트(약 2.13MiB, 디코딩 약 12MiB)만 적재하고, 훈련·승선·방어가 시작되기 전까지 전·후면 전투 아틀라스 2,559,509바이트(약 2.44MiB, 디코딩 약 12MiB)를 요구 적재하지 않음. 자산 로드 전에는 기존 보행 중립 프레임과 행동 글리프를 유지
- 정착지 첫 진입에는 핵심 1단계 건물 아틀라스만 적재하고, 저장 도시에 이미 존재하거나 건설 도감·시설 확장에서 요구된 건물군과 단계 아틀라스만 내려받습니다. 신규 정착지 기준 17개 PNG 40,794,572바이트(약 38.90MiB)와 디코딩 텍스처 약 102MiB를 초기 경로에서 유예합니다.
- Svelte 관리 UI와 Phaser 렌더 스냅샷 분리로 캔버스 프레임과 상태 갱신 격리
- 저장 데이터 정규화와 IndexedDB 비동기 기록
- 500명 정착지 180틱 회귀 계약: 시뮬레이션 p95 50ms 미만, 전체 5초 미만, 주민·건물 상태 불변식 유지
- 실제 1초 주기 5,400틱과 5분 간격 저장 왕복 18회를 수행하는 90분 대표 세션 계약: 수치·객체 수·저장 크기·초반 건설 흐름 불변식 유지

## 검증

```bash
npm run check       # Svelte + TypeScript
npm run lint        # ESLint
npm test            # Vitest 단위·통합 테스트
npm run test:e2e    # Chromium·Firefox·WebKit + Pixel 7·iPhone 14
npm run build       # 정적 프로덕션 빌드
npm run validate    # check + lint + unit + build
npm run test:coverage # 핵심 도메인 커버리지 임계치 검증
```

자동 테스트는 지형 배치, 15종 지형 아틀라스, 카탈로그와 일대일 대응하는 58종 건물 본체 라우팅, 난파선 잔해를 제외한 57종 전체 건물의 1→2→3단계 전용 본체 교체, 6종 건물 성장·상태 아틀라스, 요구 기반 건물 아틀라스 적재, 8개 주민 역할의 전·후면 3프레임 보행과 작업·전투 루프·네 대각선 방향 전환·행동별 요구 적재, 실제 PNG·24프레임 JSON 응답, 점유·미탐사 경로, 혼잡, 수직 이동 비용, 공사 자재 운송, 건설 완료, 예약 화물 보호, 시설 확장, 생산·욕구·복지·계층 상승, 통치 정책, 함선 건조, 원정 사건과 영구 손실, 함대 선장 1:1 배치·탈영 영구 손실·출항 중복 차단·해전 전리품 적재·적/아군 난이도 배율, 임무·보상의 단일 경제, 5장 이야기, 실시간 기함 출격과 함선 아틀라스, 방어 카운트다운·사상자, 캠페인 승리, 90분 장기 세션, 파괴 명령 확인, 동일 탭 세션 복구, 저장 v1→v4 마이그레이션·무결성·복구를 검증합니다. 현재 25개 파일의 Vitest 119개와 5개 브라우저/기기 프로젝트의 Playwright 70개가 품질 게이트에 포함됩니다. GitHub Actions는 타입·린트·상향된 커버리지·빌드·전체 브라우저 행렬을 강제합니다.

## 웹 앱·접근성

- 버전별 앱 셸 캐시, 80개 제한 런타임 캐시, 내비게이션 전용 오프라인 복구와 192/512 PNG 설치 아이콘을 갖춘 서비스 워커·웹 앱 매니페스트
- 외부 CDN 없이 동작하는 로컬 글꼴 체계와 원본 Ogg 바다·항구·비 환경음, 대포·선체 충돌 효과음
- Web Audio 다이내믹 컴프레서·컨볼루션 잔향·날씨/도시 활동 믹싱, 화면 분위기별 1.8~2.2초 음악 교차 전환과 디코딩 실패 시 절차 합성 폴백
- 표준·적록 보정·녹적 보정·색 비의존 팔레트, 고대비, UI 크기 조절
- 동작 감소와 품질 단계가 Phaser 파티클·트윈·표시 인구에 실제 반영
- 모달 포커스 순환, 현재 화면 표시, 이름 없는 버튼 차단 등 키보드·스크린리더 접근성
- 모바일은 건설·경고·임무·분석을 상호 배타적 하단 시트로 열고, 배치 완료 후 선택 건물 상태를 즉시 표시
- 관리 화면은 동적 import로 분리하고 Phaser 엔진은 도시·해상 화면 진입 시에만 내려받아 초기 UI 번들을 줄임

## 원본 아트

타이틀과 본거지 키 아트는 이 프로젝트를 위해 만든 원본 자산인 [`static/art/pirate-haven-keyart.png`](static/art/pirate-haven-keyart.png)를 재사용합니다. 군도 해도는 이 세계관을 위해 새로 제작한 [`static/art/archipelago-command-map.webp`](static/art/archipelago-command-map.webp)입니다. 아이소메트릭 건물과 주민은 [`static/art/settlement/`](static/art/settlement/) 아래의 핵심·산업·사회·물류·수직 기반시설·함대 건물 본체와 주민 전·후면 3프레임 보행 아틀라스를 사용합니다. 핵심 확장 외형은 [`core-buildings-tier2-atlas.png`](static/art/settlement/core-buildings-tier2-atlas.png)와 [`core-buildings-tier3-atlas.png`](static/art/settlement/core-buildings-tier3-atlas.png), 산업 확장 외형은 [`industry-buildings-tier2-atlas.png`](static/art/settlement/industry-buildings-tier2-atlas.png)와 [`industry-buildings-tier3-atlas.png`](static/art/settlement/industry-buildings-tier3-atlas.png), 사회 확장 외형은 [`society-buildings-tier2-atlas.png`](static/art/settlement/society-buildings-tier2-atlas.png)와 [`society-buildings-tier3-atlas.png`](static/art/settlement/society-buildings-tier3-atlas.png), 물류·함대 확장 외형은 [`logistics-fleet-buildings-tier2-atlas.png`](static/art/settlement/logistics-fleet-buildings-tier2-atlas.png)와 [`logistics-fleet-buildings-tier3-atlas.png`](static/art/settlement/logistics-fleet-buildings-tier3-atlas.png), 생산·생활·서비스 확장 외형은 [`livelihood-service-buildings-tier2-atlas.png`](static/art/settlement/livelihood-service-buildings-tier2-atlas.png)와 [`livelihood-service-buildings-tier3-atlas.png`](static/art/settlement/livelihood-service-buildings-tier3-atlas.png), 공공·훈련·방어·행정 확장 외형은 [`civic-defense-buildings-tier2-atlas.png`](static/art/settlement/civic-defense-buildings-tier2-atlas.png)와 [`civic-defense-buildings-tier3-atlas.png`](static/art/settlement/civic-defense-buildings-tier3-atlas.png)로 분리했습니다. 지형은 [`terrain-surfaces-atlas-v2.png`](static/art/settlement/terrain-surfaces-atlas-v2.png), 건물 성장·상태 장식은 [`building-progression-overlays-atlas.png`](static/art/settlement/building-progression-overlays-atlas.png), 주민 보행은 [`resident-walk-front-atlas.png`](static/art/settlement/resident-walk-front-atlas.png)와 [`resident-walk-rear-atlas.png`](static/art/settlement/resident-walk-rear-atlas.png), 역할별 작업은 [`resident-work-front-atlas.png`](static/art/settlement/resident-work-front-atlas.png)와 [`resident-work-rear-atlas.png`](static/art/settlement/resident-work-rear-atlas.png), 전투는 [`resident-combat-front-atlas.png`](static/art/settlement/resident-combat-front-atlas.png)와 [`resident-combat-rear-atlas.png`](static/art/settlement/resident-combat-rear-atlas.png), 9개 함선 등급은 [`fleet-classes-atlas.png`](static/art/naval/fleet-classes-atlas.png)의 프로젝트 전용 아틀라스를 사용합니다. 절벽 측면, 자원·환경 실루엣, 물류선, 날씨, 식사·치료·오락 등 비핵심 행동의 미세 동작, 항적, 포연, 피격·화재·침수·침몰 효과는 CSS와 Phaser 코드로 절차 렌더링합니다. 자산 생성·편집 프롬프트와 처리 근거는 [`docs/art-generation-provenance.md`](docs/art-generation-provenance.md)에 기록했습니다. 특정 상용 게임의 이미지·UI·명칭을 복제하지 않습니다.

## 라이선스

이 프로젝트는 [MIT License](LICENSE)로 배포됩니다.
