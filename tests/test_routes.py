import json

from tests.conftest import make_apigw_event
from repositories import analysis_repository


def _invoke(event):
  from app import lambda_handler
  return lambda_handler(event, {})


def test_create_analysis_202(dynamodb_table, sqs_queue):
  event = make_apigw_event(
    method="POST",
    path="/api/v1/analysis/requests",
    body={
      "sfen": "lnsgkgsnl/1r5b1/ppppppppp/9/9/9/PPPPPPPPP/1B5R1/LNSGKGSNL b - 1",
      "thinking_time": 3000,
    },
    username="testuser",
  )
  response = _invoke(event)

  assert response["statusCode"] == 202
  body = json.loads(response["body"])
  assert "aid" in body
  assert body["status"] == "pending"


def test_create_analysis_400_missing_sfen(dynamodb_table, sqs_queue):
  event = make_apigw_event(
    method="POST",
    path="/api/v1/analysis/requests",
    body={},
    username="testuser",
  )
  response = _invoke(event)

  assert response["statusCode"] == 400
  body = json.loads(response["body"])
  assert "message" in body


def test_create_analysis_400_invalid_thinking_time(dynamodb_table, sqs_queue):
  event = make_apigw_event(
    method="POST",
    path="/api/v1/analysis/requests",
    body={
      "sfen": "lnsgkgsnl/1r5b1/ppppppppp/9/9/9/PPPPPPPPP/1B5R1/LNSGKGSNL b - 1",
      "thinking_time": 9999,
    },
    username="testuser",
  )
  response = _invoke(event)

  assert response["statusCode"] == 400
  body = json.loads(response["body"])
  assert "message" in body


def test_get_analysis_200_pending(dynamodb_table, sqs_queue):
  # Create analysis first
  create_event = make_apigw_event(
    method="POST",
    path="/api/v1/analysis/requests",
    body={
      "sfen": "lnsgkgsnl/1r5b1/ppppppppp/9/9/9/PPPPPPPPP/1B5R1/LNSGKGSNL b - 1",
      "thinking_time": 3000,
    },
    username="testuser",
  )
  create_response = _invoke(create_event)
  aid = json.loads(create_response["body"])["aid"]

  # Get analysis
  get_event = make_apigw_event(
    method="GET",
    path=f"/api/v1/analysis/requests/{aid}",
    username="testuser",
    path_params={"aid": aid},
  )
  response = _invoke(get_event)

  assert response["statusCode"] == 200
  body = json.loads(response["body"])
  assert body["status"] == "pending"
  assert "candidates" not in body


def test_get_analysis_200_completed(dynamodb_table, sqs_queue):
  # Create analysis first
  create_event = make_apigw_event(
    method="POST",
    path="/api/v1/analysis/requests",
    body={
      "sfen": "lnsgkgsnl/1r5b1/ppppppppp/9/9/9/PPPPPPPPP/1B5R1/LNSGKGSNL b - 1",
      "thinking_time": 3000,
    },
    username="testuser",
  )
  create_response = _invoke(create_event)
  aid = json.loads(create_response["body"])["aid"]

  # Simulate worker completing the analysis
  candidates = [
    {"rank": 1, "score": 450, "pv": "7g7f 8c8d 2g2f"},
    {"rank": 2, "score": 420, "pv": "2g2f 8c8d 7g7f"},
    {"rank": 3, "score": 380, "pv": "5i6h 8c8d 7g7f"},
  ]
  analysis_repository.update_status_completed("testuser", aid, candidates)

  # Get analysis
  get_event = make_apigw_event(
    method="GET",
    path=f"/api/v1/analysis/requests/{aid}",
    username="testuser",
    path_params={"aid": aid},
  )
  response = _invoke(get_event)

  assert response["statusCode"] == 200
  body = json.loads(response["body"])
  assert body["status"] == "completed"
  assert len(body["candidates"]) == 3
  assert body["candidates"][0]["rank"] == 1
  assert body["candidates"][0]["score"] == 450


def test_get_analysis_200_failed(dynamodb_table, sqs_queue):
  # Create analysis first
  create_event = make_apigw_event(
    method="POST",
    path="/api/v1/analysis/requests",
    body={
      "sfen": "lnsgkgsnl/1r5b1/ppppppppp/9/9/9/PPPPPPPPP/1B5R1/LNSGKGSNL b - 1",
      "thinking_time": 3000,
    },
    username="testuser",
  )
  create_response = _invoke(create_event)
  aid = json.loads(create_response["body"])["aid"]

  # Simulate worker failure
  analysis_repository.update_status_failed("testuser", aid, "Engine process timed out")

  # Get analysis
  get_event = make_apigw_event(
    method="GET",
    path=f"/api/v1/analysis/requests/{aid}",
    username="testuser",
    path_params={"aid": aid},
  )
  response = _invoke(get_event)

  assert response["statusCode"] == 200
  body = json.loads(response["body"])
  assert body["status"] == "failed"
  assert body["error_message"] == "Engine process timed out"
  assert "candidates" not in body


def test_get_analysis_404(dynamodb_table, sqs_queue):
  get_event = make_apigw_event(
    method="GET",
    path="/api/v1/analysis/requests/nonexistent",
    username="testuser",
    path_params={"aid": "nonexistent"},
  )
  response = _invoke(get_event)

  assert response["statusCode"] == 404
  body = json.loads(response["body"])
  assert "message" in body
