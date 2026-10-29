# Task Workbench

실무 과제에서 AI 작업을 조정하고 실제 결과를 검증하며, 산출물의 동작과 한계를 이해하기 위한 준비 도구다. 실제 과제의 요구와 권한이 이 묶음의 예시보다 우선한다.

## 가져와서 사용하기

제공된 작업 환경에서 실제 과제 폴더를 확인한 뒤 그 위치에서 실행한다. 아래 대상 폴더가 이미 있으면 다른 빈 경로를 정한다.

```sh
git clone https://github.com/Ash-Minjae/task-workbench.git .prep/task-workbench
git -C .prep/task-workbench rev-parse HEAD
```

이 주소는 이 프로젝트의 배포 대상이다. 아직 공개되지 않았거나 접근이 허용되지 않는 환경에서는 clone이 실패한다. 개인 계정으로 로그인하거나 개인 파일을 올려 우회하지 않는다.

가져온 뒤 Codex에 [시작 요청문](docs/start.md#첫-요청문)을 전달한다. 실제 과제 지침을 확인하고 필요한 SKILL.md를 경로로 읽게 하는 방식이다. 실제 과제 폴더를 작업 위치로 유지하고, 기존 프로젝트의 지침과 전역 설정은 바꾸지 않는다.

스킬은 `.agents/skills`에 있다. Codex가 이 저장소를 작업 경로로 사용하는 경우에는 자동 검색 대상이 될 수 있다. 과제 폴더 아래에 clone해 둔 경우 상위 과제의 세션에서 자동 등록된다고 가정하지 않는다. 인식되지 않으면 이름 호출을 반복하지 말고 파일을 직접 읽힌다. [상세 절차](docs/start.md#스킬-호출과-인식-확인)에 두 방식을 구분했다.

| 필요 | 읽을 스킬 또는 실행 도구 |
|---|---|
| 목표, 제약과 AI 위임 범위 | [task-steering](.agents/skills/task-steering/SKILL.md) |
| 표 데이터의 집계와 분석 | [tabular-analysis](.agents/skills/tabular-analysis/SKILL.md) |
| 앱의 필수 사용 흐름 구현 | [app-delivery](.agents/skills/app-delivery/SKILL.md) |
| 실제 결과 확인과 오류 수정 | [artifact-checking](.agents/skills/artifact-checking/SKILL.md) |
| 처리 흐름과 선택 이유 이해 | [explain-artifact](.agents/skills/explain-artifact/SKILL.md) |
| CSV 구조, 조건과 전후 영향 | [tablecheck.py](tools/tablecheck.py) |
| 제출 파일과 형식 검사 | [artifactcheck.py](tools/artifactcheck.py) |

## 처음 확인할 것

스킬은 Markdown 파일이다. 보조 검사 도구를 실행할 때만 Python 3.10 이상이 필요하다. 아래 명령은 저장소 루트에서 공개된 합성 데이터의 관찰 보고서를 만든다. 실행 방법과 반환 코드의 의미는 [도구 설명](docs/tools.md)에 있다.

```text
python tools/tablecheck.py inspect practice/raw.csv --key order_id --numeric amount
```

Python이 없는 환경에서는 문서와 스킬을 읽고 제공된 프로젝트 도구로 검증한다. 가져오기가 막혔으면 다른 경로나 개인 파일 업로드로 우회하지 않고 실제 환경의 안내를 따른다.

## 평가 방향과 적용 범위

[Cofa의 공개 설명](https://www.getcofa.com/ko)은 결과물의 기술적 품질, AI 작업을 조정하는 의도, 실제 결과를 이해하는 인지를 구분한다. 이 묶음은 실행 검사, 목표와 범위 설정, 산출물 설명을 연결하도록 구성했다. 개별 시험의 배점과 성과를 보장하지 않는다.

도구가 통과했다고 과제 전체가 맞는 것은 아니다. 정상 사례뿐 아니라 알려진 오류를 넣어 검사가 반응하는지 확인하고 중요한 계산을 별도로 대조한다. 자동 수집되는 실행 흔적을 꾸며 내지 않고, 선택 이유와 미확인 한계만 필요한 만큼 보완한다.

이 묶음은 네트워크, 외부 모델 연결과 자동 화면 조작을 사용하지 않는다. 예제 데이터는 합성이며 완성된 시험 답안이 아니다. 적용 규정에서 AI를 금지하는 답변 단계에서는 사용하지 않는다.

## 연습과 공개

[전처리 후보 검토](practice/brief.md)로 문제 정의, 실행 검증, 실제 결과 설명을 연습할 수 있다. 데이터 삭제 정책을 미리 정하지 않고 처리 영향을 확인하는 연습이다.

처음 사용할 때는 [별도 작업 폴더에서 끝까지 실행하는 안내](docs/practice.md)를 따른다.

```text
python -m unittest discover -s tests -v
```

저장소를 공개할 경우 개인 경로와 자격증명, 실제 과제 데이터와 결과를 추가하지 않는다. 필요한 버전의 커밋을 기록하고 적용되는 공개 유지 조건을 따른다. 작업 데이터와 보고서는 별도 작업 폴더에 둔다.

지침과 도구의 이용 조건은 [MIT 라이선스](LICENSE)에 있다.
