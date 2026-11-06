-- 1. user 테이블 생성
CREATE TABLE "user" (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. follows 테이블 생성
CREATE TABLE "follows" (
    follower_id INT REFERENCES "user"(id) ON DELETE CASCADE,
    followed_id INT REFERENCES "user"(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (follower_id, followed_id)
);