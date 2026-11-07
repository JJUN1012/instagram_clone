
-- post table
CREATE TABLE post(
    post_id BIGINT,
    post_content VARCHAR(2000),
    created_time DATETIME NOT NULL,
    user_id BIGINT,
    PRIMARY KEY (post_id),
    FOREIGN KEY (user_id) REFERENCES user(user_id)
);

-- ALTER for NOT NULL of user_id
ALTER TABLE post MODIFY user_id BIGINT NOT NULL;

-- Check Constraints
SHOW CREATE TABLE post;

-- ALTER for ON DELETE CASCADE of user_id
ALTER TABLE post DROP FOREIGN KEY post_ibfk_1,
    ADD FOREIGN KEY (user_id) REFERENCES user(user_id) ON DELETE CASCADE;

SELECT * FROM post;