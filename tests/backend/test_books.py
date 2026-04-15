def test_list_books_empty(client):
    res = client.get("/books")
    assert res.status_code == 200
    assert res.json() == []
