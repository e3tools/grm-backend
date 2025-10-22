from django.contrib.auth import authenticate
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.tokens import default_token_generator
from django.shortcuts import get_object_or_404, render
from django.utils.http import urlsafe_base64_decode
from django.utils.translation import gettext_lazy as _
from django.views import View
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import ValidationError
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.constants import (
    CITIZEN_CREATE_ERROR_MESSAGE,
    FACILITATOR_NOT_FOUND_ERROR_MESSAGE,
    INACTIVE_USER_ERROR_MESSAGE,
    INVALID_INPUT_ERROR_MESSAGE,
    LOGIN_ERROR_MESSAGE,
    LOGIN_SUCCESS_MESSAGE,
    PASSWORD_RESET_REQUEST_MESSAGE,
)
from authentication.forms import PasswordResetRequestForm
from authentication.models import Citizen, User
from authentication.serializers import (
    CitizenRegistrationSerializer,
    FacilitatorProfileSerializer,
    LoginSerializer,
    PasswordResetSerializer,
)
from authentication.services import PasswordResetService
from grm.constants import (
    CITIZEN_SUCCESS_MESSAGE,
    EMAIL_ERROR_MESSAGE,
    PASSWORD_CONFIRMATION_ERROR_MESSAGE,
    USERNAME_ERROR_MESSAGE,
    VALIDATION_FAILED_MESSAGE,
)


class BaseLoginAPIView(APIView):
    """
    Base API endpoint for user authentication and token generation.

    Subclasses can extend `extra_validations(user)` to add specific checks
    (e.g., require that the user has a Citizen profile).
    """

    authentication_classes = []  # No authentication required
    permission_classes = []  # No permissions required

    def extra_validations(self, user):
        """
        Hook for subclasses to add extra validation on the authenticated user.
        Must raise a Response if validation fails.
        """
        return None

    def handle_login(self, username, password):
        """
        Core login logic shared by all login views.
        """
        # Check if user exists and active
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            user = None

        if user is not None and not user.is_active:
            return Response(
                {"error": INACTIVE_USER_ERROR_MESSAGE},
                status=status.HTTP_403_FORBIDDEN,
            )

        user = authenticate(username=username, password=password)
        if user is None:
            return Response(
                {"error": LOGIN_ERROR_MESSAGE},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Subclass hook
        extra_error = self.extra_validations(user)
        if extra_error:
            return extra_error

        # Get or create token for the user
        token, _ = Token.objects.get_or_create(user=user)

        return Response(
            {
                "token": token.key,
                "user_id": user.id,
                "username": user.username,
                "message": LOGIN_SUCCESS_MESSAGE,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        """
        Handle POST request for user authentication.

        Validates user credentials and returns authentication token.

        Args:
            request: HTTP request containing username and password

        Returns:
            Response: JSON response with token and user info or error message
        """
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "error": INVALID_INPUT_ERROR_MESSAGE,
                    "details": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        username = serializer.validated_data["username"]
        password = serializer.validated_data["password"]

        return self.handle_login(username, password)


class LoginAPIView(BaseLoginAPIView):
    """
    API endpoint for user authentication and token generation.

    This view authenticates users with username/password and returns
    an authentication token for subsequent API requests.

    Authentication is not required for this endpoint as it's used to obtain tokens.
    """

    @swagger_auto_schema(
        operation_summary="User Login",
        operation_description="Authenticate user credentials and return authentication token.",
        request_body=LoginSerializer,
        responses={
            200: openapi.Response(
                description="Login successful",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'token': openapi.Schema(
                            type=openapi.TYPE_STRING, description="Authentication token for API requests"
                        ),
                        'user_id': openapi.Schema(
                            type=openapi.TYPE_INTEGER, description="Unique identifier for the authenticated user"
                        ),
                        'username': openapi.Schema(
                            type=openapi.TYPE_STRING, description="Username of the authenticated user"
                        ),
                        'message': openapi.Schema(type=openapi.TYPE_STRING, description="Success message"),
                    },
                ),
            ),
            400: openapi.Response(
                description="Bad request - Invalid input data",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'error': openapi.Schema(
                            type=openapi.TYPE_STRING, description="Error message describing the validation issue"
                        ),
                        'details': openapi.Schema(
                            type=openapi.TYPE_OBJECT, description="Field-specific validation errors"
                        ),
                    },
                ),
            ),
            401: openapi.Response(
                description="Unauthorized - Invalid credentials",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'error': openapi.Schema(type=openapi.TYPE_STRING, description="Authentication error message"),
                    },
                ),
            ),
            403: openapi.Response(
                description="Forbidden - User account is inactive",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'error': openapi.Schema(type=openapi.TYPE_STRING, description="Account status error message"),
                    },
                ),
            ),
        },
        tags=['Authentication'],
    )
    def post(self, request):
        return super().post(request)


