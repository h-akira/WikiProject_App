"""
AWS Cognito JWT authentication middleware for Django
Based on: https://github.com/h-akira/wambda/blob/main/lib/wambda/authenticate.py
Compatible with DSQL (no session dependency)
"""
import jwt
from jwt import PyJWKClient
from django.conf import settings
from django.http import JsonResponse
from accounts.models import User
import boto3
import hmac
import hashlib
import base64


class AnonymousUser:
  """
  Custom AnonymousUser class to avoid django.contrib.contenttypes dependency
  Minimal implementation compatible with DSQL
  """
  @property
  def is_authenticated(self):
    return False

  @property
  def is_anonymous(self):
    return True

  def __str__(self):
    return 'AnonymousUser'

  def __eq__(self, other):
    return isinstance(other, self.__class__)

  def __hash__(self):
    return 1


def calculate_secret_hash(username, client_id, client_secret):
  """
  Calculate SECRET_HASH for Cognito authentication
  Required when app client has a secret configured
  """
  message = username + client_id
  dig = hmac.new(
    client_secret.encode('utf-8'),
    msg=message.encode('utf-8'),
    digestmod=hashlib.sha256
  ).digest()
  return base64.b64encode(dig).decode()


class CognitoAuthMiddleware:
  """
  Middleware to authenticate requests using AWS Cognito JWT tokens

  Supports two authentication methods:
  1. Authorization header: Bearer <token>
  2. Cookie: id_token=<token>

  Auto-refreshes expired tokens using refresh_token cookie
  """

  def __init__(self, get_response):
    self.get_response = get_response

    # Initialize PyJWKClient for fetching Cognito public keys
    region = getattr(settings, 'COGNITO_REGION', 'ap-northeast-1')
    user_pool_id = getattr(settings, 'COGNITO_USER_POOL_ID', '')

    if user_pool_id:
      jwks_url = f'https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/jwks.json'
      self.jwk_client = PyJWKClient(jwks_url)
      self.issuer = f'https://cognito-idp.{region}.amazonaws.com/{user_pool_id}'
      self.client_id = getattr(settings, 'COGNITO_CLIENT_ID', '')
      self.region = region
    else:
      self.jwk_client = None
      self.issuer = None
      self.client_id = None
      self.region = None

  def get_token_from_request(self, request):
    """
    Extract JWT token from request

    Checks in order:
    1. Authorization header (Bearer token)
    2. id_token cookie

    Args:
      request: Django HttpRequest

    Returns:
      str: JWT token or None
    """
    # Check Authorization header
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
      settings.logger.info("Found token in Authorization header")
      return auth_header[7:]  # Remove 'Bearer ' prefix

    # Check id_token cookie
    id_token = request.COOKIES.get('id_token')
    if id_token:
      settings.logger.info("Found token in cookie")
      return id_token

    settings.logger.info(f"No token found. Cookies: {list(request.COOKIES.keys())}")
    return None

  def verify_token(self, token):
    """
    Verify JWT token from Cognito

    Implementation based on:
    https://github.com/h-akira/wambda/blob/main/lib/wambda/authenticate.py

    Args:
      token: JWT token string

    Returns:
      dict: Decoded token claims if valid, None otherwise
    """
    # Mock mode: skip JWT verification
    if settings.USE_MOCK:
      try:
        # Mock tokens are in format: mock-id-{base64_encoded_json}
        if token.startswith('mock-id-'):
          import json
          payload_b64 = token.replace('mock-id-', '')
          payload_json = base64.b64decode(payload_b64).decode('utf-8')
          claims = json.loads(payload_json)
          settings.logger.info(f"Mock token verified for user: {claims.get('cognito:username')}")
          return claims
        else:
          settings.logger.info(f"Invalid mock token format: {token[:20]}...")
          return None
      except Exception as e:
        settings.logger.error(f"Error decoding mock token: {e}")
        return None

    # Real Cognito verification
    if not self.jwk_client or not self.issuer or not self.client_id:
      settings.logger.error("Cognito settings not configured")
      return None

    try:
      # Pre-validate issuer before full verification
      # This avoids PyJWKClient errors with invalid tokens
      unverified_payload = jwt.decode(
        token,
        options={"verify_signature": False}
      )

      if unverified_payload.get('iss') != self.issuer:
        settings.logger.error(f"Invalid issuer: {unverified_payload.get('iss')}")
        return None

      # Get signing key from JWKS
      signing_key = self.jwk_client.get_signing_key_from_jwt(token)

      # Verify token with full validation
      decoded = jwt.decode(
        token,
        signing_key.key,
        algorithms=['RS256'],
        audience=self.client_id,
        issuer=self.issuer
      )

      settings.logger.info(f"Real Cognito token verified for user: {decoded.get('cognito:username')}")
      return decoded

    except jwt.ExpiredSignatureError:
      settings.logger.info("Token has expired")
      return None
    except jwt.InvalidTokenError as e:
      settings.logger.error(f"Invalid token: {e}")
      return None
    except Exception as e:
      settings.logger.error(f"Error verifying token: {e}")
      return None

  def refresh_tokens(self, request):
    """
    Refresh ID token using refresh token from cookie

    Args:
      request: Django HttpRequest

    Returns:
      tuple: (new_id_token, username) or (None, None) if refresh failed
    """
    refresh_token = request.COOKIES.get('refresh_token')
    if not refresh_token:
      settings.logger.info("No refresh_token found in cookies")
      return None, None

    try:
      # Extract username from expired id_token (without full verification)
      old_id_token = request.COOKIES.get('id_token')
      if old_id_token:
        unverified_payload = jwt.decode(
          old_id_token,
          options={"verify_signature": False}
        )
        username = unverified_payload.get('cognito:username')
      else:
        settings.logger.error("No id_token to extract username from")
        return None, None

      # Calculate SECRET_HASH
      client_secret = getattr(settings, 'COGNITO_CLIENT_SECRET', None)
      if not client_secret:
        settings.logger.error("COGNITO_CLIENT_SECRET not configured")
        return None, None

      secret_hash = calculate_secret_hash(username, self.client_id, client_secret)

      # Refresh tokens using Cognito
      client = boto3.client('cognito-idp', region_name=self.region)
      response = client.initiate_auth(
        ClientId=self.client_id,
        AuthFlow='REFRESH_TOKEN_AUTH',
        AuthParameters={
          'REFRESH_TOKEN': refresh_token,
          'SECRET_HASH': secret_hash
        }
      )

      new_id_token = response['AuthenticationResult']['IdToken']
      settings.logger.info(f"Token refreshed successfully for user: {username}")
      return new_id_token, username

    except Exception as e:
      settings.logger.error(f"Error refreshing token: {e}")
      return None, None

  def get_or_create_user(self, cognito_claims):
    """
    Get or create user based on Cognito claims

    Args:
      cognito_claims: Decoded JWT claims from Cognito

    Returns:
      User: User instance or None
    """
    try:
      email = cognito_claims.get('email')
      cognito_username = cognito_claims.get('cognito:username')

      if not cognito_username or not email:
        settings.logger.error("No username or email in token claims")
        return None

      # Get or create user by username (primary identifier)
      user, created = User.objects.get_or_create(
        username=cognito_username,
        defaults={
          'email': email,
          'first_name': cognito_claims.get('given_name', ''),
          'last_name': cognito_claims.get('family_name', ''),
          'is_active': True,
        }
      )

      if created:
        settings.logger.info(f"Created new user: {email}")

      return user

    except Exception as e:
      settings.logger.error(f"Error getting/creating user: {e}")
      return None

  def __call__(self, request):
    """Process request and attach user if authenticated"""
    # Initialize Cognito-specific attributes
    request.cognito_username = None
    request.cognito_claims = None
    new_id_token = None

    # Don't override request.user if already set by AuthenticationMiddleware
    # If not set, initialize as AnonymousUser
    if not hasattr(request, 'user') or request.user is None:
      request.user = AnonymousUser()

    # Get token from request
    token = self.get_token_from_request(request)

    if token:
      # Verify token
      claims = self.verify_token(token)

      # If token verification failed, try to refresh
      if not claims and request.COOKIES.get('refresh_token'):
        settings.logger.info("ID token invalid or expired, attempting to refresh")
        new_id_token, username = self.refresh_tokens(request)

        if new_id_token:
          # Verify the new token
          claims = self.verify_token(new_id_token)

      if claims:
        # Attach claims to request
        request.cognito_claims = claims
        request.cognito_username = claims.get('cognito:username')

        # Get or create user
        user = self.get_or_create_user(claims)
        if user:
          request.user = user

    response = self.get_response(request)

    # Update id_token cookie if token was refreshed
    if new_id_token:
      # Determine if request is secure (HTTPS)
      is_secure = request.is_secure() or request.META.get('HTTP_X_FORWARDED_PROTO') == 'https'

      response.set_cookie(
        'id_token',
        new_id_token,
        max_age=3600,
        path='/',
        secure=is_secure,  # Use secure cookies for HTTPS
        httponly=True,
        samesite='Lax'  # Allow cross-site navigation
      )
      settings.logger.info("Updated id_token cookie after refresh")

    return response
