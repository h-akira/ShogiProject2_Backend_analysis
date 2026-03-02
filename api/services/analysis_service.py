import json
import time
from datetime import datetime, timezone

import boto3

from common.config import SQS_QUEUE_URL
from common.exceptions import NotFoundError, ValidationError
from common.id_generator import generate_id
from repositories import analysis_repository

VALID_THINKING_TIMES = {3000, 5000, 10000}

_sqs_client = boto3.client("sqs")


def _now_iso8601() -> str:
  return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def create_analysis(username: str, body: dict) -> dict:
  sfen = body.get("sfen")
  if not sfen or not isinstance(sfen, str) or not sfen.strip():
    raise ValidationError("sfen is required")

  thinking_time = body.get("thinking_time", 3000)
  if thinking_time not in VALID_THINKING_TIMES:
    raise ValidationError(
      f"thinking_time must be one of {sorted(VALID_THINKING_TIMES)}"
    )

  aid = generate_id()
  now = _now_iso8601()
  ttl = int(time.time()) + 86400

  item = {
    "pk": f"USER#{username}",
    "sk": f"AID#{aid}",
    "aid": aid,
    "username": username,
    "status": "pending",
    "sfen": sfen,
    "thinking_time": thinking_time,
    "created_at": now,
    "ttl": ttl,
  }
  analysis_repository.put_analysis(item)

  message_body = {
    "username": username,
    "aid": aid,
    "sfen": sfen,
    "thinking_time": thinking_time,
  }
  _sqs_client.send_message(
    QueueUrl=SQS_QUEUE_URL,
    MessageBody=json.dumps(message_body),
    MessageGroupId=username,
    MessageDeduplicationId=aid,
  )

  return {"aid": aid, "status": "pending"}


def get_analysis(username: str, aid: str) -> dict:
  item = analysis_repository.get_analysis(username, aid)
  if item is None:
    raise NotFoundError("Analysis request not found")

  result = {
    "aid": item["aid"],
    "status": item["status"],
    "sfen": item["sfen"],
    "thinking_time": int(item["thinking_time"]),
    "created_at": item["created_at"],
  }

  if item["status"] == "completed" and "candidates" in item:
    result["candidates"] = [
      {
        "rank": int(c["rank"]),
        "score": int(c["score"]),
        "pv": c["pv"],
      }
      for c in item["candidates"]
    ]

  if item["status"] == "failed" and "error_message" in item:
    result["error_message"] = item["error_message"]

  return result
