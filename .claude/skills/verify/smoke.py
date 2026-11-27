import argparse
import asyncio
import json
import sys
import time

import httpx
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

PASSWORD = "verify-smoke-password"
COOKIE = "session_token"
READ_ENDPOINTS = (
    "/auth/me",
    "/scenarios",
    "/scenarios/recommendation",
    "/sessions",
    "/weaknesses",
    "/progress",
)
MESSAGE_TIMEOUT_SECONDS = 120


def expect(response: httpx.Response, status: int) -> None:
    line = f"{response.request.method} {response.request.url.path} -> {response.status_code}"
    print(line)
    if response.status_code != status:
        raise SystemExit(f"FAIL: expected {status}: {response.text[:300]}")


def session_cookie(response: httpx.Response) -> str:
    for header in response.headers.get_list("set-cookie"):
        name, _, rest = header.partition("=")
        if name.strip() == COOKIE:
            return rest.split(";", 1)[0]
    raise SystemExit("FAIL: registration set no session cookie")


def check_http(client: httpx.Client) -> str:
    expect(client.get("/auth/me"), 401)
    stamp = int(time.time())
    registered = client.post(
        "/auth/register",
        json={
            "email": f"verify+{stamp}@example.com",
            "password": PASSWORD,
            "first_name": "Verify",
            "last_name": "Smoke",
            "nickname": f"verify_{stamp}",
        },
    )
    expect(registered, 201)
    client.headers["Cookie"] = f"{COOKIE}={session_cookie(registered)}"
    for path in READ_ENDPOINTS:
        expect(client.get(path), 200)
    scenarios = client.get("/scenarios").json()
    if not scenarios:
        raise SystemExit("FAIL: the scenario catalog is empty")
    return scenarios[0]["id"]


async def receive_until(socket, *types: str) -> dict:
    while True:
        raw = await asyncio.wait_for(socket.recv(), MESSAGE_TIMEOUT_SECONDS)
        message = json.loads(raw)
        print(f"ws <- {message['type']}")
        if message["type"] in types:
            return message


async def check_conversation(base_url: str, cookie: str, scenario_id: str) -> None:
    url = base_url.replace("http", "ws", 1)
    uri = f"{url}/practice/sessions/ws?scenario_id={scenario_id}"
    async with connect(uri, additional_headers={"Cookie": cookie}) as socket:
        await receive_until(socket, "session_started")
        await receive_until(socket, "assistant_done")
        await socket.send(
            json.dumps(
                {
                    "type": "user_message",
                    "content": "Hi! I'd like a table for two, please.",
                }
            )
        )
        await receive_until(socket, "assistant_done")
        await socket.send(json.dumps({"type": "end_session"}))
        ended = await receive_until(socket, "session_ended")
        if ended["status"] != "completed":
            raise SystemExit(f"FAIL: session ended as {ended['status']}")
        await receive_until(socket, "analysis_ready", "analysis_failed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8001")
    parser.add_argument("--conversation", action="store_true")
    arguments = parser.parse_args()

    with httpx.Client(base_url=arguments.base_url, timeout=30) as client:
        scenario_id = check_http(client)
        cookie = client.headers["Cookie"]
    if arguments.conversation:
        try:
            asyncio.run(check_conversation(arguments.base_url, cookie, scenario_id))
        except ConnectionClosed as error:
            raise SystemExit(
                f"FAIL: the socket closed with code {error.rcvd.code if error.rcvd else None}; "
                "read the server log"
            ) from None
        except TimeoutError:
            raise SystemExit(
                f"FAIL: no message within {MESSAGE_TIMEOUT_SECONDS}s"
            ) from None
    print("PASS")


if __name__ == "__main__":
    sys.exit(main())
