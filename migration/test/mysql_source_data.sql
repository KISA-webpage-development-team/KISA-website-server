-- Fixture data shaped like production, with the cases that actually break a
-- MySQL->Postgres copy: Korean/emoji text, NULLs, both boolean values, quotes,
-- and non-contiguous auto-increment ids (so sequence reset is provable).

INSERT INTO users (email, fullname, bornYear, bornMonth, bornDate, major, gradYear, linkedin, created) VALUES
  ('admin@umich.edu',    'KISA Admin',   2003, 1,  1,  'Computer Science', 2027, 'https://linkedin.com/in/kisaadmin', '2025-09-01 10:00:00'),
  ('student@umich.edu',  '김민준',        2004, 5,  14, '전기컴퓨터공학',      2028, NULL,                                 '2025-09-02 11:30:00'),
  ('quote@umich.edu',    "O'Brien, Sean", 2002, 12, 31, 'Ross School of Business', 2026, NULL,                        '2025-09-03 09:15:00');

INSERT INTO admins (email, created) VALUES ('admin@umich.edu', '2025-09-01 10:05:00');

-- non-contiguous ids: sequence must land past 500, not at 3
INSERT INTO posts (postid, type, email, title, text, isAnnouncement, fullname, readCount, anonymous, created) VALUES
  (1,   'announcement', 'admin@umich.edu',   '2026 신입생 안내',      '<p>환영합니다 🎉</p>',           1, 'KISA Admin', 42, 0, '2025-09-04 12:00:00'),
  (7,   'community',    'student@umich.edu', "It's a test post",     'quotes '' and "double" inside', 0, '김민준',      0,  0, '2025-09-05 13:00:00'),
  (500, 'community',    NULL,                'orphan post',          'author was deleted',            0, '탈퇴회원',    3,  1, '2025-09-06 14:00:00');

INSERT INTO comments (commentid, email, postid, text, isCommentOfComment, parentCommentid, anonymous, secret, created) VALUES
  (1,  'student@umich.edu', 7, '첫 댓글입니다',      0, NULL, 0, 0, '2025-09-05 14:00:00'),
  (2,  'admin@umich.edu',   7, 'reply to the above', 1, 1,    0, 1, '2025-09-05 15:00:00'),
  (88, 'quote@umich.edu',   1, 'anonymous secret',   0, NULL, 1, 1, '2025-09-06 16:00:00');

INSERT INTO postlikes (email, postid, created) VALUES
  ('student@umich.edu', 1, '2025-09-05 10:00:00'),
  ('quote@umich.edu',   1, '2025-09-05 10:01:00'),
  ('admin@umich.edu',   7, '2025-09-05 10:02:00');

INSERT INTO commentlikes (email, commentid, created) VALUES
  ('admin@umich.edu',   1,  '2025-09-05 16:00:00'),
  ('student@umich.edu', 88, '2025-09-06 17:00:00');

INSERT INTO pocha (pochaID, startDate, endDate, title, description) VALUES
  (1,  '2025-10-31 18:00:00', '2025-11-01 02:00:00', '할로윈 포차',  '지난 포차'),
  (12, '2026-08-24 18:00:00', '2026-12-31 23:59:59', '가을 포차',    '진행중인 포차');

INSERT INTO menu (menuID, nameKor, nameEng, category, price, stock, isImmediatePrep, parentPochaID, ageCheckRequired) VALUES
  (1,  '김밥',     'Kimbap',      'food',  5.00,  25, 0, 12, 0),
  (2,  '떡볶이',   'Tteokbokki',  'food',  7.50,  20, 0, 12, 0),
  (3,  '콜라',     'Coke',        'drink', 2.00,  40, 1, 12, 0),
  (40, '소주',     'Soju',        'drink', 12.25, 15, 1, 12, 1);

INSERT INTO `order` (orderID, email, parentPochaID, isPaid) VALUES
  (1,   'student@umich.edu', 1,  1),
  (2,   'admin@umich.edu',   12, 1),
  (300, 'student@umich.edu', 12, 0);

INSERT INTO orderItem (orderItemID, status, quantity, parentOrderID, menuID) VALUES
  (1,    'closed',    2, 1,   1),
  (2,    'ready',     1, 2,   40),
  (3,    'preparing', 3, 2,   2),
  (9000, 'pending',   1, 300, 1);

INSERT INTO notificationARNs (email, endpointARN, created) VALUES
  ('student@umich.edu', 'arn:aws:sns:us-east-2:220688543567:endpoint/APNS_SANDBOX/kisa/abc-123', '2025-09-07 08:00:00');