class CitizenLoginAPIView(BaseLoginAPIView):
    """
    API endpoint for user authentication and token generation.

    This view authenticates users with username/password and returns
    an authentication token for subsequent API requests.

    Authentication is not required for this endpoint as it's used to obtain tokens.
    """

    @swagger_auto_schema(
        operation_summary="Citizen Login",
        operation_description="Authenticate user credentials and return authentication token. "
        "Only users linked to a Citizen profile are allowed.",
        request_body=LoginSerializer,
        responses={
            200: openapi.Response(
                description="Login successful",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'token': openapi.Schema(
                            type=openapi.TYPE_STRING, description="Authentication token for API requests"
                        ),
                        'user_id': openapi.Schema(
                            type=openapi.TYPE_INTEGER, description="Unique identifier for the authenticated user"
                        ),
                        'username': openapi.Schema(
                            type=openapi.TYPE_STRING, description="Username of the authenticated user"
                        ),
                        'message': openapi.Schema(type=openapi.TYPE_STRING, description="Success message"),
                    },
                ),
            ),
            400: openapi.Response(
                description="Bad request - Invalid input data",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'error': openapi.Schema(
                            type=openapi.TYPE_STRING, description="Error message describing the validation issue"
                        ),
                        'details': openapi.Schema(
                            type=openapi.TYPE_OBJECT, description="Field-specific validation errors"
                        ),
                    },
                ),
            ),
            401: openapi.Response(
                description="Unauthorized - Invalid credentials or missing Citizen relation",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'error': openapi.Schema(type=openapi.TYPE_STRING, description="Authentication error message"),
                    },
                ),
            ),
            403: openapi.Response(
                description="Forbidden - User account is inactive",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'error': openapi.Schema(type=openapi.TYPE_STRING, description="Account status error message"),
                    },
                ),
            ),
        },
        tags=['Authentication'],
    )
    def post(self, request):
        return super().post(request)

    def extra_validations(self, user):
        if not hasattr(user, "citizen"):
            return Response(
                {"error": LOGIN_ERROR_MESSAGE},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        return None


class CitizenRegistrationCreateAPIView(CreateAPIView):
    """
    API View for registering new Citizens.

    This view handles the creation of new User accounts and associated Citizen instances.
    No authentication is required for registration.
    """

    serializer_class = CitizenRegistrationSerializer
    authentication_classes = []  # No authentication required
    permission_classes = []  # No permissions required

    @swagger_auto_schema(
        operation_summary="Register a new citizen",
        operation_description="""
        Register a new citizen account. Creates both a User and associated Citizen record.

        **No authentication required for this endpoint.**
        """,
        tags=['Authentication'],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['username', 'phone_number', 'password', 'confirm_password'],
            properties={
                'username': openapi.Schema(
                    type=openapi.TYPE_STRING, description='Unique username for the account', example='john.doe'
                ),
                'first_name': openapi.Schema(
                    type=openapi.TYPE_STRING, description='First name of the citizen', example='John', max_length=150
                ),
                'last_name': openapi.Schema(
                    type=openapi.TYPE_STRING, description='Last name of the citizen', example='Doe', max_length=150
                ),
                'email': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format=openapi.FORMAT_EMAIL,
                    description='Unique email address for the account',
                    example='john.doe@example.com',
                ),
                'phone_number': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Phone number of the citizen',
                    example='987 765 543',
                    max_length=45,
                ),
                'password': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format=openapi.FORMAT_PASSWORD,
                    description='Account password (must meet security requirements)',
                    example='SecurePassword123!',
                ),
                'confirm_password': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format=openapi.FORMAT_PASSWORD,
                    description='Password confirmation (must match password)',
                    example='SecurePassword123!',
                ),
            },
        ),
        responses={
            201: openapi.Response(
                description="Citizen registered successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING, example=CITIZEN_SUCCESS_MESSAGE),
                        'data': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'id': openapi.Schema(type=openapi.TYPE_INTEGER, description='User ID', example=42),
                                'username': openapi.Schema(
                                    type=openapi.TYPE_STRING,
                                    format=openapi.FORMAT_EMAIL,
                                    description='Username',
                                    example='john.doe',
                                ),
                                'email': openapi.Schema(
                                    type=openapi.TYPE_STRING,
                                    format=openapi.FORMAT_EMAIL,
                                    description='User email address',
                                    example='john.doe@example.com',
                                ),
                                'phone_number': openapi.Schema(
                                    type=openapi.TYPE_STRING,
                                    description='User phone number',
                                    example='987 765 543',
                                ),
                                'first_name': openapi.Schema(
                                    type=openapi.TYPE_STRING, description='User first name', example='John'
                                ),
                                'last_name': openapi.Schema(
                                    type=openapi.TYPE_STRING, description='User last name', example='Doe'
                                ),
                            },
                        ),
                    },
                ),
            ),
            400: openapi.Response(
                description="Bad Request - Validation Failed",
                examples={
                    "application/json": {
                        "message": VALIDATION_FAILED_MESSAGE,
                        "errors": {
                            "username": [USERNAME_ERROR_MESSAGE],
                            "email": [EMAIL_ERROR_MESSAGE],
                            "confirm_password": [PASSWORD_CONFIRMATION_ERROR_MESSAGE],
                            "password": ["This password is too short. It must contain at least 8 characters."],
                        },
                    }
                },
            ),
            500: openapi.Response(
                description="Internal Server Error",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING, example=CITIZEN_CREATE_ERROR_MESSAGE)
                    },
                ),
            ),
        },
    )
    def post(self, request, *args, **kwargs):
        """
        Register a new citizen.

        Creates a new User account and associated Citizen record.

        Args:
            request: HTTP request object containing registration data

        Returns:
            Response: JSON response with created user data or error details
        """
        try:
            serializer = self.get_serializer(data=request.data)

            if serializer.is_valid():
                user = serializer.save()

                response_data = {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'phone_number': user.phone_number,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                }

                return Response(
                    {'message': CITIZEN_SUCCESS_MESSAGE, 'data': response_data},
                    status=status.HTTP_201_CREATED,
                )
            else:
                return Response(
                    {'message': VALIDATION_FAILED_MESSAGE, 'errors': serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        except ValidationError as e:
            return Response(
                {'message': VALIDATION_FAILED_MESSAGE, 'errors': e.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return Response(
                {'message': CITIZEN_CREATE_ERROR_MESSAGE, 'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class CitizenDetailAPIView(APIView):
    """
    Retrieve detailed citizen and user information by user primary key,
    including serialized age_group, group, and group_2 from issues serializers.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Retrieve Citizen information by user ID",
        operation_description=(
            "Fetches detailed user and related citizen information, "
            "including serialized fields for `age_group`, `group`, and `group_2`."
        ),
        tags=['Citizens'],
        manual_parameters=[
            openapi.Parameter(
                'user_pk',
                openapi.IN_PATH,
                description='Primary key of the related user',
                type=openapi.TYPE_INTEGER,
                required=True,
            ),
        ],
        responses={
            200: openapi.Response(
                description="Detailed Citizen information retrieved successfully.",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "first_name": openapi.Schema(type=openapi.TYPE_STRING, description="User's first name"),
                        "last_name": openapi.Schema(type=openapi.TYPE_STRING, description="User's last name"),
                        "phone_number": openapi.Schema(type=openapi.TYPE_STRING, description="User's phone number"),
                        "email": openapi.Schema(type=openapi.TYPE_STRING, description="User's email address"),
                        "gender": openapi.Schema(type=openapi.TYPE_STRING, description="Citizen's gender"),
                        "age_group": openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            description="Serialized age group details",
                            properties={
                                "id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Age group ID"),
                                "name": openapi.Schema(type=openapi.TYPE_STRING, description="Age group name"),
                                "created_date": openapi.Schema(type=openapi.TYPE_STRING, format="date-time"),
                                "updated_date": openapi.Schema(type=openapi.TYPE_STRING, format="date-time"),
                            },
                        ),
                        "group": openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            description="Serialized citizen group details",
                            properties={
                                "id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Group ID"),
                                "name": openapi.Schema(type=openapi.TYPE_STRING, description="Group name"),
                                "type": openapi.Schema(type=openapi.TYPE_STRING, description="Group type"),
                                "created_date": openapi.Schema(type=openapi.TYPE_STRING, format="date-time"),
                                "updated_date": openapi.Schema(type=openapi.TYPE_STRING, format="date-time"),
                            },
                        ),
                        "group_2": openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            description="Serialized secondary citizen group details",
                            properties={
                                "id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Group ID"),
                                "name": openapi.Schema(type=openapi.TYPE_STRING, description="Group name"),
                                "type": openapi.Schema(type=openapi.TYPE_STRING, description="Group type"),
                                "created_date": openapi.Schema(type=openapi.TYPE_STRING, format="date-time"),
                                "updated_date": openapi.Schema(type=openapi.TYPE_STRING, format="date-time"),
                            },
                        ),
                        "created_date": openapi.Schema(type=openapi.TYPE_STRING, format="date-time"),
                        "updated_date": openapi.Schema(type=openapi.TYPE_STRING, format="date-time"),
                    },
                ),
            ),
            401: "Unauthorized – authentication credentials not provided or invalid.",
            404: "User or Citizen not found.",
        },
    )
    def get(self, request, user_pk):
        user = get_object_or_404(User, pk=user_pk)
        citizen_auth = get_object_or_404(Citizen, user=user)
        issues_citizen = citizen_auth.citizen

        # Lazy imports to avoid circular imports
        from issues.serializers import CitizenAgeGroupSerializer, CitizenGroupSerializer

        # Serialize related nested objects if they exist
        age_group_data = CitizenAgeGroupSerializer(issues_citizen.age_group).data if issues_citizen.age_group else None
        group_data = CitizenGroupSerializer(issues_citizen.group).data if issues_citizen.group else None
        group_2_data = CitizenGroupSerializer(issues_citizen.group_2).data if issues_citizen.group_2 else None

        data = {
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone_number": user.phone_number,
            "email": user.email,
            "age_group": age_group_data,
            "gender": getattr(issues_citizen, "gender", None),
            "group": group_data,
            "group_2": group_2_data,
            "created_date": issues_citizen.created_date,
            "updated_date": issues_citizen.updated_date,
        }

        return Response(data, status=status.HTTP_200_OK)


class CitizenUpdateAPIView(APIView):
    """
    Update citizen and user fields (PATCH) by user primary key.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Update Citizen and User fields by user ID",
        operation_description=(
            "Allows partial update (PATCH) of fields in both User and related Citizen models. "
            "Supports updating name, phone, email, age group, gender, and group fields."
        ),
        tags=['Citizens'],
        manual_parameters=[
            openapi.Parameter(
                'user_pk',
                openapi.IN_PATH,
                description='Primary key of the related user',
                type=openapi.TYPE_INTEGER,
                required=True,
            ),
        ],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "first_name": openapi.Schema(type=openapi.TYPE_STRING),
                "last_name": openapi.Schema(type=openapi.TYPE_STRING),
                "phone_number": openapi.Schema(type=openapi.TYPE_STRING),
                "email": openapi.Schema(type=openapi.TYPE_STRING),
                "age_group_id": openapi.Schema(type=openapi.TYPE_INTEGER),
                "gender": openapi.Schema(type=openapi.TYPE_STRING),
                "group_id": openapi.Schema(type=openapi.TYPE_INTEGER),
                "group_2_id": openapi.Schema(type=openapi.TYPE_INTEGER),
            },
        ),
        responses={200: "Citizen information updated successfully."},
    )
    def patch(self, request, user_pk):
        user = get_object_or_404(User, pk=user_pk)
        citizen_auth = get_object_or_404(Citizen, user=user)
        issues_citizen = citizen_auth.citizen
        data = request.data

        # Update user fields
        for field in ["first_name", "last_name", "phone_number", "email"]:
            if field in data:
                setattr(user, field, data[field])
        user.save()

        # Update issues citizen fields
        for field in ["age_group_id", "gender", "group_id", "group_2_id"]:
            if field in data:
                setattr(issues_citizen, field, data[field])
        issues_citizen.save()

        response_data = {
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone_number": user.phone_number,
            "email": user.email,
            "age_group_id": getattr(issues_citizen, "age_group_id", None),
            "gender": getattr(issues_citizen, "gender", None),
            "group_id": getattr(issues_citizen, "group_id", None),
            "group_2_id": getattr(issues_citizen, "group_2_id", None),
        }

        return Response(response_data, status=status.HTTP_200_OK)


class PasswordResetAPIView(APIView):
    """
    API endpoint for requesting a password reset.

    This view allows users to request a password reset by providing
    their registered email address. If the email exists in the system,
    a password reset token and UID are generated and sent to the user's email.

    Authentication is not required for this endpoint.
    """

    authentication_classes = []
    permission_classes = []

    @swagger_auto_schema(
        operation_summary="Password Reset Request",
        operation_description="Send password reset instructions to a user via email.",
        request_body=PasswordResetSerializer,
        responses={
            200: openapi.Response(
                description="Password reset email sent successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={"message": openapi.Schema(type=openapi.TYPE_STRING, description="Success message")},
                ),
            ),
            400: openapi.Response(
                description="Invalid input data",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "error": openapi.Schema(type=openapi.TYPE_STRING, description="Error message"),
                        "details": openapi.Schema(type=openapi.TYPE_OBJECT, description="Validation errors"),
                    },
                ),
            ),
        },
        tags=["Authentication"],
    )
    def post(self, request):
        """
        Handle POST request for initiating password reset.

        Args:
            request: HTTP request containing the user's email.

        Returns:
            Response: JSON response with success or error message.
        """
        serializer = PasswordResetSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"error": INVALID_INPUT_ERROR_MESSAGE, "details": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = serializer.validated_data["email"]
        PasswordResetService.handle_password_reset_request(request, email)

        return Response(
            {"message": PASSWORD_RESET_REQUEST_MESSAGE},
            status=status.HTTP_200_OK,
        )


