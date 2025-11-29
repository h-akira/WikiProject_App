from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import json
import boto3
import hmac
import hashlib
import base64
from .models import User
from .decorators import cognito_login_required, cognito_staff_required

# Check if we're in mock mode
if settings.USE_MOCK:
  from mock.cognito import mock_sign_up, mock_initiate_auth, mock_confirm_sign_up


def calculate_secret_hash(username, client_id, client_secret):
  """
  Calculate SECRET_HASH for Cognito authentication
  Required when app client has a secret configured

  Reference: https://github.com/h-akira/wambda/blob/main/lib/wambda/authenticate.py
  """
  message = username + client_id
  dig = hmac.new(
    client_secret.encode('utf-8'),
    msg=message.encode('utf-8'),
    digestmod=hashlib.sha256
  ).digest()
  return base64.b64encode(dig).decode()


@require_http_methods(["GET"])
@cognito_staff_required
def user_list(request):
  """
  List all users (for testing DSQL connection)
  Requires staff authentication via Cognito
  """
  users = User.objects.all().values('id', 'email', 'first_name', 'last_name', 'date_joined')
  return JsonResponse({
    'count': users.count(),
    'users': list(users)
  })


@require_http_methods(["GET"])
@cognito_login_required
def current_user(request):
  """
  Get current authenticated user information
  Demonstrates accessing request.user and request.cognito_claims
  """
  return JsonResponse({
    'email': request.user.email,
    'first_name': request.user.first_name,
    'last_name': request.user.last_name,
    'full_name': request.user.get_full_name(),
    'is_staff': request.user.is_staff,
    'is_superuser': request.user.is_superuser,
    'cognito_username': request.cognito_username,
    'cognito_claims': request.cognito_claims
  })


@require_http_methods(["GET"])
def health_check(request):
  """
  Health check endpoint with database connection test
  """
  try:
    # Test database connection
    user_count = User.objects.count()
    return JsonResponse({
      'status': 'healthy',
      'database': 'connected',
      'user_count': user_count
    })
  except Exception as e:
    return JsonResponse({
      'status': 'unhealthy',
      'database': 'disconnected',
      'error': str(e)
    }, status=500)


@require_http_methods(["GET"])
@cognito_login_required
def protected_page(request):
  """
  Protected page that requires Cognito authentication
  Accessible only with valid JWT token
  """
  return render(request, 'accounts/protected.html', {
    'user': request.user,
    'cognito_username': request.cognito_username,
    'cognito_claims': request.cognito_claims
  })


@require_http_methods(["GET", "POST"])
def login_page(request):
  """
  Login page with form handling
  GET: Display login form
  POST: Process login with Cognito
  """
  if request.method == 'POST':
    username = request.POST.get('username')
    password = request.POST.get('password')

    if not username or not password:
      return render(request, 'accounts/login.html', {
        'error': 'Username and password are required'
      })

    try:
      # Use mock or real Cognito based on environment
      if settings.USE_MOCK:
        # Mock authentication
        response = mock_initiate_auth(
          username=username,
          password=password,
          client_id=settings.COGNITO_CLIENT_ID,
          client_secret=settings.COGNITO_CLIENT_SECRET if hasattr(settings, 'COGNITO_CLIENT_SECRET') else ''
        )
        auth_result = response['AuthenticationResult']
      else:
        # Real Cognito authentication
        client = boto3.client('cognito-idp', region_name=settings.AWS_REGION)
        auth_parameters = {
          'USERNAME': username,
          'PASSWORD': password
        }

        if hasattr(settings, 'COGNITO_CLIENT_SECRET') and settings.COGNITO_CLIENT_SECRET:
          auth_parameters['SECRET_HASH'] = calculate_secret_hash(
            username,
            settings.COGNITO_CLIENT_ID,
            settings.COGNITO_CLIENT_SECRET
          )

        response = client.admin_initiate_auth(
          UserPoolId=settings.COGNITO_USER_POOL_ID,
          ClientId=settings.COGNITO_CLIENT_ID,
          AuthFlow='ADMIN_USER_PASSWORD_AUTH',
          AuthParameters=auth_parameters
        )
        auth_result = response['AuthenticationResult']

      # Set cookies and redirect to home page
      id_token = auth_result['IdToken']
      refresh_token = auth_result['RefreshToken']

      response_redirect = redirect('wiki:index')

      # Set id_token cookie (expires in 1 hour)
      response_redirect.set_cookie(
        'id_token',
        id_token,
        max_age=3600,
        path='/',
        secure=True,
        httponly=True,
        samesite='Strict'
      )

      # Set refresh_token cookie (expires in 30 days)
      response_redirect.set_cookie(
        'refresh_token',
        refresh_token,
        max_age=30*24*3600,  # 30 days
        path='/',
        secure=True,
        httponly=True,
        samesite='Strict'
      )

      return response_redirect

    except Exception as e:
      error_msg = str(e)
      # Handle different error types
      if 'UserNotConfirmedException' in error_msg:
        return render(request, 'accounts/login.html', {
          'error': 'User is not confirmed. Please check your email for confirmation code.',
          'redirect_confirm': True,
          'username': username
        })
      elif 'NotAuthorizedException' in error_msg or 'Incorrect username or password' in error_msg:
        return render(request, 'accounts/login.html', {
          'error': 'Incorrect username or password'
        })
      elif 'UserNotFoundException' in error_msg:
        return render(request, 'accounts/login.html', {
          'error': 'User not found'
        })
      else:
        return render(request, 'accounts/login.html', {
          'error': f'Login failed: {error_msg}'
        })

  # GET request
  return render(request, 'accounts/login.html')


