-- name: insert_post_like
INSERT IGNORE INTO post_likes (user_id, post_id, created_time) VALUES (%s, %s, NOW());

-- name: delete_post_like
DELETE FROM post_likes WHERE user_id = %s AND post_id = %s;

-- name: count_post_likes
SELECT COUNT(*) FROM post_likes WHERE post_id = %s;

-- name: list_comments
SELECT c.comment_id, c.comment_content, c.comment_created_time,
       u.user_id, u.user_username, u.user_name, u.user_profile_url
FROM comment c
JOIN user u ON c.user_id = u.user_id
WHERE c.post_id = %s {where_cursor}
ORDER BY c.comment_id DESC
LIMIT %s;

-- name: insert_comment
INSERT INTO comment (user_id, post_id, comment_content, comment_created_time) VALUES (%s, %s, %s, NOW());

-- name: get_comment_created_time
SELECT comment_created_time FROM comment WHERE comment_id = %s;

-- name: get_comment_owner
SELECT user_id FROM comment WHERE comment_id = %s;

-- name: delete_comment
DELETE FROM comment WHERE comment_id = %s;
