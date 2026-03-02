import json
import os
import logging

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TABLE_NAME = os.environ["DYNAMODB_TABLE_NAME"]

_dynamodb = boto3.resource("dynamodb")
_table = _dynamodb.Table(TABLE_NAME)


def handler(event, context):
  for record in event["Records"]:
    body = json.loads(record["body"])
    username = body["username"]
    aid = body["aid"]

    logger.info(f"DLQ processing: username={username}, aid={aid}")

    _table.update_item(
      Key={"pk": f"USER#{username}", "sk": f"AID#{aid}"},
      UpdateExpression="SET #status = :st, error_message = :em",
      ExpressionAttributeNames={"#status": "status"},
      ExpressionAttributeValues={
        ":st": "failed",
        ":em": "Analysis failed due to infrastructure error",
      },
    )