@require_http_methods(["GET", "POST"])
def signup_page(request):
  """
  Sign up page with form handling
  GET: Display signup form
  POST: Process signup with Cognito
  """
  if request.method == 'POST':
    username = request.POST.get('username')
    email = request.POST.get('email')
    password = request.POST.get('password')
    given_name = request.POST.get('given_name', '')
    family_name = request.POST.get('family_name', '')

    if not username or not email or not password:
      return render(request, 'accounts/signup.html', {
        'error': 'Username, email, and password are required'
      })

    try:
      # Use mock or real Cognito based on environment
      if settings.USE_MOCK:
        # Mock signup
        response = mock_sign_up(
          username=username,
          password=password,
          email=email,
          given_name=given_name,
          family_name=family_name,
          client_id=settings.COGNITO_CLIENT_ID,
          client_secret=settings.COGNITO_CLIENT_SECRET if hasattr(settings, 'COGNITO_CLIENT_SECRET') else ''
        )
      else:
        # Real Cognito signup
        client = boto3.client('cognito-idp', region_name=settings.AWS_REGION)
        signup_kwargs = {
          'ClientId': settings.COGNITO_CLIENT_ID,
          'Username': username,
          'Password': password,
          'UserAttributes': [
            {'Name': 'email', 'Value': email},
            {'Name': 'given_name', 'Value': given_name},
            {'Name': 'family_name', 'Value': family_name}
          ]
        }

        if hasattr(settings, 'COGNITO_CLIENT_SECRET') and settings.COGNITO_CLIENT_SECRET:
          signup_kwargs['SecretHash'] = calculate_secret_hash(
            username,
            settings.COGNITO_CLIENT_ID,
            settings.COGNITO_CLIENT_SECRET
          )

        response = client.sign_up(**signup_kwargs)

      # Check if user is confirmed
      user_confirmed = response.get('UserConfirmed', False)

      if user_confirmed:
        # Auto-confirmed, redirect to login
        return render(request, 'accounts/signup.html', {
          'success': 'Account created and confirmed successfully! Please log in.',
          'redirect_login': True
        })
      else:
        # Need confirmation, redirect to confirm page
        return redirect(f"{reverse('confirm_page')}?username={username}")

    except Exception as e:
      error_msg = str(e)
      # Handle different error types
      if 'UsernameExistsException' in error_msg:
        return render(request, 'accounts/signup.html', {
          'error': 'Username already exists'
        })
      elif 'InvalidPasswordException' in error_msg:
        return render(request, 'accounts/signup.html', {
          'error': f'Invalid password: {error_msg}'
        })
      else:
        return render(request, 'accounts/signup.html', {
          'error': f'Sign up failed: {error_msg}'
        })

  # GET request
  return render(request, 'accounts/signup.html')


