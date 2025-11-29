import boto3
import hashlib
import hmac
import base64
from datetime import datetime, timedelta
import json

# In-memory storage for mock users
MOCK_USERS = {}
MOCK_CONFIRMATION_CODES = {}

def calculate_secret_hash(username, client_id, client_secret):
  """Calculate SECRET_HASH for Cognito"""
  message = bytes(username + client_id, 'utf-8')
  secret = bytes(client_secret, 'utf-8')
  dig = hmac.new(secret, message, hashlib.sha256).digest()
  return base64.b64encode(dig).decode()

def setup_mock_cognito():
  """
  Setup mock Cognito IDP for local development

  This creates a mock user pool and enables sign up/login functionality
  without requiring actual AWS Cognito service.
  """
  cognito = boto3.client('cognito-idp')

  # Create a test user for development
  test_username = 'testuser'
  test_email = 'test@example.com'
  test_password = 'TestPass123!'

  try:
    # Store test user in mock storage
    MOCK_USERS[test_username] = {
      'username': test_username,
      'email': test_email,
      'password': test_password,
      'confirmed': True,
      'attributes': {
        'email': test_email,
        'email_verified': 'true',
        'given_name': 'Test',
        'family_name': 'User'
      }
    }

    print(f"Mock Cognito setup complete. Test user created: {test_username}")
    print(f"Test credentials - username: {test_username}, password: {test_password}")

  except Exception as e:
    print(f"Mock Cognito setup error: {e}")

def mock_sign_up(username, password, email, given_name='', family_name='', client_id='', client_secret=''):
  """Mock implementation of Cognito sign_up"""

  # Check if user already exists
  if username in MOCK_USERS:
    raise Exception('UsernameExistsException')

  # Validate password (basic validation)
  if len(password) < 8:
    raise Exception('InvalidPasswordException: Password must be at least 8 characters')

  # Create user
  MOCK_USERS[username] = {
    'username': username,
    'email': email,
    'password': password,
    'confirmed': True,  # Auto-confirm in mock environment
    'attributes': {
      'email': email,
      'email_verified': 'true',
      'given_name': given_name,
      'family_name': family_name
    }
  }

  return {
    'UserConfirmed': True,
    'UserSub': f'mock-{username}-sub'
  }

def mock_initiate_auth(username, password, client_id='', client_secret=''):
  """Mock implementation of Cognito initiate_auth"""

  # Check if user exists
  if username not in MOCK_USERS:
    raise Exception('UserNotFoundException')

  user = MOCK_USERS[username]

  # Check password
  if user['password'] != password:
    raise Exception('NotAuthorizedException: Incorrect username or password')

  # Check if user is confirmed
  if not user.get('confirmed', False):
    raise Exception('UserNotConfirmedException')

  # Generate mock JWT token
  token_payload = {
    'sub': f'mock-{username}-sub',
    'cognito:username': username,
    'email': user['attributes']['email'],
    'email_verified': user['attributes']['email_verified'],
    'given_name': user['attributes'].get('given_name', ''),
    'family_name': user['attributes'].get('family_name', ''),
    'exp': int((datetime.now() + timedelta(hours=1)).timestamp())
  }

  # In mock environment, we use a simple base64 encoding instead of real JWT
  mock_token = base64.b64encode(json.dumps(token_payload).encode()).decode()

  return {
    'AuthenticationResult': {
      'AccessToken': f'mock-access-{mock_token}',
      'IdToken': f'mock-id-{mock_token}',
      'RefreshToken': f'mock-refresh-{mock_token}',
      'ExpiresIn': 3600,
      'TokenType': 'Bearer'
    }
  }

def mock_confirm_sign_up(username, confirmation_code, client_id='', client_secret=''):
  """Mock implementation of Cognito confirm_sign_up"""

  # Check if user exists
  if username not in MOCK_USERS:
    raise Exception('UserNotFoundException')

  # In mock environment, accept any confirmation code
  MOCK_USERS[username]['confirmed'] = True

  return {'ResponseMetadata': {'HTTPStatusCode': 200}}
