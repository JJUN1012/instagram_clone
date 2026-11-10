CREATE TABLE `post_likes` (
    `user_id` BIGINT NOT NULL,
    `post_id` BIGINT NOT NULL,
    `created_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`user_id`, `post_id`),
    FOREIGN KEY (`user_id`) REFERENCES `user` (`user_id`) ON DELETE CASCADE,
    FOREIGN KEY (`post_id`) REFERENCES `post` (`post_id`) ON DELETE CASCADE
);