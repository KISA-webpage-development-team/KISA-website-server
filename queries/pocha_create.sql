CREATE TABLE ebdb.pocha (
    pochaID INT AUTO_INCREMENT PRIMARY KEY,
    startDate DATETIME NOT NULL,
    endDate DATETIME NOT NULL,
    title VARCHAR(32) NOT NULL,
    description VARCHAR(1024) NOT NULL
);

CREATE TABLE ebdb.menu (
    menuID INT AUTO_INCREMENT PRIMARY KEY,
    nameKor VARCHAR(32) NOT NULL,
    nameEng VARCHAR(32) NOT NULL,
    category VARCHAR(32) NOT NULL,
    price DOUBLE(5,2) NOT NULL,
    stock INT NOT NULL,
    isImmediatePrep TINYINT NOT NULL,
    parentPochaID INT NOT NULL,
    ageCheckRequired TINYINT NOT NULL DEFAULT 0,
    FOREIGN KEY (parentPochaID) REFERENCES ebdb.pocha(pochaID) ON DELETE CASCADE
);

CREATE TABLE ebdb.order (
    orderID INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(40),
    parentPochaID INT NOT NULL,
    isPaid TINYINT NOT NULL DEFAULT 0,
    FOREIGN KEY (parentPochaID) REFERENCES ebdb.pocha(pochaID),
    FOREIGN KEY (email) REFERENCES ebdb.users(email)
);

CREATE TABLE ebdb.orderItem (
    orderItemID INT AUTO_INCREMENT PRIMARY KEY,
    status VARCHAR(16) NOT NULL,
    quantity INT NOT NULL,
    parentOrderID INT NOT NULL,
    menuID INT NOT NULL,
    FOREIGN KEY (parentOrderID) REFERENCES ebdb.order(orderID),
    FOREIGN KEY (menuID) REFERENCES ebdb.menu(menuID)
);
