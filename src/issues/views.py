from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.generics import CreateAPIView, ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from dashboard.grm.constants import (
    CONTACT_INFO_EMAIL_ERROR_MESSAGE,
    CONTACT_MEDIUM_ERROR_MESSAGE,
)
from issues.models import Issue, IssueCategory, IssueStatus, IssueType
from issues.serializers import (
    IssueCategorySerializer,
    IssueCreateSerializer,
    IssueDetailSerializer,
    IssueSerializer,
    IssueStatusSerializer,
    IssueTypeSerializer,
)


class IssueCreateAPIView(CreateAPIView):
    """
    API View for creating new Issue objects.

    This view handles the creation of new Issue instances with proper validation
    and error handling. It requires Token authentication and validates all required fields.
    """

    queryset = Issue.objects.all()
    serializer_class = IssueCreateSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=[
                'title',
                'description',
                'category',
                'issue_type',
                'issue_sub_type',
                'contact_medium',
                'tracking_code',
                'intake_date',
                'administrative_region',
            ],
            properties={
                'title': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Brief title describing the issue',
                    example='Water supply problem in downtown area',
                ),
                'description': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Detailed description of the issue',
                    example='The water supply has been intermittent for the past 3 days affecting 200+ households',
                ),
                'category': openapi.Schema(
                    type=openapi.TYPE_INTEGER, description='ID of the issue category', example=1
                ),
                'issue_type': openapi.Schema(
                    type=openapi.TYPE_STRING, description='Type of the issue', example='infrastructure'
                ),
                'issue_sub_type': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Sub-type of the issue for more specific classification',
                    example='water_supply',
                ),
                'contact_medium': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Medium through which the issue was reported',
                    enum=['phone', 'email', 'web', 'in_person', 'alert', 'anonymous'],
                    example='web',
                ),
                'contact_method': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Specific contact method (required if contact_medium is "alert")',
                    enum=['email', 'phone_number', 'whatsapp', 'sms'],
                    example='email',
                ),
                'contact_information': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Contact details (email/phone based on contact_method)',
                    example='citizen@example.com',
                ),
                'tracking_code': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Unique tracking code for the issue',
                    example='ISS-2024-001234',
                ),
                'intake_date': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    format=openapi.FORMAT_DATETIME,
                    description='Date and time when the issue was reported',
                    example='2024-08-28T10:30:00Z',
                ),
                'ongoing_issue': openapi.Schema(
                    type=openapi.TYPE_BOOLEAN,
                    description='Whether this is an ongoing issue',
                    default=False,
                    example=True,
                ),
                'location_description': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Textual description of where the issue occurred',
                    example='Corner of Main Street and 5th Avenue, near the central plaza',
                ),
                'status': openapi.Schema(
                    type=openapi.TYPE_INTEGER, description='Initial status ID for the issue (optional)', example=1
                ),
                'administrative_region': openapi.Schema(
                    type=openapi.TYPE_INTEGER,
                    description='ID of the administrative region where the issue occurred',
                    example=5,
                ),
                'component': openapi.Schema(
                    type=openapi.TYPE_INTEGER, description='ID of the system component related to the issue', example=3
                ),
                'sub_component': openapi.Schema(
                    type=openapi.TYPE_INTEGER, description='ID of the system sub-component', example=7
                ),
                'citizen': openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    description='Information about the citizen reporting the issue',
                    properties={
                        'name': openapi.Schema(
                            type=openapi.TYPE_STRING, description='Full name of the citizen', example='John Doe'
                        ),
                        'age_group': openapi.Schema(
                            type=openapi.TYPE_STRING, description='Age group classification', example='adult'
                        ),
                        'type': openapi.Schema(
                            type=openapi.TYPE_STRING, description='Citizen type classification', example='individual'
                        ),
                        'group': openapi.Schema(
                            type=openapi.TYPE_STRING, description='Primary group classification', example='general'
                        ),
                        'group_2': openapi.Schema(
                            type=openapi.TYPE_STRING, description='Secondary group classification', example='urban'
                        ),
                    },
                ),
            },
        ),
        responses={
            201: IssueDetailSerializer,
            400: openapi.Response(
                description="Bad Request - Validation Failed",
                examples={
                    "application/json": {
                        "message": "Validation failed.",
                        "errors": {
                            "title": ["This field is required."],
                            "category": ["This field is required."],
                            "issue_type": ["This field is required."],
                            "administrative_region": ["This field is required."],
                            "contact_method": [CONTACT_MEDIUM_ERROR_MESSAGE],
                            "contact_information": [CONTACT_INFO_EMAIL_ERROR_MESSAGE],
                        },
                    }
                },
            ),
            401: openapi.Response(
                description="Unauthorized - Invalid or missing token",
                examples={"application/json": {"detail": "Invalid token."}},
            ),
            500: openapi.Response(
                description="Internal Server Error",
                examples={
                    "application/json": {
                        "message": "An error occurred while creating the issue.",
                        "error": "Error details",
                    }
                },
            ),
        },
        operation_summary="Create an issue",
        operation_description="Create an issue",
        tags=['Issues'],
        security=[{'Token': []}],  # References the Token security definition
    )
    def post(self, request, *args, **kwargs):
        """
        Create a new Issue instance.

        Overrides the default create method to provide custom response format
        and error handling.

        Args:
            request: HTTP request object containing issue data

        Returns:
            Response: JSON response with created issue data or error details
        """
        try:
            serializer = self.get_serializer(data=request.data)

            if serializer.is_valid():
                issue = serializer.save()
                detail_serializer = IssueDetailSerializer(issue)
                return Response(
                    {'message': _('Issue created successfully.'), 'data': detail_serializer.data},
                    status=status.HTTP_201_CREATED,
                )
            else:
                return Response(
                    {'message': _('Validation failed.'), 'errors': serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        except ValidationError as e:
            return Response(
                {'message': _('Validation failed.'), 'errors': e.message_dict},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return Response(
                {'message': _('An error occurred while creating the issue.'), 'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class IssueListAPIView(ListAPIView):
    """
    API View for listing Issue objects with pagination.

    This view provides a paginated read-only list of all available issues.
    It requires Token authentication and returns paginated results.
    """

    # Optimize database queries by selecting related objects
    queryset = Issue.objects.select_related(
        'status', 'category', 'issue_type', 'administrative_region', 'reporter', 'assignee'
    ).all()
    serializer_class = IssueSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                'page', openapi.IN_QUERY, description="Page number for pagination", type=openapi.TYPE_INTEGER, default=1
            ),
            openapi.Parameter(
                'page_size',
                openapi.IN_QUERY,
                description="Number of results per page (max: 100)",
                type=openapi.TYPE_INTEGER,
                default=20,
            ),
        ],
        responses={
            200: openapi.Response(
                description="Paginated list of issues",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'next': openapi.Schema(
                            type=openapi.TYPE_STRING,
                            format=openapi.FORMAT_URI,
                            description='URL to next page (null if no next page)',
                            nullable=True,
                        ),
                        'previous': openapi.Schema(
                            type=openapi.TYPE_STRING,
                            format=openapi.FORMAT_URI,
                            description='URL to previous page (null if no previous page)',
                            nullable=True,
                        ),
                        'results': openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            description='Array of issue objects',
                            items=openapi.Schema(
                                type=openapi.TYPE_OBJECT,
                                properties={
                                    'id': openapi.Schema(type=openapi.TYPE_INTEGER, example=1),
                                    'tracking_code': openapi.Schema(type=openapi.TYPE_STRING, example="Tree254"),
                                    'title': openapi.Schema(
                                        type=openapi.TYPE_STRING, example="Network connectivity issue"
                                    ),
                                    'intake_date': openapi.Schema(
                                        type=openapi.TYPE_STRING,
                                        format=openapi.FORMAT_DATETIME,
                                        example="2021-03-23T10:30:45.123Z",
                                    ),
                                    'administrative_region': openapi.Schema(
                                        type=openapi.TYPE_OBJECT,
                                        properties={
                                            'administrative_id': openapi.Schema(
                                                type=openapi.TYPE_STRING,
                                                example="5101",
                                                description="Administrative region ID",
                                            ),
                                            'name': openapi.Schema(
                                                type=openapi.TYPE_STRING,
                                                example="KADJÈRÈ",
                                                description="Administrative region name",
                                            ),
                                        },
                                        description="Administrative region information",
                                    ),
                                    'reporter': openapi.Schema(
                                        type=openapi.TYPE_OBJECT,
                                        properties={
                                            'id': openapi.Schema(
                                                type=openapi.TYPE_INTEGER, example=4556, description="Reporter user ID"
                                            ),
                                            'name': openapi.Schema(
                                                type=openapi.TYPE_STRING,
                                                example="Commité village",
                                                description="Reporter full name",
                                            ),
                                        },
                                        description="User who reported the issue",
                                    ),
                                    'assignee': openapi.Schema(
                                        type=openapi.TYPE_OBJECT,
                                        properties={
                                            'id': openapi.Schema(
                                                type=openapi.TYPE_INTEGER, example=123, description="Assignee user ID"
                                            ),
                                            'name': openapi.Schema(
                                                type=openapi.TYPE_STRING,
                                                example="Comité National",
                                                description="Assignee full name",
                                            ),
                                        },
                                        description="User assigned to handle the issue",
                                    ),
                                    'status': openapi.Schema(
                                        type=openapi.TYPE_OBJECT,
                                        properties={
                                            'id': openapi.Schema(
                                                type=openapi.TYPE_INTEGER, example=1, description="Issue status ID"
                                            ),
                                            'name': openapi.Schema(
                                                type=openapi.TYPE_STRING, example="Open", description="Status name"
                                            ),
                                        },
                                        description="Status information",
                                    ),
                                    'category': openapi.Schema(
                                        type=openapi.TYPE_OBJECT,
                                        properties={
                                            'id': openapi.Schema(
                                                type=openapi.TYPE_INTEGER, example=1, description="Issue category ID"
                                            ),
                                            'name': openapi.Schema(
                                                type=openapi.TYPE_STRING,
                                                example="Environmental",
                                                description="Category name",
                                            ),
                                        },
                                        description="Category information",
                                    ),
                                    'issue_type': openapi.Schema(
                                        type=openapi.TYPE_OBJECT,
                                        properties={
                                            'id': openapi.Schema(
                                                type=openapi.TYPE_INTEGER, example=1, description="Issue type ID"
                                            ),
                                            'name': openapi.Schema(
                                                type=openapi.TYPE_STRING, example="Complaint", description="Type name"
                                            ),
                                        },
                                        description="Issue type information",
                                    ),
                                },
                                description="Issue object with all related information",
                            ),
                        ),
                    },
                ),
            ),
            400: openapi.Response(description="Bad request - Invalid query parameters"),
            401: openapi.Response(
                description="Unauthorized - Invalid or missing token",
                examples={"application/json": {"detail": "Invalid token."}},
            ),
            500: openapi.Response(description="Internal server error"),
        },
        operation_summary="List all issues (paginated)",
        operation_description="Retrieve a paginated list of all issues ordered by intake date.",
        tags=['Issues'],
        security=[{'Token': []}],  # References the Token security definition
    )
    def get(self, request, *args, **kwargs):
        """
        Retrieve paginated list of Issue objects.

        Returns a paginated list of all issues available in the system.
        The list is ordered by intake date.

        Args:
            request: HTTP request object

        Returns:
            Response: JSON response with paginated list of issues
        """
        return super().get(request, *args, **kwargs)


