# 별도 작업 폴더에서 한 번 끝까지 실행하기

이 과정은 합성 데이터로 도구 사용과 결과 설명을 연습하는 예시다. 실제 업무나 시험의 정답이 아니다.

1. 저장소 루트에 work/rehearsal이라는 새 폴더를 만든다. practice의 raw.csv, candidate.csv, artifacts.json을 그 폴더에 복사한다. 원본 연습 파일은 그대로 둔다.
2. 저장소 루트의 터미널에서 아래 명령을 실행한다. inspect와 compare는 관찰 보고서이며 데이터 처리 정책을 승인하지 않는다.

```text
python tools/tablecheck.py inspect work/rehearsal/raw.csv --key order_id --numeric amount --output work/rehearsal/profile.json
python tools/tablecheck.py compare work/rehearsal/raw.csv work/rehearsal/candidate.csv --key order_id --numeric amount --group region --output work/rehearsal/impact.json
```

3. Codex에 profile.json과 impact.json의 관찰 결과를 근거로 summary.json 작성을 요청한다. assumptions는 가정의 배열, checks는 실제 검증 결과의 객체, limitations는 남은 한계의 배열로 쓴다. 월 정보가 없다는 점과 제거 정책의 승인 여부를 직접 확인한다. 도구가 유효 숫자만 합산했다는 사실도 반영한다.
4. 작성한 요약과 실제 수치가 일치하는지 확인하고 다음 명령으로 파일과 형식을 검사한다.

```text
python tools/artifactcheck.py work/rehearsal/artifacts.json --workspace work/rehearsal --output work/rehearsal/artifact-report.json
```

summary.json이 없거나 형식이 다르면 실패한다. 형식에 통과해도 판단이 올바른지는 사람이 확인한다. 임의의 내용으로 통과시키는 것을 목표로 삼지 않는다.

5. AI와 기록을 닫고 제거된 항목의 영향, 환불을 오류로 취급해도 되는지, 직접 확인한 부분과 남은 질문을 자신의 말로 설명한다.

출력 파일이 이미 있으면 덮어쓰지 않는다. 연습을 다시 할 때는 새 작업 폴더나 새 보고서 이름을 사용한다. 숫자 열의 빈 값을 금지하려면 --numeric뿐 아니라 --required도 지정해야 한다.
