import json
import os
import logging

import boto3

from engine import ShogiEngine, EngineError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ENGINE_PATH = "/var/task/Engine/YaneuraOu-by-gcc"
TABLE_NAME = os.environ["DYNAMODB_TABLE_NAME"]

_dynamodb = boto3.resource("dynamodb")
_table = _dynamodb.Table(TABLE_NAME)


def handler(event, context):
  for record in event["Records"]:
    body = json.loads(record["body"])
    username = body["username"]
    aid = body["aid"]
    sfen = body["sfen"]
    thinking_time = body["thinking_time"]

    pk = f"USER#{username}"
    sk = f"AID#{aid}"

    logger.info(f"Processing analysis: username={username}, aid={aid}")

    # Update status to running
    _table.update_item(
      Key={"pk": pk, "sk": sk},
      UpdateExpression="SET #status = :st",
      ExpressionAttributeNames={"#status": "status"},
      ExpressionAttributeValues={":st": "running"},
    )

    engine = None
    try:
      engine = ShogiEngine(ENGINE_PATH)
      engine.start()
      candidates = engine.analyze(sfen, thinking_time)

      # Update status to completed
      _table.update_item(
        Key={"pk": pk, "sk": sk},
        UpdateExpression="SET #status = :st, candidates = :ca",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={":st": "completed", ":ca": candidates},
      )
      logger.info(f"Analysis completed: aid={aid}")
    except Exception as e:
      logger.error(f"Analysis failed: aid={aid}, error={e}")
      # Update status to failed
      _table.update_item(
        Key={"pk": pk, "sk": sk},
        UpdateExpression="SET #status = :st, error_message = :em",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={":st": "failed", ":em": str(e)},
      )
    finally:
      if engine:
        engine.quit()