class IssueStatusListAPIView(ListAPIView):
    """
    API View for listing IssueStatus objects with pagination.

    This view provides a paginated read-only list of all available issue statuses.
    It requires Token authentication and returns paginated results.
    """

    queryset = IssueStatus.objects.all()
    serializer_class = IssueStatusSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                'page', openapi.IN_QUERY, description="Page number for pagination", type=openapi.TYPE_INTEGER, default=1
            ),
            openapi.Parameter(
                'page_size',
                openapi.IN_QUERY,
                description="Number of results per page (max: 100)",
                type=openapi.TYPE_INTEGER,
                default=20,
            ),
        ],
        responses={
            200: openapi.Response(
                description="Paginated list of issue statuses",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'count': openapi.Schema(type=openapi.TYPE_INTEGER, description='Total number of items'),
                        'next': openapi.Schema(
                            type=openapi.TYPE_STRING,
                            format=openapi.FORMAT_URI,
                            description='URL to next page (null if no next page)',
                            nullable=True,
                        ),
                        'previous': openapi.Schema(
                            type=openapi.TYPE_STRING,
                            format=openapi.FORMAT_URI,
                            description='URL to previous page (null if no previous page)',
                            nullable=True,
                        ),
                        'results': openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            items=openapi.Schema(
                                type=openapi.TYPE_OBJECT,
                                properties={
                                    'id': openapi.Schema(
                                        type=openapi.TYPE_INTEGER, description='Unique identifier for the issue status'
                                    ),
                                    'name': openapi.Schema(
                                        type=openapi.TYPE_STRING, description='Name of the issue status'
                                    ),
                                    'final_status': openapi.Schema(
                                        type=openapi.TYPE_BOOLEAN, description='Is final status'
                                    ),
                                    'initial_status': openapi.Schema(
                                        type=openapi.TYPE_BOOLEAN, description='Is initial status'
                                    ),
                                    'rejected_status': openapi.Schema(
                                        type=openapi.TYPE_BOOLEAN, description='Is rejected status'
                                    ),
                                    'open_status': openapi.Schema(
                                        type=openapi.TYPE_BOOLEAN, description='Is open status'
                                    ),
                                },
                            ),
                            description="List of issue statuses for current page",
                        ),
                    },
                ),
                examples={
                    "application/json": {
                        "count": 25,
                        "next": "http://localhost:8000/issues/issue-statuses/?page=3",
                        "previous": "http://localhost:8000/issues/issue-statuses/?page=1",
                        "results": [
                            {
                                "id": 1,
                                "name": "Créé",
                                "final_status": False,
                                "initial_status": True,
                                "rejected_status": False,
                                "open_status": False,
                            },
                            {
                                "id": 2,
                                "name": "Ouverte",
                                "final_status": False,
                                "initial_status": False,
                                "rejected_status": False,
                                "open_status": True,
                            },
                        ],
                    }
                },
            ),
            400: openapi.Response(description="Bad request - Invalid query parameters"),
            401: openapi.Response(
                description="Unauthorized - Invalid or missing token",
                examples={"application/json": {"detail": "Invalid token."}},
            ),
            500: openapi.Response(description="Internal server error"),
        },
        operation_summary="List all issue statuses (paginated)",
        operation_description="Retrieve a paginated list of all issue statuses ordered by name.",
        tags=['Issue Statuses'],
        security=[{'Token': []}],
    )
    def get(self, request, *args, **kwargs):
        """
        Retrieve paginated list of IssueStatus objects.

        Returns a paginated list of all issue statuses available in the system.
        The list is ordered alphabetically by status name.

        Args:
            request: HTTP request object

        Returns:
            Response: JSON response with paginated list of issue statuses
        """
        return super().get(request, *args, **kwargs)


