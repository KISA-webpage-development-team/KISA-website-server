INSERT INTO admins(email)
VALUES
('wookwan@umich.edu'),
('dongsubk@umich.edu'),
('jiohin@umich.edu');

INSERT INTO users(email, fullname)
VALUES
('dongsubk@umich.edu', '김동섭'),
-- ('jiohin@umich.edu', '인지오'),
('wookwan@umich.edu', '권우관');

INSERT INTO posts(type, title, fullname, email, text, readCount, isAnnouncement)
VALUES
('community', 'test community post 1', '김동섭', 'dongsubk@umich.edu', '인지옹? 앙 인지옹', 0, False),
('community', 'test community post 2', '권우관', 'wookwan@umich.edu', '사퇴하겠습니다.', 0, True),
('community', 'test community post 3', '인지오', 'jiohin@umich.edu', '나? 재능 있어', 0, False),
('community', 'test post with comments 1', '김동섭', 'dongsubk@umich.edu', '무수한 댓글의 요청이...', 0, False),
('community', 'test post with comments 2', '인지오', 'jiohin@umich.edu', '무수한 댓글의 요청이...', 0, False),
('alumni', 'alumni dummy post 1', '김동섭', 'dongsubk@umich.edu', '게시물입니다.', 0, False),
('community', '두번째 페이지 첫번째 게시물', '김동섭', 'dongsubk@umich.edu', '게시물입니다.', 0, False),
('alumni', 'alumni dummy post 2', '김동섭', 'dongsubk@umich.edu', '게시물입니다.', 0, False),
('community', '첫 페이지 마지막 게시물', '김동섭', 'dongsubk@umich.edu', '게시물입니다.', 0, False),
('community', 'dummy post at 7', '김동섭', 'dongsubk@umich.edu', '게시물입니다.', 0, False),
('alumni', 'alumni dummy post 3', '김동섭', 'dongsubk@umich.edu', '게시물입니다.', 0, False),
('community', 'dummy post at 8', '김동섭', 'dongsubk@umich.edu', '게시물입니다.', 0, False),
('community', 'dummy post at 9', '김동섭', 'dongsubk@umich.edu', '게시물입니다.', 0, False),
('community', 'dummy post at 10', '김동섭', 'dongsubk@umich.edu', '게시물입니다.', 0, False),
('community', 'dummy post at 11', '김동섭', 'dongsubk@umich.edu', '게시물입니다.', 0, False),
('community', 'dummy post at 12', '김동섭', 'dongsubk@umich.edu', '게시물입니다.', 0, False),
('community', 'dummy post at 13', '김동섭', 'dongsubk@umich.edu', '게시물입니다.', 0, False),
('community', 'dummy post at 14', '김동섭', 'dongsubk@umich.edu', '게시물입니다.', 0, False),
('community', 'dummy post at 15', '김동섭', 'dongsubk@umich.edu', '게시물입니다.', 0, False);


INSERT INTO comments(email, postid, text, isCommentOfComment, parentCommentid)
VALUES
('dongsubk@umich.edu', 4, '난 너희가 어젯밤에 한 일을 알고 있다...', False, 0),
('wookwan@umich.edu', 4, '이 글은 곧 성지가 됩니다', False, 0),
('jiohin@umich.edu', 4, 'ㅇㄷ', False, 0),
('wookwan@umich.edu', 4, '뭔데 뭔데', True, 1),
('jiohin@umich.edu', 4, 'ㅇㄷ', True, 4),
('dongsubk@umich.edu', 4, '다들 조심하도록 해...', True, 1);

INSERT INTO comments(email, postid, text, isCommentOfComment, parentCommentid)
VALUES
('dongsubk@umich.edu', 5, '난 너희가 어젯밤에 한 일을 알고 있다...', False, 0),
('wookwan@umich.edu', 5, '이 글은 곧 성지가 됩니다', False, 0),
('jiohin@umich.edu', 5, 'ㅇㄷ', False, 0),
('wookwan@umich.edu', 5, '뭔데 뭔데', True, 7),
('jiohin@umich.edu', 5, 'ㅇㄷ', True, 10),
('dongsubk@umich.edu', 5, '다들 조심하도록 해...', True, 7);