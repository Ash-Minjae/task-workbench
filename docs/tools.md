# 실행 조건

Python 3.10 이상과 표준 라이브러리만 사용한다. 별도 패키지와 설치, API 키가 필요하지 않다. 실제 환경에 Python이 있는지는 먼저 확인한다. 없으면 스킬 지침과 프로젝트가 제공한 도구로 검증한다. 아래 python은 환경에 따라 python3일 수 있다.

명령은 저장소 루트에서 실행한다. 다른 작업 폴더에서는 tools 경로를 실제 위치로 바꾼다. 네트워크와 외부 프로그램을 호출하지 않고 입력 파일을 수정하지 않는다. JSON 출력에 입력의 SHA-256을 포함한다. 출력 경로를 지정하면 새 파일만 쓰며 기존 파일을 덮어쓰지 않는다.

## CSV와 TSV

```text
python tools/tablecheck.py inspect practice/raw.csv --key order_id --numeric amount
python tools/tablecheck.py check practice/raw.csv --key order_id --required amount --numeric amount
python tools/tablecheck.py compare practice/raw.csv practice/candidate.csv --key order_id --numeric amount --group region
```

inspect와 compare는 관찰 보고서다. 구조를 읽고 보고서를 만들면0을 반환하며, 데이터와 변화가 올바르다는 판정이 아니다. check는 지정한 검사만 통과하면0, 조건 위반이 있으면1, 입력이나 설정 문제면2를 반환한다. 검사 없이 check를 실행하면2를 반환한다. 위 raw.csv의 check는 알려진 문제 때문에1이 예상된다.

- --required는 해당 열이 존재하며 각 행에서 공백이 아닌 값을 요구한다.
- --key는 선택한 열들의 복합 키가 비어 있지 않고 중복되지 않아야 한다는 조건이다. 값의 앞뒤 공백이나 선행0을 자동 정규화하지 않는다.
- --numeric은 비어 있지 않은 값의 숫자 형식만 검사한다. 빈 값도 금지하려면 --required를 함께 쓴다.
- --nonnegative는 숫자 형식과 음수 여부를 검사한다. 환불처럼 음수가 유효한 열에 임의로 적용하지 않는다.
- --expect-rows는 정확한 행 수 조건이다. 0을 명시하지 않은 빈 데이터 검사는 실패한다.
- --group은 compare의 집단별 영향을 확인한다. 키와 숫자, 집단 열 옵션은 반복할 수 있다.
- --output은 JSON 보고서를 저장한다. 부모 폴더는 미리 있어야 하며 기존 경로를 지정하면 오류로 끝난다.

.tsv는 탭, 그 밖의 확장자는 쉼표로 읽는다. 필요하면 --delimiter로 한 글자를 지정한다. UTF-8과 BOM을 기본 지원하며 --encoding으로 바꿀 수 있다. 열 이름이 비거나 겹치고 행 길이가 다르면 거부한다. 빈 물리 행은 건너뛰고 그 수를 보고한다. 파일 전체를 메모리에 읽으므로 대용량 처리용은 아니다.

숫자는 소수와 지수 표기를 지원한다. 통화 기호, 천 단위 구분, NaN과 무한대는 변환하지 않는다. 수치의 지수 절댓값1000과 유효숫자2000자리를 넘는 값은 지원 범위 밖으로 처리한다. valid_value_sum은 숫자로 해석한 값의 합계다. 누락과 잘못된 값이 있으면 그 수를 함께 보고한다. 행이 있는데 유효 숫자가 하나도 없으면 합계는 null이다. 행 자체가0개인 집단의 합계는0이다.

compare는 두 파일의 열과 순서가 같아야 한다. 행의 추가와 제거는 중복 횟수를 보존하는 비교이며, 같은 키의 값이 바뀌면 행 기준으로 제거1개와 추가1개가 될 수 있다. 키 비교는 별도로 제공한다. 숫자 차이는 후값에서 전값을 뺀 값이며 전후 중 합계를 계산할 수 없는 쪽이 있으면 null이다. 단위와 업무상 의미는 도구가 추정하지 않는다.

## 산출물 계약

```text
python tools/artifactcheck.py practice/artifacts.json --workspace practice
```

연습 폴더에는 summary.json이 없으므로 위 명령은1을 반환한다. 별도 작업 폴더에서 실제 요약을 작성한 뒤 다시 검사한다. 0은 계약에 쓴 파일과 형식 조건의 통과이며 과제 전체 성공이 아니다.

계약에는 비어 있지 않은 artifacts 목록을 쓴다. 각 항목은 상대 경로 path와 file, json, csv 중 kind를 가진다. min_bytes의 기본값은1이다. JSON의 required_keys는 최상위 키의 존재만 확인한다. 값의 형식도 확인하려면 types에 필드명과 object, array, string, number, boolean, null 중 기대 형식을 지정한다. types에 쓴 필드는 존재해야 한다. CSV는 columns, min_rows, max_rows를 선택할 수 있다. 빈 계약, 잘못된 옵션과 중복 경로, 작업 폴더를 벗어난 경로는 거부한다. JSON의 중복 키와 NaN 등 비표준 값도 거부하며, 표현 가능한 숫자 범위를 넘은 경우 해당 항목의 내용 오류로 보고한다. 형식 검사는 업무 내용의 타당성까지 판정하지 않는다.
