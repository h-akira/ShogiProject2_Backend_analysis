import json

from aws_lambda_powertools.event_handler.api_gateway import Router, Response

from common.auth import get_username
from services import analysis_service

router = Router()


@router.post("/")
def create_analysis():
  username = get_username(router)
  body = router.current_event.json_body or {}
  result = analysis_service.create_analysis(username, body)
  return Response(
    status_code=202,
    content_type="application/json",
    body=json.dumps(result),
  )


@router.get("/<aid>")
def get_analysis(aid: str):
  username = get_username(router)
  return analysis_service.get_analysis(username, aid)