class PasswordResetView(View):
    """
    Django view for requesting a password reset via a form.

    This view:
    - Displays a form to collect the user's email.
    - If valid, sends a password reset email with a reset link.
    - Shows a success message regardless of whether the email exists in the system.
    """

    template_name = "authentication/password_reset_form.html"
    success_template_name = "authentication/password_reset_done.html"

    def get(self, request, *args, **kwargs):
        """Render the password reset request form."""
        form = PasswordResetRequestForm()
        return render(request, self.template_name, {"form": form, "title": _("Password Reset")})

    def post(self, request, *args, **kwargs):
        """Handle form submission for password reset request."""
        form = PasswordResetRequestForm(request.POST)

        if form.is_valid():
            email = form.cleaned_data["email"]
            PasswordResetService.handle_password_reset_request(request, email)
            return render(
                request,
                self.success_template_name,
                {"title": _("Password Reset Sent"), "message": PASSWORD_RESET_REQUEST_MESSAGE},
            )
        return render(request, self.template_name, {"form": form, "title": _("Password Reset")})


class PasswordResetConfirmView(View):
    """
    View to handle password reset confirmation.

    This view is responsible for:
    - Validating the reset token and user.
    - Displaying a form to set a new password.
    - Updating the user's password upon successful form submission.
    - Showing a success message once the password has been reset.
    """

    template_name = "authentication/password_reset_confirm.html"
    success_template_name = "authentication/password_reset_complete.html"

    def get_user(self, uidb64):
        """
        Retrieve the user based on the base64 encoded user ID.
        """
        try:
            uid = urlsafe_base64_decode(uidb64).decode()
            return User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return None

    def get(self, request, uidb64, token):
        """
        Handle GET request.
        If token is valid, display the password reset form.
        If token is invalid, show an error message.
        """
        user = self.get_user(uidb64)

        context = {'title': _("Reset Password"), "validlink": True}

        if user is not None and default_token_generator.check_token(user, token):
            form = SetPasswordForm(user)
            context["form"] = form
        else:
            context["validlink"] = False
        return render(request, self.template_name, context)

    def post(self, request, uidb64, token):
        """
        Handle POST request.
        Validate and save the new password.
        If successful, render a success template instead of the form.
        """
        user = self.get_user(uidb64)

        context = {'title': _("Reset Password"), "validlink": True}

        if user is None or not default_token_generator.check_token(user, token):
            context["validlink"] = False
            return render(request, self.template_name, context)

        form = SetPasswordForm(user, request.POST)
        if form.is_valid():
            form.save()
            # Force a reload of the user so the token is invalidated
            user.refresh_from_db()
            return render(request, self.success_template_name, {"title": _("Password reset complete")})

        context["form"] = form
        return render(request, self.template_name, context)