@require_http_methods(["GET", "POST"])
def confirm_page(request):
  """
  Confirmation code page with form handling
  GET: Display confirmation form
  POST: Confirm user with Cognito
  """
  if request.method == 'POST':
    username = request.POST.get('username')
    code = request.POST.get('code')

    if not username or not code:
      return render(request, 'accounts/confirm.html', {
        'error': 'Username and confirmation code are required',
        'username': username
      })

    try:
      # Use mock or real Cognito based on environment
      if settings.USE_MOCK:
        # Mock confirmation
        mock_confirm_sign_up(
          username=username,
          confirmation_code=code,
          client_id=settings.COGNITO_CLIENT_ID,
          client_secret=settings.COGNITO_CLIENT_SECRET if hasattr(settings, 'COGNITO_CLIENT_SECRET') else ''
        )
      else:
        # Real Cognito confirmation
        client = boto3.client('cognito-idp', region_name=settings.AWS_REGION)
        confirm_kwargs = {
          'ClientId': settings.COGNITO_CLIENT_ID,
          'Username': username,
          'ConfirmationCode': code
        }

        if hasattr(settings, 'COGNITO_CLIENT_SECRET') and settings.COGNITO_CLIENT_SECRET:
          confirm_kwargs['SecretHash'] = calculate_secret_hash(
            username,
            settings.COGNITO_CLIENT_ID,
            settings.COGNITO_CLIENT_SECRET
          )

        client.confirm_sign_up(**confirm_kwargs)

      # Success, redirect to login
      return render(request, 'accounts/confirm.html', {
        'success': 'Account confirmed successfully! Redirecting to login...',
        'redirect_login': True
      })

    except Exception as e:
      error_msg = str(e)
      # Handle different error types
      if 'CodeMismatchException' in error_msg:
        return render(request, 'accounts/confirm.html', {
          'error': 'Invalid confirmation code',
          'username': username
        })
      elif 'ExpiredCodeException' in error_msg:
        return render(request, 'accounts/confirm.html', {
          'error': 'Confirmation code has expired. Please request a new one.',
          'username': username
        })
      else:
        return render(request, 'accounts/confirm.html', {
          'error': f'Confirmation failed: {error_msg}',
          'username': username
        })

  # GET request
  username = request.GET.get('username', '')
  return render(request, 'accounts/confirm.html', {'username': username})


