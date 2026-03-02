import json
import os
import sys

# Set environment variables before any application imports
os.environ["DYNAMODB_TABLE_NAME"] = "test-analysis-table"
os.environ["SQS_QUEUE_URL"] = "https://sqs.ap-northeast-1.amazonaws.com/123456789012/test-queue.fifo"
os.environ["AWS_DEFAULT_REGION"] = "ap-northeast-1"
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"

# Add worker/ to sys.path for test_engine.py
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "worker"))

import pytest
import boto3
from moto import mock_aws


@pytest.fixture
def aws_mock():
  with mock_aws():
    yield


@pytest.fixture
def dynamodb_table(aws_mock):
  dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")
  table = dynamodb.create_table(
    TableName="test-analysis-table",
    KeySchema=[
      {"AttributeName": "pk", "KeyType": "HASH"},
      {"AttributeName": "sk", "KeyType": "RANGE"},
    ],
    AttributeDefinitions=[
      {"AttributeName": "pk", "AttributeType": "S"},
      {"AttributeName": "sk", "AttributeType": "S"},
    ],
    BillingMode="PAY_PER_REQUEST",
  )
  yield table


@pytest.fixture
def sqs_queue(aws_mock):
  sqs = boto3.resource("sqs", region_name="ap-northeast-1")
  queue = sqs.create_queue(
    QueueName="test-queue.fifo",
    Attributes={"FifoQueue": "true"},
  )
  yield queue


def make_apigw_event(
  method: str,
  path: str,
  body: dict | None = None,
  username: str | None = None,
  path_params: dict | None = None,
) -> dict:
  event = {
    "httpMethod": method,
    "path": path,
    "body": json.dumps(body) if body else None,
    "queryStringParameters": None,
    "pathParameters": path_params,
    "headers": {"Content-Type": "application/json"},
    "requestContext": {},
    "multiValueHeaders": {},
    "multiValueQueryStringParameters": None,
    "isBase64Encoded": False,
    "resource": path,
    "stageVariables": None,
  }
  if username:
    event["requestContext"] = {
      "authorizer": {
        "claims": {
          "cognito:username": username,
        },
      },
    }
  return event
