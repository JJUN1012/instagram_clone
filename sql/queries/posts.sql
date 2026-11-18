-- name: get_post_images
SELECT post_id, post_image_url
FROM post_image
WHERE post_id IN ({placeholders})
ORDER BY post_image_id ASC;

-- name: get_feed
SELECT 
    p.post_id, p.post_content, p.post_created_time,
    u.user_id, u.user_username, u.user_name, u.user_profile_url,
    (SELECT COUNT(*) FROM post_likes WHERE post_id = p.post_id) AS like_count,
    (SELECT COUNT(*) FROM comment WHERE post_id = p.post_id) AS comment_count,
    EXISTS(SELECT 1 FROM post_likes WHERE post_id = p.post_id AND user_id = %s) AS liked_by_me,
    EXISTS(SELECT 1 FROM follows WHERE follower_id = %s AND followee_id = u.user_id) AS followed_by_me
FROM post p
JOIN user u ON p.user_id = u.user_id
{where_clause}
ORDER BY p.post_id DESC
LIMIT %s;

-- name: insert_post
INSERT INTO post (post_content, post_created_time, user_id) VALUES (%s, NOW(), %s);

-- name: insert_post_image
INSERT INTO post_image (post_image_url, post_id) VALUES (%s, %s);

-- name: get_post_detail
SELECT 
    p.post_id, p.post_content, p.post_created_time,
    u.user_id, u.user_username, u.user_name, u.user_profile_url,
    (SELECT COUNT(*) FROM post_likes WHERE post_id = p.post_id) AS like_count,
    (SELECT COUNT(*) FROM comment WHERE post_id = p.post_id) AS comment_count,
    EXISTS(SELECT 1 FROM post_likes WHERE post_id = p.post_id AND user_id = %s) AS liked_by_me,
    EXISTS(SELECT 1 FROM follows WHERE follower_id = %s AND followee_id = u.user_id) AS followed_by_me
FROM post p
JOIN user u ON p.user_id = u.user_id
WHERE p.post_id = %s;

-- name: get_post_owner
SELECT user_id FROM post WHERE post_id = %s;

-- name: delete_post_images
DELETE FROM post_image WHERE post_id = %s;

-- name: delete_post_likes
DELETE FROM post_likes WHERE post_id = %s;

-- name: delete_post_comments
DELETE FROM comment WHERE post_id = %s;

-- name: delete_post
DELETE FROM post WHERE post_id = %s;
