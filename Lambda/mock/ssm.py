import boto3
import os

def set_data():
  """SSM Parameter Storeのモックデータを設定"""
  ssm = boto3.client('ssm')

  # 必要なパラメータを設定
  parameters = [
    {
      'Name': '/Django/secret_key',
      'Value': 'django-insecure-vk7dnvxedeket+ayq=ukpo=p^0spk216)zjfzde!orwx3(v8_c',  # This is different from the real one
      'Type': 'String'
    },
    {
      'Name': '/Cognito/user_pool_id',
      'Value': os.environ.get('MOCK_COGNITO_USER_POOL_ID', 'us-east-1_ExamplePoolId'),
      'Type': 'String'
    },
    {
      'Name': '/Cognito/client_id',
      'Value': os.environ.get('MOCK_COGNITO_CLIENT_ID', 'testclientid'),
      'Type': 'String'
    },
    {
      'Name': '/Cognito/client_secret',
      'Value': os.environ.get('MOCK_COGNITO_CLIENT_SECRET', 'testclientsecret'),
      'Type': 'String'
    },
    {
      'Name': '/DSQL/cluster_endpoint',
      'Value': os.environ.get('MOCK_DSQL_CLUSTER_ENDPOINT', 'test-dsql-cluster.dsql.ap-northeast-1.on.aws'),
      'Type': 'String'
    }
  ]
  
  for param in parameters:
    try:
      ssm.put_parameter(
        Name=param['Name'],
        Value=param['Value'],
        Type=param['Type'],
        Overwrite=True
      )
    except Exception as e:
      print(f"SSM parameter setting error: {e}")