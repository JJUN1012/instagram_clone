-- name: get_session_user
SELECT u.user_id, u.user_username, u.user_name, u.user_bio, u.user_profile_url, s.session_expires_at
FROM session s
JOIN user u ON s.user_id = u.user_id
WHERE s.session_id = %s;

-- name: check_username_exists
SELECT user_id FROM user WHERE user_username = %s;

-- name: insert_user
INSERT INTO user (user_username, user_name, user_password) VALUES (%s, %s, %s);

-- name: get_user_for_login
SELECT user_id, user_username, user_name, user_password FROM user WHERE user_username = %s;

-- name: insert_session
INSERT INTO session (session_id, user_id, session_expires_at) VALUES (%s, %s, %s);

-- name: delete_session
DELETE FROM session WHERE session_id = %s;
