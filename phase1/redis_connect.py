#!/usr/bin/env python3
"""
redis_connect.py

Usage:
  REDIS_URL=redis://127.0.0.1:6380/0 python redis_connect.py
  # or
  REDIS_HOST=127.0.0.1 REDIS_PORT=6380 REDIS_DB=0 python redis_connect.py
"""

import os

import redis


def get_client() -> redis.Redis:
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        return redis.Redis.from_url(redis_url, decode_responses=True)

    host = os.getenv("REDIS_HOST", "127.0.0.1")
    port = int(os.getenv("REDIS_PORT", "6379"))
    db = int(os.getenv("REDIS_DB", "0"))
    password = os.getenv("REDIS_PASSWORD") or None

    return redis.Redis(
        host=host,
        port=port,
        db=db,
        password=password,
        decode_responses=True,
    )


def main() -> None:
    client = get_client()
    client.ping()

    client.set("connection_test", "ok", ex=30)
    value = client.get("connection_test")
    print("Connected to Redis.")
    print("SET/GET test:", value)


if __name__ == "__main__":
    main()
