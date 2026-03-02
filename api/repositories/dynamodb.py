import boto3
from common.config import DYNAMODB_TABLE_NAME

_dynamodb = boto3.resource("dynamodb")
table = _dynamodb.Table(DYNAMODB_TABLE_NAME)
