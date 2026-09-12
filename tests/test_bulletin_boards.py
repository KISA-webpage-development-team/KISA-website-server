"""Board listings: same JSON as before, one query per request."""

STUDENT = "student@example.com"


def test_first_page_with_counts(bulletin_scenario, client, query_log, golden):
    response = client.get("/api/v2/boards/community/posts/?size=10&page=0")
    assert response.status_code == 200
    golden("board_page0", response.data)
    assert len(query_log) == 1, query_log


def test_last_partial_page(bulletin_scenario, client, query_log, golden):
    response = client.get("/api/v2/boards/community/posts/?size=10&page=1")
    assert response.status_code == 200
    golden("board_page1", response.data)
    assert len(query_log) == 1, query_log


def test_page_past_the_end_is_404(bulletin_scenario, client, golden):
    response = client.get("/api/v2/boards/community/posts/?size=10&page=2")
    assert response.status_code == 404
    golden("board_page_past_end", response.data)


def test_board_without_posts_is_204(bulletin_scenario, client):
    response = client.get("/api/v2/boards/nothing-here/posts/?size=10&page=0")
    assert response.status_code == 204


def test_invalid_pagination_is_400(bulletin_scenario, client, golden):
    response = client.get("/api/v2/boards/community/posts/?size=15&page=0")
    assert response.status_code == 400
    golden("board_bad_pagination", response.data)


def test_announcements_with_comment_counts(bulletin_scenario, client, query_log, golden):
    response = client.get("/api/v2/boards/community/announcements/")
    assert response.status_code == 200
    golden("board_announcements", response.data)
    assert len(query_log) == 1, query_log


def test_user_posts_newest_first_with_comment_counts(bulletin_scenario, client, auth, query_log, golden):
    response = client.get(f"/api/v2/users/{STUDENT}/posts/", headers=auth(STUDENT))
    assert response.status_code == 200
    golden("user_posts_student", response.data)
    # user lookup + one query for the posts
    assert len(query_log) == 2, query_log
