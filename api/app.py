import json

from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler import APIGatewayRestResolver, CORSConfig, Response

from common.exceptions import AppError
from routes.analysis import router as analysis_router

logger = Logger()

app = APIGatewayRestResolver(
  strip_prefixes=["/api/v1/analysis"],
  cors=CORSConfig(
    allow_origin="*",
    allow_headers=["Content-Type", "Authorization"],
    allow_credentials=False,
  ),
)

app.include_router(analysis_router, prefix="/requests")


@app.exception_handler(AppError)
def handle_app_error(ex: AppError):
  return Response(
    status_code=ex.status_code,
    content_type="application/json",
    body=json.dumps({"message": ex.message}),
  )


@app.exception_handler(Exception)
def handle_unexpected_error(ex: Exception):
  logger.exception("Unexpected error")
  return Response(
    status_code=500,
    content_type="application/json",
    body=json.dumps({"message": "Internal server error"}),
  )


def lambda_handler(event, context):
  return app.resolve(event, context)
