-- name: check_username_duplicate
SELECT user_id FROM user WHERE user_username = %s;

-- name: update_user_profile
UPDATE user
SET user_name = %s, user_username = %s, user_bio = %s, user_profile_url = %s
WHERE user_id = %s;

-- name: get_user_password
SELECT user_password FROM user WHERE user_id = %s;

-- name: update_user_password
UPDATE user SET user_password = %s WHERE user_id = %s;

-- name: search_users
SELECT user_id, user_username, user_name, user_bio, user_profile_url
FROM user
WHERE user_username LIKE %s OR user_name LIKE %s
ORDER BY user_username ASC
LIMIT 30;

-- name: count_user_posts
SELECT COUNT(*) AS cnt FROM post WHERE user_id = %s;

-- name: count_user_followers
SELECT COUNT(*) AS cnt FROM follows WHERE followee_id = %s;

-- name: count_user_following
SELECT COUNT(*) AS cnt FROM follows WHERE follower_id = %s;

-- name: check_is_following
SELECT 1 FROM follows WHERE follower_id = %s AND followee_id = %s;

-- name: get_user_by_username
SELECT * FROM user WHERE user_username = %s;

-- name: get_user_id_by_username
SELECT user_id FROM user WHERE user_username = %s;

-- name: get_user_posts
SELECT 
    p.post_id, p.post_content, p.post_created_time,
    u.user_id, u.user_username, u.user_name, u.user_profile_url,
    (SELECT COUNT(*) FROM post_likes WHERE post_id = p.post_id) AS like_count,
    (SELECT COUNT(*) FROM comment WHERE post_id = p.post_id) AS comment_count,
    EXISTS(SELECT 1 FROM post_likes WHERE post_id = p.post_id AND user_id = %s) AS liked_by_me,
    EXISTS(SELECT 1 FROM follows WHERE follower_id = %s AND followee_id = u.user_id) AS followed_by_me
FROM post p
JOIN user u ON p.user_id = u.user_id
WHERE p.user_id = %s {where_cursor}
ORDER BY p.post_id DESC
LIMIT %s;

-- name: insert_follow
INSERT IGNORE INTO follows (follower_id, followee_id, follow_time) VALUES (%s, %s, NOW());

-- name: delete_follow
DELETE FROM follows WHERE follower_id = %s AND followee_id = %s;

-- name: get_followers
SELECT u.user_id, u.user_username, u.user_name, u.user_bio, u.user_profile_url
FROM follows f
JOIN user u ON f.follower_id = u.user_id
WHERE f.followee_id = %s {where_cursor}
ORDER BY u.user_id DESC
LIMIT %s;

-- name: get_following
SELECT u.user_id, u.user_username, u.user_name, u.user_bio, u.user_profile_url
FROM follows f
JOIN user u ON f.followee_id = u.user_id
WHERE f.follower_id = %s {where_cursor}
ORDER BY u.user_id DESC
LIMIT %s;
