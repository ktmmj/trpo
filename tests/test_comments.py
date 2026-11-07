from tests.conftest import auth
from tests.test_tickets import _create_ticket


def test_internal_comment_hidden_from_client(client, client_token, op_token):
    t = _create_ticket(client, client_token)
    client.post(f"/tickets/{t['id']}/comments",
                json={"body": "внутр", "is_internal": True},
                headers=auth(op_token))
    r = client.get(f"/tickets/{t['id']}/comments", headers=auth(client_token))
    assert r.status_code == 200
    assert all(not c["is_internal"] for c in r.json())


def test_client_cannot_mark_internal(client, client_token):
    t = _create_ticket(client, client_token)
    r = client.post(f"/tickets/{t['id']}/comments",
                    json={"body": "x", "is_internal": True},
                    headers=auth(client_token))
    assert r.status_code == 403


def test_comment_on_closed_forbidden(client, client_token, op_token):
    t = _create_ticket(client, client_token)
    client.patch(f"/tickets/{t['id']}/status", json={"status_id": 5},
                 headers=auth(op_token))
    r = client.post(f"/tickets/{t['id']}/comments",
                    json={"body": "x"}, headers=auth(client_token))
    assert r.status_code == 403
