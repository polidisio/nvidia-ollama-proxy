#!/usr/bin/env python3
"""
Ollama-to-Nvidia API Proxy
Converts Ollama API format to Nvidia AI Foundation-endpoint format.

Usage:
    python3 nvidia_ollama_proxy.py [--port 11435]

Environment variables:
    NVIDIA_API_KEY - Your Nvidia AI Foundation Models API key
"""

import argparse
import json
import logging
import os
import time
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

# ── Config ──────────────────────────────────────────────────────────────────
NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "nvapi-YOUR_API_KEY_HERE")
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"

MODEL_MAP = {
    "nemotron-3-super-120b": "nvidia/nemotron-3-super-120b-a12b",
    "nemotron-nano-12b-vl": "nvidia/nemotron-nano-12b-v2-vl",
    "llama-3.1-70b": "meta/llama-3.1-70b-instruct",
    "llama-3.1-8b": "meta/llama-3.1-8b-instruct",
    "llama-3.3-70b": "meta/llama-3.3-70b-instruct",
    "mistral-large-3": "mistralai/mistral-large-3-675b-instruct-2512",
    "mistral-7b": "mistralai/mistral-7b-instruct-v0.3",
    "deepseek-v4-flash": "deepseek-ai/deepseek-v4-flash",
    "glm-5.1": "z-ai/glm-5.1",
    "minimax-m2.7": "minimaxai/minimax-m2.7",
    "llama3": "meta/llama-3.1-70b-instruct",
    "llama3.1": "meta/llama-3.1-70b-instruct",
}

VISION_MODELS = {"nemotron-nano-12b-vl"}

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("nvidia-proxy")


class OllamaProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):
        log.info(f"{self.address_string()} — {format % args}")

    def send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def send_error(self, status, message):
        self.send_json({"error": message}, status)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/tags":
            self.handle_tags()
        elif parsed.path == "/v1/models":
            models = [{"id": k, "object": "model", "created": 1700000000, "owned_by": "nvidia"} for k in MODEL_MAP.keys()]
            self.send_json({"object": "list", "data": models})
        else:
            self.send_json({"status": "ok", "version": "0.1.0"})

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "/api/chat":
            self.handle_chat()
        elif path == "/api/chat/completions":
            self.handle_chat()
        elif path == "/api/chat/stream":
            self.handle_chat(stream=True)
        elif path == "/v1/chat/completions":
            self.handle_chat()
        elif path == "/api/generate":
            self.handle_generate()
        elif path == "/api/tags":
            self.handle_tags()
        elif path == "/api/models":
            self.handle_tags()
        else:
            self.send_error(404, f"Unknown endpoint: {path}")

    def handle_chat(self, stream=False):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
        except Exception as e:
            return self.send_error(400, f"Bad request: {e}")

        model_name = body.get("model", "llama3")
        nvidia_model = MODEL_MAP.get(model_name, model_name)
        messages = body.get("messages", [])
        stream_flag = stream or body.get("stream", False)

        has_images = any(msg.get("images") or msg.get("image_urls") for msg in messages)
        supports_vision = nvidia_model in VISION_MODELS or "vl" in nvidia_model.lower()

        if has_images and not supports_vision:
            return self.send_error(400, f"Model {model_name} does not support images")

        oai_messages = [{"role": msg.get("role", "user"), "content": msg.get("content", "")} for msg in messages]

        payload = {
            "model": nvidia_model,
            "messages": oai_messages,
            "stream": False,
        }

        for key in ("temperature", "max_tokens", "top_p", "frequency_penalty", "presence_penalty"):
            if key in body:
                payload[key] = body[key]

        nvidia_url = f"{NVIDIA_BASE_URL}/chat/completions"

        try:
            req = urllib.request.Request(
                nvidia_url,
                data=json.dumps(payload).encode(),
                headers={"Authorization": f"Bearer {NVIDIA_API_KEY}", "Content-Type": "application/json"},
                method="POST",
            )
            resp_body = None
            for attempt in range(3):
                try:
                    with urllib.request.urlopen(req, timeout=120) as resp:
                        resp_body = resp.read().decode()
                        if resp_body.strip():
                            break
                except Exception as e:
                    if attempt < 2:
                        wait = 2 ** attempt
                        log.warning(f"Nvidia attempt {attempt+1} failed, retrying in {wait}s: {e}")
                        time.sleep(wait)
                    else:
                        raise

            if not resp_body or not resp_body.strip():
                self.send_error(502, "Nvidia API returned empty response (rate limited?)")
                return
            data = json.loads(resp_body)
            ollama_resp = self.convert_response(data, model_name)
            self.send_json(ollama_resp)

        except urllib.error.HTTPError as e:
            body_err = e.read().decode()
            log.error(f"Nvidia API error {e.code}: {body_err}")
            self.send_error(502, f"Nvidia API error: {body_err[:200]}")
        except json.JSONDecodeError as e:
            log.error(f"Nvidia returned invalid JSON: {e}")
            self.send_error(502, f"Nvidia returned invalid JSON")
        except Exception as e:
            log.error(f"Proxy error: {e}")
            self.send_error(502, str(e))

    def handle_generate(self, stream=False):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
        except Exception as e:
            return self.send_error(400, f"Bad request: {e}")

        model_name = body.get("model", "llama3")
        prompt = body.get("prompt", "")
        messages = [{"role": "user", "content": prompt}]
        body["model"] = model_name
        body["messages"] = messages
        self.handle_chat(stream=stream)

    def handle_tags(self):
        models = []
        for nickname, nvidia_id in MODEL_MAP.items():
            models.append({
                "name": nickname,
                "model": nvidia_id,
                "size": 0,
                "modified_at": "2026-01-01T00:00:00Z",
                "digest": "sha256:0000000000",
            })
        self.send_json({"models": models})

    def convert_response(self, data, model_name):
        try:
            choice = data["choices"][0]
            message = choice.get("message", {})
            content = message.get("content", "")
            return {"model": model_name, "message": {"role": "assistant", "content": content}, "done": True}
        except (KeyError, IndexError) as e:
            log.error(f"Response conversion error: {e} — {data}")
            return {"error": f"Conversion error: {e}", "raw": data}


def main():
    parser = argparse.ArgumentParser(description="Nvidia Ollama API Proxy")
    parser.add_argument("--port", type=int, default=11435, help="Local port")
    args = parser.parse_args()

    server = HTTPServer(("0.0.0.0", args.port), OllamaProxyHandler)
    log.info(f"🚀 Nvidia↔Ollama proxy listening on http://0.0.0.0:{args.port}")
    log.info(f"   Models: {', '.join(MODEL_MAP.keys())}")
    log.info(f"   API Key: {'✓ set' if NVIDIA_API_KEY != 'nvapi-YOUR_API_KEY_HERE' else '✗ NOT SET (set NVIDIA_API_KEY env var)'}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
