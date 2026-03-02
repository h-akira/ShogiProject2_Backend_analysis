import json
from unittest.mock import patch, MagicMock

import pytest

from common.exceptions import NotFoundError, ValidationError
from services import analysis_service


@pytest.fixture
def mock_repo(dynamodb_table):
  """Provide real DynamoDB via moto for repository operations."""
  return dynamodb_table


@pytest.fixture
def mock_sqs(sqs_queue):
  """Provide real SQS via moto for message operations."""
  with patch.object(analysis_service, "_sqs_client") as mock_client:
    mock_client.send_message = MagicMock()
    yield mock_client


def test_create_analysis_success(mock_repo, mock_sqs):
  result = analysis_service.create_analysis("testuser", {
    "sfen": "lnsgkgsnl/1r5b1/ppppppppp/9/9/9/PPPPPPPPP/1B5R1/LNSGKGSNL b - 1",
    "thinking_time": 3000,
  })

  assert "aid" in result
  assert len(result["aid"]) == 12
  assert result["status"] == "pending"


def test_create_analysis_sqs_message(mock_repo, mock_sqs):
  sfen = "lnsgkgsnl/1r5b1/ppppppppp/9/9/9/PPPPPPPPP/1B5R1/LNSGKGSNL b - 1"
  result = analysis_service.create_analysis("testuser", {
    "sfen": sfen,
    "thinking_time": 5000,
  })

  mock_sqs.send_message.assert_called_once()
  call_kwargs = mock_sqs.send_message.call_args[1]
  body = json.loads(call_kwargs["MessageBody"])

  assert body["username"] == "testuser"
  assert body["aid"] == result["aid"]
  assert body["sfen"] == sfen
  assert body["thinking_time"] == 5000
  assert call_kwargs["MessageGroupId"] == "testuser"
  assert call_kwargs["MessageDeduplicationId"] == result["aid"]


def test_create_analysis_missing_sfen(mock_repo, mock_sqs):
  with pytest.raises(ValidationError, match="sfen is required"):
    analysis_service.create_analysis("testuser", {})


def test_create_analysis_empty_sfen(mock_repo, mock_sqs):
  with pytest.raises(ValidationError, match="sfen is required"):
    analysis_service.create_analysis("testuser", {"sfen": ""})


def test_create_analysis_invalid_thinking_time(mock_repo, mock_sqs):
  with pytest.raises(ValidationError, match="thinking_time must be one of"):
    analysis_service.create_analysis("testuser", {
      "sfen": "lnsgkgsnl/1r5b1/ppppppppp/9/9/9/PPPPPPPPP/1B5R1/LNSGKGSNL b - 1",
      "thinking_time": 2000,
    })


def test_get_analysis_success(mock_repo, mock_sqs):
  result = analysis_service.create_analysis("testuser", {
    "sfen": "lnsgkgsnl/1r5b1/ppppppppp/9/9/9/PPPPPPPPP/1B5R1/LNSGKGSNL b - 1",
    "thinking_time": 3000,
  })

  analysis = analysis_service.get_analysis("testuser", result["aid"])
  assert analysis["aid"] == result["aid"]
  assert analysis["status"] == "pending"
  assert analysis["thinking_time"] == 3000
  assert "created_at" in analysis


def test_get_analysis_not_found(mock_repo, mock_sqs):
  with pytest.raises(NotFoundError, match="Analysis request not found"):
    analysis_service.get_analysis("testuser", "nonexistent")
