import httpx

from app.ui.api import sanitize_chat_reply, user_facing_error


def test_nested_json_error_is_extracted_without_rendering_json():
    response = httpx.Response(
        400,
        json={"error": {"message": "Order reference is invalid."}},
    )

    message = user_facing_error(response)

    assert message == "Order reference is invalid."
    assert "{" not in message


def test_server_error_maps_to_friendly_copy():
    response = httpx.Response(500, json={"detail": "database timeout"})

    assert user_facing_error(response) == "Something went wrong. Please try again shortly."


def test_provider_error_payload_is_not_rendered_in_chat():
    message = sanitize_chat_reply(
        'AI Service Error: {"error":{"message":"User not found.","code":401}}'
    )

    assert "User not found" not in message
    assert message.startswith("I'm having trouble checking the catalog")