class FacilitatorProfileAPIView(APIView):
    """
    API endpoint to retrieve the authenticated facilitator's profile information.

    Returns all facilitator fields including department and administrative_region details
    for users with an associated Facilitator profile.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Get Facilitator Profile Information",
        operation_description="""
        Retrieve the authenticated user's complete facilitator profile information.

        Returns all facilitator fields including department and administrative_region details.
        Only accessible to users with an associated Facilitator profile.
        """,
        responses={
            200: openapi.Response(
                description="Facilitator profile information retrieved successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'id': openapi.Schema(type=openapi.TYPE_INTEGER, description='Facilitator ID', example=1),
                        'user': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            description='Associated user information',
                            properties={
                                'id': openapi.Schema(type=openapi.TYPE_INTEGER, example=1),
                                'name': openapi.Schema(type=openapi.TYPE_STRING, example='John Doe'),
                            },
                        ),
                        'department': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            description='Department details',
                            properties={
                                'id': openapi.Schema(type=openapi.TYPE_INTEGER, example=1),
                                'name': openapi.Schema(type=openapi.TYPE_STRING, example='Public Works'),
                                'head': openapi.Schema(type=openapi.TYPE_INTEGER, example=5),
                                'created_date': openapi.Schema(
                                    type=openapi.TYPE_STRING, format=openapi.FORMAT_DATETIME
                                ),
                                'updated_date': openapi.Schema(
                                    type=openapi.TYPE_STRING, format=openapi.FORMAT_DATETIME
                                ),
                            },
                        ),
                        'administrative_region': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'id': openapi.Schema(
                                    type=openapi.TYPE_INTEGER,
                                    example=2,
                                    description="Administrative region ID",
                                ),
                                'name': openapi.Schema(
                                    type=openapi.TYPE_STRING,
                                    example="ALIBORI",
                                    description="Administrative region name",
                                ),
                                'administrative_level': openapi.Schema(
                                    type=openapi.TYPE_INTEGER, example=5, description="Administrative level ID"
                                ),
                                'parent': openapi.Schema(
                                    type=openapi.TYPE_INTEGER,
                                    example=5,
                                    description="Administrative region parent ID",
                                ),
                            },
                            description="Administrative region information",
                        ),
                        'unique_region': openapi.Schema(
                            type=openapi.TYPE_BOOLEAN,
                            description='Indicates if the facilitator has a unique region',
                            example=True,
                        ),
                        'village_secretary': openapi.Schema(
                            type=openapi.TYPE_BOOLEAN,
                            description='Indicates if the facilitator is a village secretary',
                            example=False,
                        ),
                        'created_date': openapi.Schema(
                            type=openapi.TYPE_STRING,
                            format=openapi.FORMAT_DATETIME,
                            description='Profile creation timestamp',
                        ),
                        'updated_date': openapi.Schema(
                            type=openapi.TYPE_STRING,
                            format=openapi.FORMAT_DATETIME,
                            description='Profile last update timestamp',
                        ),
                    },
                ),
            ),
            401: openapi.Response(
                description="Unauthorized - Invalid or missing token",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'detail': openapi.Schema(
                            type=openapi.TYPE_STRING, description='Error message', example='Invalid token.'
                        ),
                    },
                ),
            ),
            404: openapi.Response(
                description="Not Found - User does not have a facilitator profile",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'error': openapi.Schema(
                            type=openapi.TYPE_STRING,
                            description='Error message',
                            example=FACILITATOR_NOT_FOUND_ERROR_MESSAGE,
                        ),
                    },
                ),
            ),
        },
        tags=['Facilitator'],
    )
    def get(self, request):
        """
        Handle GET request to retrieve facilitator profile information.

        Args:
            request: HTTP request object with authenticated user

        Returns:
            Response: JSON response with complete facilitator profile data or error message
        """
        user = request.user

        # Check if user has an associated Facilitator
        if not hasattr(user, 'facilitator'):
            return Response(
                {'error': FACILITATOR_NOT_FOUND_ERROR_MESSAGE},
                status=status.HTTP_404_NOT_FOUND,
            )

        facilitator = user.facilitator

        # Serialize the complete facilitator profile
        serializer = FacilitatorProfileSerializer(facilitator)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )
