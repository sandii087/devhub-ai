from io import BytesIO

from PIL import Image
import pytest
from fastapi.testclient import TestClient

from devhub.main import create_app
from devhub.passwords import validate_password, hash_password, verify_password


def picture(format="PNG"):
    output = BytesIO()
    image = Image.new("RGB", (480, 320), "blue")
    image.save(output, format=format)
    return output.getvalue()


def test_profile_authorization_names_and_readonly_fields(clients):
    one, two = clients("one@example.com"), clients("two@example.com")
    assert one.patch("/api/v1/me", json={"display_name": "  New Name  "}).status_code == 200
    assert one.get("/auth/session").json()["user"]["display_name"] == "New Name"
    assert two.get("/api/v1/me").json()["display_name"] != "New Name"
    for value in ("", " ", "x" * 101):
        assert one.patch("/api/v1/me", json={"display_name": value}).status_code == 422
    assert (
        one.patch("/api/v1/me", json={"display_name": "Name", "email": "other@example.com"}).status_code
        == 422
    )
    assert (
        one.patch("/api/v1/me", json={"display_name": "Name"}, headers={"X-CSRF-Token": "wrong"}).status_code
        == 403
    )
    with TestClient(create_app()) as anonymous:
        assert anonymous.get("/api/v1/me").status_code == 401
        assert anonymous.get("/api/v1/me/avatar").status_code == 401
        assert (
            anonymous.put(
                "/api/v1/me/avatar", content=picture(), headers={"Content-Type": "image/png"}
            ).status_code
            == 401
        )


@pytest.mark.parametrize(
    "format,mime", [("PNG", "image/png"), ("JPEG", "image/jpeg"), ("WEBP", "image/webp")]
)
def test_avatar_persistence_sanitization_and_removal(clients, format, mime):
    one, two = clients("one@example.com"), clients("two@example.com")
    raw = picture(format) + b"discard-this-trailing-payload"
    response = one.put("/api/v1/me/avatar", content=raw, headers={"Content-Type": mime})
    assert response.status_code == 200
    url = response.json()["avatar_url"]
    assert one.get("/auth/session").json()["user"]["avatar_url"] == url
    stored = one.get(url)
    assert stored.status_code == 200 and stored.headers["content-type"] == "image/jpeg"
    assert stored.headers["cache-control"] == "no-store"
    assert b"discard-this-trailing-payload" not in stored.content
    with Image.open(BytesIO(stored.content)) as image:
        assert max(image.size) <= 256 and not image.getexif()
    assert two.get(url).status_code == 404  # Own avatar only, never another user's path.
    assert one.delete("/api/v1/me/avatar").json()["avatar_url"] is None
    assert one.get(url).status_code == 404


def test_invalid_avatar_and_csrf_do_not_change_profile(clients):
    client = clients()
    for data, mime, status in [
        (b'<svg onload="alert(1)"/>', "image/svg+xml", 415),
        (b"../../etc/passwd", "image/png", 422),
        (picture(), "image/jpeg", 422),
        (picture()[:20], "image/png", 422),
        (b"x" * 1_048_577, "image/png", 413),
    ]:
        assert (
            client.put("/api/v1/me/avatar", content=data, headers={"Content-Type": mime}).status_code
            == status
        )
    assert (
        client.put(
            "/api/v1/me/avatar",
            content=picture(),
            headers={"Content-Type": "image/png", "X-CSRF-Token": "bad"},
        ).status_code
        == 403
    )
    assert client.get("/api/v1/me").json()["avatar_url"] is None


def test_avatar_rejects_excessive_pixels_and_animation(clients):
    client = clients()
    output = BytesIO()
    Image.new("RGB", (3000, 3000)).save(output, "PNG")
    assert (
        client.put(
            "/api/v1/me/avatar", content=output.getvalue(), headers={"Content-Type": "image/png"}
        ).status_code
        == 422
    )
    output = BytesIO()
    Image.new("RGB", (10, 10), "red").save(
        output, "PNG", save_all=True, append_images=[Image.new("RGB", (10, 10), "blue")]
    )
    assert (
        client.put(
            "/api/v1/me/avatar", content=output.getvalue(), headers={"Content-Type": "image/png"}
        ).status_code
        == 422
    )


@pytest.mark.parametrize("value", ["Aa1!aaaa", "Aa1_aaaa", "Aa1!" + "a" * 124])
def test_password_policy_accepts_boundaries(value):
    assert validate_password(value) == value


@pytest.mark.parametrize(
    "value", ["Aa1!aaa", "Aa1!" + "a" * 125, "aa1!aaaa", "AA1!AAAA", "Aa!!aaaa", "Aa12aaaa", "Aa12    "]
)
def test_password_policy_rejects_missing_requirement(value):
    with pytest.raises(ValueError):
        validate_password(value)


def test_old_password_hashes_still_verify():
    value = "old passphrase without complexity"
    assert verify_password(value, hash_password(value))
