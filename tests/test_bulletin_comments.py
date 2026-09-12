"""Comment threads: same nested JSON as before, one query per post."""


def test_nested_comments_with_likes_and_names(bulletin_scenario, client, query_log, golden):
    response = client.get("/api/v2/comments/1/")
    assert response.status_code == 200
    golden("comments_post1", response.data)
    assert len(query_log) == 1, query_log


def test_post_without_comments_is_empty_list(bulletin_scenario, client, golden):
    response = client.get("/api/v2/comments/12/")
    assert response.status_code == 200
    golden("comments_none", response.data)
