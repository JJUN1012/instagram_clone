## Repository 폴더 설명

- `app/`: FastAPI 백엔드 코드
  - `routers/`: 회원·팔로우·게시글·댓글 기능별 코드
  - `templates/`: Jinja2 HTML 화면
  - `static/css/`, `static/js/`: 스타일과 JavaScript
- `sql/`: 전체 테이블 구조와 테스트 데이터
  - `migrations/`: DB 구조 변경 이력
  - `queries/`: 기능별 SQL 쿼리
- `docs/`: ERD·관계 스키마·정규화 문서
- `scripts/`: DB 변경 적용 등 개발 보조 스크립트
- `tests/`: 테스트 코드
- `uploads/`: 업로드한 사진(Git 제외)

`.gitkeep`은 빈 폴더를 Git에 보관하기 위한 파일이므로 필요한 파일을 업로드 한 후에는 삭제할 것.
