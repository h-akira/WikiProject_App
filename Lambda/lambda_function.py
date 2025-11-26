import os
import boto3
import logging
from moto import mock_aws

logger = logging.getLogger(__name__)

# Load SSM parameters into environment variables before Django initialization
USE_MOCK = os.environ.get('USE_MOCK', 'false').lower() == 'true'
USE_DSQL = os.environ.get('USE_DSQL', 'false').lower() == 'true'

if USE_MOCK:
  # Setup mock SSM
  mock = mock_aws()
  mock.start()
  from mock.ssm import set_data as set_ssm_data
  set_ssm_data()

# Get SSM parameters and set as environment variables
ssm_client = boto3.client('ssm')

os.environ['DJANGO_SECRET_KEY'] = ssm_client.get_parameter(Name='/Django/secret_key')['Parameter']['Value']
os.environ['COGNITO_USER_POOL_ID'] = ssm_client.get_parameter(Name='/Cognito/user_pool_id')['Parameter']['Value']
os.environ['COGNITO_CLIENT_ID'] = ssm_client.get_parameter(Name='/Cognito/client_id')['Parameter']['Value']
os.environ['COGNITO_CLIENT_SECRET'] = ssm_client.get_parameter(Name='/Cognito/client_secret')['Parameter']['Value']

if USE_DSQL:
  os.environ['DSQL_CLUSTER_ENDPOINT'] = ssm_client.get_parameter(Name='/DSQL/cluster_endpoint')['Parameter']['Value']

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'WikiProject.settings')

from mangum import Mangum
from WikiProject.asgi import application

# Create Mangum adapter for ASGI application
mangum_handler = Mangum(application, lifespan="off")


def run_migrations():
  """
  Run Django database migrations

  Returns:
    dict: Response with migration status and output
  """
  import django
  django.setup()
  from django.core.management import call_command
  from io import StringIO

  logger.info("Running database migrations...")
  output = StringIO()
  try:
    call_command('migrate', stdout=output, interactive=False)
    result = output.getvalue()
    logger.info(f"Migration completed successfully:\n{result}")
    return {
      'statusCode': 200,
      'body': {
        'status': 'success',
        'output': result
      }
    }
  except Exception as e:
    error_output = output.getvalue()
    logger.error(f"Migration failed: {e}\n{error_output}")
    return {
      'statusCode': 500,
      'body': {
        'status': 'error',
        'error': str(e),
        'output': error_output
      }
    }


def lambda_handler(event, context):
  """
  AWS Lambda handler function

  Args:
    event: Lambda event object (API Gateway event or custom event)
    context: Lambda context object

  Returns:
    API Gateway response or migration result
  """
  # Check if this is a migration request
  if event.get('action') == 'migrate':
    return run_migrations()

  # Extract API Gateway stage name from event and set as SCRIPT_NAME
  # This allows Django's FORCE_SCRIPT_NAME to work correctly
  request_context = event.get('requestContext', {})
  stage = request_context.get('stage', '')
  if stage and stage != '$default':
    os.environ['SCRIPT_NAME'] = f'/{stage}'
  else:
    os.environ['SCRIPT_NAME'] = ''

  # Apply mock_aws decorator for sam local start-api
  if USE_MOCK:
    with mock_aws():
      return mangum_handler(event, context)
  else:
    return mangum_handler(event, context)
