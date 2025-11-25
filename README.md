# EcoNutriScore-Backend
# 가상환경  실행방법: poetry env activate 입력 결과물을 그대로 입력
# 로컬 서버 실행방법: uvicorn main:app --reload
# mysql 접속 방법: docker exec -it 컨테이너이름 mysql -u root -p
# redis 캐시 접속 방법: docker exec -it my-redis redis-cli
# 테스트 유저 코드: INSERT INTO users (login_id, password_hash) VALUES ('test_user', 'pass1234');