class IssueTypeListView(ListAPIView):
    """
    API View for listing IssueType objects with pagination.

    This view provides a paginated read-only list of all available issue types.
    It requires Token authentication and returns paginated results.
    """

    queryset = IssueType.objects.all()
    serializer_class = IssueTypeSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                'page', openapi.IN_QUERY, description="Page number for pagination", type=openapi.TYPE_INTEGER, default=1
            ),
            openapi.Parameter(
                'page_size',
                openapi.IN_QUERY,
                description="Number of items per page (max: 100)",
                type=openapi.TYPE_INTEGER,
                default=20,
            ),
        ],
        responses={
            200: openapi.Response(
                description="Paginated list of issue types",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'count': openapi.Schema(type=openapi.TYPE_INTEGER, description="Total number of items"),
                        'next': openapi.Schema(
                            type=openapi.TYPE_STRING,
                            format=openapi.FORMAT_URI,
                            description="URL to next page (null if no next page)",
                            nullable=True,
                        ),
                        'previous': openapi.Schema(
                            type=openapi.TYPE_STRING,
                            format=openapi.FORMAT_URI,
                            description="URL to previous page (null if no previous page)",
                            nullable=True,
                        ),
                        'results': openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            items=openapi.Schema(
                                type=openapi.TYPE_OBJECT,
                                properties={
                                    'id': openapi.Schema(
                                        type=openapi.TYPE_INTEGER, description="Unique identifier for the issue type"
                                    ),
                                    'name': openapi.Schema(
                                        type=openapi.TYPE_STRING, description="Name of the issue type"
                                    ),
                                },
                            ),
                            description="List of issue types for current page",
                        ),
                    },
                ),
            ),
            400: openapi.Response(description="Bad request - Invalid query parameters"),
            401: openapi.Response(
                description="Unauthorized - Invalid or missing token",
                examples={"application/json": {"detail": "Invalid token."}},
            ),
            500: openapi.Response(description="Internal server error"),
        },
        operation_summary="List Issue Types",
        operation_description="Retrieve a paginated list of all issue types ordered by name.",
        tags=['Issue Types'],
        security=[{'Token': []}],
    )
    def get(self, request, *args, **kwargs):
        """
        Retrieve paginated list of IssueType objects.

        Returns a paginated list of all issue types available in the system.
        The list is ordered alphabetically by type name.

        Args:
            request: HTTP request object

        Returns:
            Response: JSON response with paginated list of issue types
        """
        return super().get(request, *args, **kwargs)


