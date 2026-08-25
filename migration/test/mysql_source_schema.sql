-- Source-side (AWS RDS MySQL) schema, reconstructed for migration testing.
-- pocha/menu/order/orderItem and notificationARNs are verbatim from the repo's
-- queries/*.sql; users/admins/posts/comments/*likes are reconstructed from
-- supabase_schema.sql plus the columns the Flask SQL actually reads and writes.

CREATE TABLE users (
    email VARCHAR(40) PRIMARY KEY,
    fullname VARCHAR(255) NOT NULL,
    bornYear INT NOT NULL,
    bornMonth INT NOT NULL,
    bornDate INT NOT NULL,
    major VARCHAR(255) NOT NULL,
    gradYear INT NOT NULL,
    linkedin TEXT,
    created DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE admins (
    email VARCHAR(40) PRIMARY KEY,
    created DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (email) REFERENCES users(email) ON DELETE CASCADE
);

CREATE TABLE posts (
    postid INT AUTO_INCREMENT PRIMARY KEY,
    type VARCHAR(64) NOT NULL,
    email VARCHAR(40),
    title VARCHAR(255) NOT NULL,
    text TEXT NOT NULL,
    isAnnouncement TINYINT NOT NULL DEFAULT 0,
    fullname VARCHAR(255) NOT NULL,
    readCount INT NOT NULL DEFAULT 0,
    anonymous TINYINT NOT NULL DEFAULT 0,
    created DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (email) REFERENCES users(email) ON DELETE SET NULL
);

CREATE TABLE comments (
    commentid INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(40) NOT NULL,
    postid INT NOT NULL,
    text TEXT NOT NULL,
    isCommentOfComment TINYINT NOT NULL DEFAULT 0,
    parentCommentid INT,
    anonymous TINYINT NOT NULL DEFAULT 0,
    secret TINYINT NOT NULL DEFAULT 0,
    created DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (email) REFERENCES users(email) ON DELETE CASCADE,
    FOREIGN KEY (postid) REFERENCES posts(postid) ON DELETE CASCADE,
    FOREIGN KEY (parentCommentid) REFERENCES comments(commentid) ON DELETE CASCADE
);

CREATE TABLE postlikes (
    email VARCHAR(40) NOT NULL,
    postid INT NOT NULL,
    created DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (email, postid),
    FOREIGN KEY (email) REFERENCES users(email) ON DELETE CASCADE,
    FOREIGN KEY (postid) REFERENCES posts(postid) ON DELETE CASCADE
);

CREATE TABLE commentlikes (
    email VARCHAR(40) NOT NULL,
    commentid INT NOT NULL,
    created DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (email, commentid),
    FOREIGN KEY (email) REFERENCES users(email) ON DELETE CASCADE,
    FOREIGN KEY (commentid) REFERENCES comments(commentid) ON DELETE CASCADE
);

-- verbatim from queries/pocha_create.sql (ebdb. prefix dropped)
CREATE TABLE pocha (
    pochaID INT AUTO_INCREMENT PRIMARY KEY,
    startDate DATETIME NOT NULL,
    endDate DATETIME NOT NULL,
    title VARCHAR(32) NOT NULL,
    description VARCHAR(1024) NOT NULL
);

CREATE TABLE menu (
    menuID INT AUTO_INCREMENT PRIMARY KEY,
    nameKor VARCHAR(32) NOT NULL,
    nameEng VARCHAR(32) NOT NULL,
    category VARCHAR(32) NOT NULL,
    price DOUBLE(5,2) NOT NULL,
    stock INT NOT NULL,
    isImmediatePrep TINYINT NOT NULL,
    parentPochaID INT NOT NULL,
    ageCheckRequired TINYINT NOT NULL DEFAULT 0,
    FOREIGN KEY (parentPochaID) REFERENCES pocha(pochaID) ON DELETE CASCADE
);

CREATE TABLE `order` (
    orderID INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(40),
    parentPochaID INT NOT NULL,
    isPaid TINYINT NOT NULL DEFAULT 0,
    FOREIGN KEY (parentPochaID) REFERENCES pocha(pochaID),
    FOREIGN KEY (email) REFERENCES users(email)
);

CREATE TABLE orderItem (
    orderItemID INT AUTO_INCREMENT PRIMARY KEY,
    status VARCHAR(16) NOT NULL,
    quantity INT NOT NULL,
    parentOrderID INT NOT NULL,
    menuID INT NOT NULL,
    FOREIGN KEY (parentOrderID) REFERENCES `order`(orderID),
    FOREIGN KEY (menuID) REFERENCES menu(menuID)
);

-- verbatim from queries/notification_tokens_create.sql (ebdb. prefix dropped)
CREATE TABLE notificationARNs (
    email VARCHAR(40) PRIMARY KEY,
    endpointARN TEXT NOT NULL,
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_email FOREIGN KEY (email) REFERENCES users(email) ON DELETE CASCADE
);
