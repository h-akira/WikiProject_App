#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
  """Run administrative tasks."""
  import boto3

  # Setup mock SSM if USE_MOCK is enabled
  USE_MOCK = os.environ.get('USE_MOCK', 'false').lower() == 'true'
  USE_DSQL = os.environ.get('USE_DSQL', 'false').lower() == 'true'

  if USE_MOCK:
    from moto import mock_aws

    # Start mock
    mock = mock_aws()
    mock.start()

    # Setup mock SSM data
    from mock.ssm import set_data as set_ssm_data
    set_ssm_data()

  # Get SSM parameters and set as environment variables
  ssm_client = boto3.client('ssm')

  os.environ.setdefault('DJANGO_SECRET_KEY', ssm_client.get_parameter(Name='/Django/secret_key')['Parameter']['Value'])
  os.environ.setdefault('COGNITO_USER_POOL_ID', ssm_client.get_parameter(Name='/Cognito/user_pool_id')['Parameter']['Value'])
  os.environ.setdefault('COGNITO_CLIENT_ID', ssm_client.get_parameter(Name='/Cognito/client_id')['Parameter']['Value'])
  os.environ.setdefault('COGNITO_CLIENT_SECRET', ssm_client.get_parameter(Name='/Cognito/client_secret')['Parameter']['Value'])

  if USE_DSQL:
    os.environ.setdefault('DSQL_CLUSTER_ENDPOINT', ssm_client.get_parameter(Name='/DSQL/cluster_endpoint')['Parameter']['Value'])

  os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'WikiProject.settings')
  try:
    from django.core.management import execute_from_command_line
  except ImportError as exc:
    raise ImportError(
      "Couldn't import Django. Are you sure it's installed and "
      "available on your PYTHONPATH environment variable? Did you "
      "forget to activate a virtual environment?"
    ) from exc
  execute_from_command_line(sys.argv)


if __name__ == '__main__':
  main()