class IssueCategoryListView(ListAPIView):
    """
    API View for listing IssueCategory objects with pagination.

    This view provides a paginated read-only list of all available issue categories.
    It requires Token authentication and returns paginated results.
    """

    queryset = IssueCategory.objects.select_related(
        'assigned_department__department',
        'assigned_department__administrative_level',
        'assigned_appeal_department__department',
        'assigned_appeal_department__administrative_level',
        'assigned_escalation_department__department',
        'assigned_escalation_department__administrative_level',
        'parent',
    ).all()
    serializer_class = IssueCategorySerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                'page', openapi.IN_QUERY, description="Page number for pagination", type=openapi.TYPE_INTEGER, default=1
            ),
            openapi.Parameter(
                'page_size',
                openapi.IN_QUERY,
                description="Number of items per page (max: 100)",
                type=openapi.TYPE_INTEGER,
                default=20,
            ),
        ],
        responses={
            200: openapi.Response(
                description="Paginated list of issue categories",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'count': openapi.Schema(type=openapi.TYPE_INTEGER, description="Total number of items"),
                        'next': openapi.Schema(
                            type=openapi.TYPE_STRING,
                            format=openapi.FORMAT_URI,
                            description="URL to next page (null if no next page)",
                            nullable=True,
                        ),
                        'previous': openapi.Schema(
                            type=openapi.TYPE_STRING,
                            format=openapi.FORMAT_URI,
                            description="URL to previous page (null if no previous page)",
                            nullable=True,
                        ),
                        'results': openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            items=openapi.Schema(
                                type=openapi.TYPE_OBJECT,
                                properties={
                                    'id': openapi.Schema(
                                        type=openapi.TYPE_INTEGER,
                                        description="Unique identifier for the issue category",
                                    ),
                                    'name': openapi.Schema(
                                        type=openapi.TYPE_STRING, description="Name of the issue category"
                                    ),
                                    'abbreviation': openapi.Schema(
                                        type=openapi.TYPE_STRING,
                                        description="Abbreviation for the issue category",
                                        nullable=True,
                                    ),
                                    'assigned_department': openapi.Schema(
                                        type=openapi.TYPE_OBJECT,
                                        properties={
                                            'name': openapi.Schema(
                                                type=openapi.TYPE_STRING, description="Department name"
                                            ),
                                            'id': openapi.Schema(
                                                type=openapi.TYPE_INTEGER, description="Department ID"
                                            ),
                                            'administrative_level': openapi.Schema(
                                                type=openapi.TYPE_STRING, description="Administrative level name"
                                            ),
                                        },
                                        description="Assigned department information",
                                    ),
                                    'assigned_appeal_department': openapi.Schema(
                                        type=openapi.TYPE_OBJECT,
                                        properties={
                                            'name': openapi.Schema(
                                                type=openapi.TYPE_STRING, description="Appeal department name"
                                            ),
                                            'id': openapi.Schema(
                                                type=openapi.TYPE_INTEGER, description="Appeal department ID"
                                            ),
                                            'administrative_level': openapi.Schema(
                                                type=openapi.TYPE_STRING, description="Administrative level name"
                                            ),
                                        },
                                        description="Assigned appeal department information",
                                    ),
                                    'assigned_escalation_department': openapi.Schema(
                                        type=openapi.TYPE_OBJECT,
                                        properties={
                                            'name': openapi.Schema(
                                                type=openapi.TYPE_STRING, description="Escalation department name"
                                            ),
                                            'id': openapi.Schema(
                                                type=openapi.TYPE_INTEGER, description="Escalation department ID"
                                            ),
                                            'administrative_level': openapi.Schema(
                                                type=openapi.TYPE_STRING, description="Administrative level name"
                                            ),
                                        },
                                        description="Assigned escalation department information",
                                    ),
                                    'confidentiality_level': openapi.Schema(
                                        type=openapi.TYPE_STRING, description="Confidentiality level", nullable=True
                                    ),
                                    'redirection_protocol': openapi.Schema(
                                        type=openapi.TYPE_INTEGER, description="Redirection protocol number"
                                    ),
                                    'label': openapi.Schema(
                                        type=openapi.TYPE_STRING,
                                        description="Category label (same as name, convenience field)",
                                    ),
                                    'value': openapi.Schema(
                                        type=openapi.TYPE_INTEGER,
                                        description="Category value (same as id, convenience field)",
                                    ),
                                    'parent_id': openapi.Schema(
                                        type=openapi.TYPE_INTEGER, description="Subtype ID", nullable=True
                                    ),
                                },
                            ),
                            description="List of issue categories for current page",
                        ),
                    },
                ),
            ),
            400: openapi.Response(description="Bad request - Invalid query parameters"),
            401: openapi.Response(
                description="Unauthorized - Invalid or missing token",
                examples={"application/json": {"detail": "Invalid token."}},
            ),
            500: openapi.Response(description="Internal server error"),
        },
        operation_summary="List Issue Categories",
        operation_description="Retrieve a paginated list of all issue categories ordered by name.",
        tags=['Issue Categories'],
        security=[{'Token': []}],
    )
    def get(self, request, *args, **kwargs):
        """
        Retrieve paginated list of IssueCategory objects.

        Returns a paginated list of all issue categories available in the system.
        The list is ordered alphabetically by category name.

        Args:
            request: HTTP request object

        Returns:
            Response: JSON response with paginated issue category data including
                     detailed department information and convenience fields
        """
        return super().get(request, *args, **kwargs)
