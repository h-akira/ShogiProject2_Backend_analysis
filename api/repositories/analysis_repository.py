from repositories.dynamodb import table


def _make_key(username: str, aid: str) -> dict:
  return {"pk": f"USER#{username}", "sk": f"AID#{aid}"}


def put_analysis(item: dict) -> None:
  table.put_item(Item=item)


def get_analysis(username: str, aid: str) -> dict | None:
  response = table.get_item(Key=_make_key(username, aid))
  return response.get("Item")


def update_status_running(username: str, aid: str) -> None:
  table.update_item(
    Key=_make_key(username, aid),
    UpdateExpression="SET #status = :st",
    ExpressionAttributeNames={"#status": "status"},
    ExpressionAttributeValues={":st": "running"},
  )


def update_status_completed(username: str, aid: str, candidates: list) -> None:
  table.update_item(
    Key=_make_key(username, aid),
    UpdateExpression="SET #status = :st, candidates = :ca",
    ExpressionAttributeNames={"#status": "status"},
    ExpressionAttributeValues={":st": "completed", ":ca": candidates},
  )


def update_status_failed(username: str, aid: str, error_message: str) -> None:
  table.update_item(
    Key=_make_key(username, aid),
    UpdateExpression="SET #status = :st, error_message = :em",
    ExpressionAttributeNames={"#status": "status"},
    ExpressionAttributeValues={":st": "failed", ":em": error_message},
  )
