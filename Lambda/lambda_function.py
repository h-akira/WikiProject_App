import os
# import django
from moto import mock_aws

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'WikiProject.settings')

# # Setup Django
# django.setup()

from mangum import Mangum
from WikiProject.asgi import application

# Create Mangum adapter for ASGI application
mangum_handler = Mangum(application, lifespan="off")

# Determine if we are using mock AWS services
USE_MOCK = os.environ.get('USE_MOCK', 'false').lower() == 'true'

def lambda_handler(event, context):
  if USE_MOCK:
    return mock_main(event, context)
  else:
    return main(event, context)
    
def main(event, context):
  """
  AWS Lambda handler function

  Args:
    event: Lambda event object (API Gateway event)
    context: Lambda context object

  Returns:
    API Gateway response
  """
  # Extract API Gateway stage name from event and set as SCRIPT_NAME
  # This allows Django's FORCE_SCRIPT_NAME to work correctly
  request_context = event.get('requestContext', {})
  stage = request_context.get('stage', '')
  if stage and stage != '$default':
    os.environ['SCRIPT_NAME'] = f'/{stage}'
  else:
    os.environ['SCRIPT_NAME'] = ''

  return mangum_handler(event, context)

@mock_aws
def mock_main(event, context):
  """
  AWS Lambda handler function

  Args:
    event: Lambda event object (API Gateway event)
    context: Lambda context object

  Returns:
    API Gateway response
  """
  from mock.ssm import set_data as set_ssm_data
  set_ssm_data()
  return main(event, context)
