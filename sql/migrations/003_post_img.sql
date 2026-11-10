CREATE TABLE post_image(
    post_image_id BIGINT AUTO_INCREMENT,
    post_image_url TEXT NOT NULL,
    post_id BIGINT NOT NULL,
    PRIMARY KEY (post_image_id),
    FOREIGN KEY (post_id) REFERENCES post (post_id) ON DELETE CASCADE
);