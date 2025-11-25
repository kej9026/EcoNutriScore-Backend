# 1. Python 공식 이미지 사용 
FROM python:3.12-slim

# 2. 시스템 라이브러리 설치 (zbar 라이브러리)
# Read-only file system 오류를 피하기 위해 Dockerfile에서 설치합니다.
RUN apt-get update && apt-get install -y \
    libzbar0 \
    && rm -rf /var/lib/apt/lists/*

# 3. 작업 디렉토리 설정
WORKDIR /usr/src/app

# 4. Poetry 설치 및 환경 변수 설정
ENV POETRY_HOME="/opt/poetry" \
    PATH="$POETRY_HOME/bin:$PATH"
# Poetry 버전은 님의 환경에 맞춰 조정하세요 (2.1.3 유지)
RUN pip install poetry==2.2.1

# 5. 프로젝트 파일 복사 및 종속성 설치
COPY pyproject.toml poetry.lock ./
# --no-root 옵션으로 기본 설치 진행
RUN poetry install --no-root

# 6. 앱 파일 복사
COPY . .

# 7. 포트 및 실행 명령어 설정
EXPOSE 8080 
# Render는 $PORT 대신 8080 포트를 명시하는 경우가 많습니다.
# Start Command에서 환경 변수로 PORT를 받지 않는다면 8080을 사용합니다.
CMD gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app