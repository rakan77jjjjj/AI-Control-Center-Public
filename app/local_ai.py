import json
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_FILE = ROOT / "config" / "local_ai.json"


def load_config():
    return json.loads(
        CONFIG_FILE.read_text(
            encoding="utf-8-sig"
        )
    )


def _request(path, payload=None, timeout=180):
    config = load_config()

    base_url = config.get(
        "base_url",
        "http://127.0.0.1:11434"
    ).rstrip("/")

    url = base_url + path

    data = None
    headers = {
        "Accept": "application/json"
    }

    method = "GET"

    if payload is not None:
        method = "POST"
        data = json.dumps(
            payload
        ).encode("utf-8")
        headers[
            "Content-Type"
        ] = "application/json"

    request = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method=method
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=timeout
        ) as response:
            text = response.read().decode(
                "utf-8"
            )

            return {
                "ok": True,
                "status": response.status,
                "data": json.loads(text)
                if text
                else {}
            }

    except urllib.error.HTTPError as error:
        try:
            body = error.read().decode(
                "utf-8"
            )
        except Exception:
            body = str(error)

        return {
            "ok": False,
            "status": error.code,
            "error": body
        }

    except Exception as error:
        return {
            "ok": False,
            "status": 0,
            "error": str(error)
        }


def health():
    config = load_config()

    result = _request(
        "/api/tags",
        timeout=10
    )

    if not result.get(
        "ok"
    ):
        return {
            "connected": False,
            "model_ready": False,
            "model": config.get(
                "model"
            ),
            "error": result.get(
                "error"
            )
        }

    models = (
        result.get(
            "data",
            {}
        ).get(
            "models",
            []
        )
    )

    target = config.get(
        "model",
        "gpt-oss:20b"
    )

    names = {
        item.get(
            "name"
        )
        for item in models
        if isinstance(
            item,
            dict
        )
    }

    return {
        "connected": True,
        "model_ready": target in names,
        "model": target,
        "models": sorted(
            name
            for name in names
            if name
        )
    }


def chat(
    messages,
    agent=None,
    timeout=600
):
    config = load_config()

    payload = {
        "model": config.get(
            "model",
            "gpt-oss:20b"
        ),
        "messages": messages,
        "stream": False,
        "keep_alive": "10m",
        "options": {
            "num_ctx": int(
                config.get(
                    "context_tokens",
                    8192
                )
            )
        }
    }

    result = _request(
        "/api/chat",
        payload=payload,
        timeout=timeout
    )

    if not result.get(
        "ok"
    ):
        raise RuntimeError(
            result.get(
                "error",
                "Local AI request failed"
            )
        )

    data = result.get(
        "data",
        {}
    )

    message = data.get(
        "message",
        {}
    )

    return {
        "agent": agent,
        "model": data.get(
            "model",
            config.get(
                "model"
            )
        ),
        "content": message.get(
            "content",
            ""
        ),
        "done": data.get(
            "done",
            False
        ),
        "prompt_eval_count": data.get(
            "prompt_eval_count"
        ),
        "eval_count": data.get(
            "eval_count"
        ),
        "total_duration": data.get(
            "total_duration"
        )
    }


if __name__ == "__main__":
    status = health()

    print("")
    print("OLLAMA")
    print(
        "CONNECTED"
        if status.get(
            "connected"
        )
        else "NOT CONNECTED"
    )

    print(
        "MODEL:",
        status.get(
            "model"
        )
    )

    print(
        "MODEL READY:",
        "YES"
        if status.get(
            "model_ready"
        )
        else "NO"
    )

    if not status.get(
        "connected"
    ):
        print(
            "ERROR:",
            status.get(
                "error"
            )
        )
        raise SystemExit(1)

    if not status.get(
        "model_ready"
    ):
        raise SystemExit(2)

    print("")
    print("LOCAL TEST STARTING")

    result = chat(
        [
            {
                "role": "system",
                "content": "You are a local system health test. Reply with exactly LOCAL_OK."
            },
            {
                "role": "user",
                "content": "Run the health check."
            }
        ],
        agent="local_health_test",
        timeout=600
    )

    print(
        "RESPONSE:",
        result.get(
            "content",
            ""
        ).strip()
    )

    print(
        "LOCAL INFERENCE:",
        "READY"
    )

    print(
        "CLOUD API:",
        "NOT USED"
    )
