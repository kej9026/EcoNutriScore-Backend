# 1. Python 공식 이미지 사용 
FROM python:3.12-slim

# 2. 시스템 라이브러리 설치
RUN apt-get update && apt-get install -y \
    libzbar0 \
    && rm -rf /var/lib/apt/lists/*

# 3. 작업 디렉토리 설정
WORKDIR /usr/src/app

# 4. Poetry 설치
ENV POETRY_HOME="/opt/poetry" \
    PATH="$POETRY_HOME/bin:$PATH"
RUN pip install poetry==2.2.1

# 5. 프로젝트 파일 복사
COPY pyproject.toml poetry.lock ./

# [중요 1] 가상환경 생성 방지 설정 추가! <--- 여기가 핵심입니다.
# 이렇게 해야 gunicorn이 시스템 경로에 설치되어 명령어를 찾을 수 있습니다.
RUN poetry config virtualenvs.create false && \
    poetry install --no-root

# 6. 앱 파일 복사
COPY . .

# 7. 포트 및 실행 명령어 설정
# Render는 실행 시 $PORT 환경변수(보통 10000)를 주입합니다.
# [중요 2] --bind 0.0.0.0:$PORT 추가 <--- 이거 없으면 접속 안 됨
CMD gunicorn -w 1 -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:$PORT