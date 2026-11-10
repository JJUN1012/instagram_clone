CREATE TABLE `comment` (
    `comment_id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `user_id` BIGINT NOT NULL,
    `post_id` BIGINT NOT NULL,
    `comment_content` VARCHAR(1000) NOT NULL,
    `comment_created_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (`user_id`) REFERENCES `user` (`user_id`) ON DELETE CASCADE,
    FOREIGN KEY (`post_id`) REFERENCES `post` (`post_id`) ON DELETE CASCADE
);