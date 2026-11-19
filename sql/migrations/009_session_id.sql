CREATE TABLE session (
	session_id	CHAR(64) PRIMARY KEY NOT NULL COMMENT 'secrets.token_hex(32)',
	user_id	BIGINT NOT NULL,
	session_expires_at	DATETIME NOT NULL COMMENT '30일 뒤 세션 만료(로그인시 갱신)',
    FOREIGN KEY (user_id) REFERENCES user (user_id) ON DELETE CASCADE
);