from repositories import analysis_repository


def test_put_and_get_analysis(dynamodb_table):
  item = {
    "pk": "USER#testuser",
    "sk": "AID#abc123def456",
    "aid": "abc123def456",
    "username": "testuser",
    "status": "pending",
    "sfen": "lnsgkgsnl/1r5b1/ppppppppp/9/9/9/PPPPPPPPP/1B5R1/LNSGKGSNL b - 1",
    "thinking_time": 3000,
    "created_at": "2025-01-15T09:30:00Z",
    "ttl": 1736934600,
  }
  analysis_repository.put_analysis(item)
  result = analysis_repository.get_analysis("testuser", "abc123def456")

  assert result is not None
  assert result["aid"] == "abc123def456"
  assert result["status"] == "pending"
  assert result["sfen"] == item["sfen"]


def test_get_analysis_not_found(dynamodb_table):
  result = analysis_repository.get_analysis("testuser", "nonexistent")
  assert result is None


def test_get_analysis_wrong_user(dynamodb_table):
  item = {
    "pk": "USER#user1",
    "sk": "AID#abc123def456",
    "aid": "abc123def456",
    "username": "user1",
    "status": "pending",
    "sfen": "lnsgkgsnl/1r5b1/ppppppppp/9/9/9/PPPPPPPPP/1B5R1/LNSGKGSNL b - 1",
    "thinking_time": 3000,
    "created_at": "2025-01-15T09:30:00Z",
    "ttl": 1736934600,
  }
  analysis_repository.put_analysis(item)

  result = analysis_repository.get_analysis("user2", "abc123def456")
  assert result is None


def test_update_status_running(dynamodb_table):
  item = {
    "pk": "USER#testuser",
    "sk": "AID#abc123def456",
    "aid": "abc123def456",
    "username": "testuser",
    "status": "pending",
    "sfen": "lnsgkgsnl/1r5b1/ppppppppp/9/9/9/PPPPPPPPP/1B5R1/LNSGKGSNL b - 1",
    "thinking_time": 3000,
    "created_at": "2025-01-15T09:30:00Z",
    "ttl": 1736934600,
  }
  analysis_repository.put_analysis(item)
  analysis_repository.update_status_running("testuser", "abc123def456")

  result = analysis_repository.get_analysis("testuser", "abc123def456")
  assert result["status"] == "running"


def test_update_status_completed(dynamodb_table):
  item = {
    "pk": "USER#testuser",
    "sk": "AID#abc123def456",
    "aid": "abc123def456",
    "username": "testuser",
    "status": "running",
    "sfen": "lnsgkgsnl/1r5b1/ppppppppp/9/9/9/PPPPPPPPP/1B5R1/LNSGKGSNL b - 1",
    "thinking_time": 3000,
    "created_at": "2025-01-15T09:30:00Z",
    "ttl": 1736934600,
  }
  analysis_repository.put_analysis(item)

  candidates = [
    {"rank": 1, "score": 450, "pv": "7g7f 8c8d 2g2f"},
    {"rank": 2, "score": 420, "pv": "2g2f 8c8d 7g7f"},
    {"rank": 3, "score": 380, "pv": "5i6h 8c8d 7g7f"},
  ]
  analysis_repository.update_status_completed("testuser", "abc123def456", candidates)

  result = analysis_repository.get_analysis("testuser", "abc123def456")
  assert result["status"] == "completed"
  assert len(result["candidates"]) == 3
  assert result["candidates"][0]["rank"] == 1


def test_update_status_failed(dynamodb_table):
  item = {
    "pk": "USER#testuser",
    "sk": "AID#abc123def456",
    "aid": "abc123def456",
    "username": "testuser",
    "status": "running",
    "sfen": "lnsgkgsnl/1r5b1/ppppppppp/9/9/9/PPPPPPPPP/1B5R1/LNSGKGSNL b - 1",
    "thinking_time": 3000,
    "created_at": "2025-01-15T09:30:00Z",
    "ttl": 1736934600,
  }
  analysis_repository.put_analysis(item)
  analysis_repository.update_status_failed("testuser", "abc123def456", "Engine process timed out")

  result = analysis_repository.get_analysis("testuser", "abc123def456")
  assert result["status"] == "failed"
  assert result["error_message"] == "Engine process timed out"
