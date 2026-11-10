-- 1. user 테이블 생성
CREATE TABLE `user` (
    `user_id` BIGINT AUTO_INCREMENT PRIMARY KEY,
    `user_username` VARCHAR(50) NOT NULL,
    `user_name` VARCHAR(50) NOT NULL,
    `user_password` VARCHAR(50) NOT NULL,
    `user_bio` VARCHAR(250),
    `user_profile_url` TEXT
);

-- 2. follows 테이블 생성
CREATE TABLE `follows` (
    `follower_id` BIGINT NOT NULL,
    `followee_id` BIGINT NOT NULL,
    PRIMARY KEY (`follower_id`, `followee_id`),
    FOREIGN KEY (`follower_id`) REFERENCES `user`(`user_id`) ON DELETE CASCADE,
    FOREIGN KEY (`followee_id`) REFERENCES `user`(`user_id`) ON DELETE CASCADE
);