@csrf_exempt
@require_http_methods(["POST"])
def api_login(request):
  """
  Cognito login API endpoint using ADMIN_USER_PASSWORD_AUTH
  Authenticates user with username (or email) and password
  """
  client = boto3.client('cognito-idp', region_name=settings.AWS_REGION)

  try:
    data = json.loads(request.body)
    username = data.get('username')  # Can be username or email (alias)
    password = data.get('password')

    if not username or not password:
      return JsonResponse({'error': 'Username and password required'}, status=400)

    # Prepare auth parameters for ADMIN flow
    auth_parameters = {
      'USERNAME': username,
      'PASSWORD': password
    }

    # ADMIN flow requires SECRET_HASH if client has a secret
    if hasattr(settings, 'COGNITO_CLIENT_SECRET') and settings.COGNITO_CLIENT_SECRET:
      auth_parameters['SECRET_HASH'] = calculate_secret_hash(
        username,
        settings.COGNITO_CLIENT_ID,
        settings.COGNITO_CLIENT_SECRET
      )

    # Authenticate with Cognito using ADMIN flow
    response = client.admin_initiate_auth(
      UserPoolId=settings.COGNITO_USER_POOL_ID,
      ClientId=settings.COGNITO_CLIENT_ID,
      AuthFlow='ADMIN_USER_PASSWORD_AUTH',
      AuthParameters=auth_parameters
    )

    # Return tokens
    return JsonResponse({
      'id_token': response['AuthenticationResult']['IdToken'],
      'access_token': response['AuthenticationResult']['AccessToken'],
      'refresh_token': response['AuthenticationResult']['RefreshToken'],
      'expires_in': response['AuthenticationResult']['ExpiresIn']
    })

  except client.exceptions.NotAuthorizedException:
    return JsonResponse({'error': 'Incorrect username or password'}, status=401)
  except client.exceptions.UserNotFoundException:
    return JsonResponse({'error': 'User not found'}, status=404)
  except Exception as e:
    return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def api_signup(request):
  """
  Cognito sign up API endpoint
  Creates a new user account with username
  """
  client = boto3.client('cognito-idp', region_name=settings.AWS_REGION)

  try:
    data = json.loads(request.body)
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    given_name = data.get('given_name', '')
    family_name = data.get('family_name', '')

    if not username or not email or not password:
      return JsonResponse({'error': 'Username, email, and password required'}, status=400)

    # Prepare signup parameters
    signup_kwargs = {
      'ClientId': settings.COGNITO_CLIENT_ID,
      'Username': username,  # User-chosen username
      'Password': password,
      'UserAttributes': [
        {'Name': 'email', 'Value': email},
        {'Name': 'given_name', 'Value': given_name},
        {'Name': 'family_name', 'Value': family_name}
      ]
    }

    # Add SECRET_HASH if client secret is configured
    if hasattr(settings, 'COGNITO_CLIENT_SECRET') and settings.COGNITO_CLIENT_SECRET:
      signup_kwargs['SecretHash'] = calculate_secret_hash(
        username,
        settings.COGNITO_CLIENT_ID,
        settings.COGNITO_CLIENT_SECRET
      )

    # Sign up with Cognito
    response = client.sign_up(**signup_kwargs)

    return JsonResponse({
      'message': 'User created successfully',
      'user_sub': response['UserSub'],
      'user_confirmed': response['UserConfirmed'],
      'username': username
    })

  except client.exceptions.UsernameExistsException:
    return JsonResponse({'error': 'Username already exists'}, status=409)
  except client.exceptions.InvalidPasswordException as e:
    return JsonResponse({'error': f'Invalid password: {str(e)}'}, status=400)
  except Exception as e:
    return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def api_confirm(request):
  """
  Cognito confirmation API endpoint
  Confirms user account with verification code
  """
  client = boto3.client('cognito-idp', region_name=settings.AWS_REGION)

  try:
    data = json.loads(request.body)
    username = data.get('username')
    code = data.get('code')

    if not username or not code:
      return JsonResponse({'error': 'Username and confirmation code required'}, status=400)

    # Prepare confirmation parameters
    confirm_kwargs = {
      'ClientId': settings.COGNITO_CLIENT_ID,
      'Username': username,
      'ConfirmationCode': code
    }

    # Add SECRET_HASH if client secret is configured
    if hasattr(settings, 'COGNITO_CLIENT_SECRET') and settings.COGNITO_CLIENT_SECRET:
      confirm_kwargs['SecretHash'] = calculate_secret_hash(
        username,
        settings.COGNITO_CLIENT_ID,
        settings.COGNITO_CLIENT_SECRET
      )

    # Confirm sign up with Cognito
    client.confirm_sign_up(**confirm_kwargs)

    return JsonResponse({
      'message': 'Account confirmed successfully'
    })

  except client.exceptions.CodeMismatchException:
    return JsonResponse({'error': 'Invalid verification code'}, status=400)
  except client.exceptions.ExpiredCodeException:
    return JsonResponse({'error': 'Verification code has expired'}, status=400)
  except client.exceptions.NotAuthorizedException as e:
    return JsonResponse({'error': f'User cannot be confirmed: {str(e)}'}, status=401)
  except client.exceptions.UserNotFoundException as e:
    return JsonResponse({'error': f'User not found: {str(e)}'}, status=404)
  except Exception as e:
    return JsonResponse({'error': f'Confirmation failed: {str(e)}'}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def api_resend_code(request):
  """
  Resend confirmation code API endpoint
  Resends verification code to user's email
  """
  client = boto3.client('cognito-idp', region_name=settings.AWS_REGION)

  try:
    data = json.loads(request.body)
    username = data.get('username')

    if not username:
      return JsonResponse({'error': 'Username required'}, status=400)

    # Prepare resend parameters
    resend_kwargs = {
      'ClientId': settings.COGNITO_CLIENT_ID,
      'Username': username
    }

    # Add SECRET_HASH if client secret is configured
    if hasattr(settings, 'COGNITO_CLIENT_SECRET') and settings.COGNITO_CLIENT_SECRET:
      resend_kwargs['SecretHash'] = calculate_secret_hash(
        username,
        settings.COGNITO_CLIENT_ID,
        settings.COGNITO_CLIENT_SECRET
      )

    # Resend confirmation code
    client.resend_confirmation_code(**resend_kwargs)

    return JsonResponse({
      'message': 'Confirmation code resent successfully'
    })

  except client.exceptions.UserNotFoundException:
    return JsonResponse({'error': 'User not found'}, status=404)
  except client.exceptions.InvalidParameterException:
    return JsonResponse({'error': 'User is already confirmed'}, status=400)
  except Exception as e:
    return JsonResponse({'error': str(e)}, status=500)
