from django.http import Http404
from django.utils.translation import gettext_lazy as _
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.generics import (
    CreateAPIView,
    DestroyAPIView,
    ListAPIView,
    RetrieveAPIView,
    UpdateAPIView,
    get_object_or_404,
)
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from dashboard.grm.constants import (
    CONTACT_INFO_EMAIL_ERROR_MESSAGE,
    CONTACT_MEDIUM_ERROR_MESSAGE,
    RATING_ERROR_MESSAGE,
)
from issues.models import (
    CitizenAgeGroup,
    CitizenGroup,
    Comment,
    Issue,
    IssueAttachment,
    IssueCategory,
    IssueStatus,
    IssueType,
    SubProjectGroup,
)
from issues.permissions import IsReporterOrAssigneePermission
from issues.serializers import (
    CitizenAgeGroupSerializer,
    CitizenGroupSerializer,
    CommentCreateSerializer,
    CommentSerializer,
    IssueAttachmentCreateSerializer,
    IssueAttachmentSerializer,
    IssueCategorySerializer,
    IssueCreateSerializer,
    IssueDetailSerializer,
    IssueSerializer,
    IssueStatusSerializer,
    IssueTypeSerializer,
    IssueUpdateSerializer,
    SubProjectGroupSerializer,
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
        operation_summary="Create an issue",
        operation_description="Create an issue",
        tags=['Issues'],
        security=[{'Token': []}],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=[
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
            201: openapi.Response(
                description="Issue created successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING, example='Issue created successfully.'),
                        'data': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'id': openapi.Schema(
                                    type=openapi.TYPE_INTEGER, description='Unique issue identifier', example=42
                                ),
                                'intake_date': openapi.Schema(
                                    type=openapi.TYPE_STRING,
                                    format=openapi.FORMAT_DATETIME,
                                    description='Date and time when the issue was reported',
                                    example='2024-08-28T10:30:00Z',
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
                                        'final_status': openapi.Schema(type=openapi.TYPE_BOOLEAN, example=False),
                                        'initial_status': openapi.Schema(type=openapi.TYPE_BOOLEAN, example=False),
                                        'rejected_status': openapi.Schema(type=openapi.TYPE_BOOLEAN, example=False),
                                        'open_status': openapi.Schema(type=openapi.TYPE_BOOLEAN, example=True),
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
                                        'parent_id': openapi.Schema(
                                            type=openapi.TYPE_INTEGER, description="Subtype ID", nullable=True
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
                            },
                        ),
                    },
                ),
            ),
            400: openapi.Response(
                description="Bad Request - Validation Failed",
                examples={
                    "application/json": {
                        "message": "Validation failed.",
                        "errors": {
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
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'detail': openapi.Schema(
                            type=openapi.TYPE_STRING, example='An error occurred while creating the issue.'
                        )
                    },
                ),
            ),
        },
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
        except Exception as e:
            return Response(
                {'message': _('An error occurred while creating the issue.'), 'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class AssigneeIssueListAPIView(ListAPIView):
    """
    API View for listing Issue objects assigned to the authenticated user with pagination.

    This view provides a paginated read-only list of issues assigned to the authenticated user.
    It requires Token authentication and returns paginated results.
    """

    serializer_class = IssueSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="List issues (paginated) assigned to the authenticated user",
        operation_description="Retrieve a paginated list of issues where the authenticated user is the assignee.",
        tags=['Issues'],
        security=[{'Token': []}],
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
                                                example="2",
                                                description="Administrative region ID",
                                            ),
                                            'name': openapi.Schema(
                                                type=openapi.TYPE_STRING,
                                                example="ALIBORI",
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
                                            'final_status': openapi.Schema(type=openapi.TYPE_BOOLEAN, example=False),
                                            'initial_status': openapi.Schema(type=openapi.TYPE_BOOLEAN, example=False),
                                            'rejected_status': openapi.Schema(type=openapi.TYPE_BOOLEAN, example=False),
                                            'open_status': openapi.Schema(type=openapi.TYPE_BOOLEAN, example=True),
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
    )
    def get(self, request, *args, **kwargs):
        """
        Retrieve paginated list of Issue objects.

        Returns a paginated list of issues assigned to the authenticated user.
        The list is ordered by intake date in descending order (most recent first).

        Args:
            request: HTTP request object

        Returns:
            Response: JSON response with paginated list of issues
        """
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        return (
            Issue.objects.select_related(
                'status', 'category', 'issue_type', 'administrative_region', 'reporter', 'assignee'
            )
            .filter(assignee=self.request.user)
            .order_by("-intake_date")
        )


class ReporterIssueListAPIView(ListAPIView):
    """
    API View for listing Issue objects reported by the authenticated user with pagination.

    This view provides a paginated read-only list of issues reported by the authenticated user.
    It requires Token authentication and returns paginated results.
    """

    serializer_class = IssueSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="List issues (paginated) reported by the authenticated user",
        operation_description="Retrieve a paginated list of issues where the authenticated user is the reporter.",
        tags=['Issues'],
        security=[{'Token': []}],
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
                                                example="2",
                                                description="Administrative region ID",
                                            ),
                                            'name': openapi.Schema(
                                                type=openapi.TYPE_STRING,
                                                example="ALIBORI",
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
                                            'final_status': openapi.Schema(type=openapi.TYPE_BOOLEAN, example=False),
                                            'initial_status': openapi.Schema(type=openapi.TYPE_BOOLEAN, example=False),
                                            'rejected_status': openapi.Schema(type=openapi.TYPE_BOOLEAN, example=False),
                                            'open_status': openapi.Schema(type=openapi.TYPE_BOOLEAN, example=True),
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
    )
    def get(self, request, *args, **kwargs):
        """
        Retrieve paginated list of Issue objects.

        Returns a paginated list of issues reported by the authenticated user.
        The list is ordered by intake date in descending order (most recent first).

        Args:
            request: HTTP request object

        Returns:
            Response: JSON response with paginated list of issues
        """
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        return (
            Issue.objects.select_related(
                'status', 'category', 'issue_type', 'administrative_region', 'reporter', 'assignee'
            )
            .filter(reporter=self.request.user)
            .order_by("-intake_date")
        )


class IssueRetrieveAPIView(RetrieveAPIView):
    """
    API View for retrieving a single Issue object.

    This view allows authenticated users to retrieve detailed information about
    a specific issue, but only if they are either the reporter or the assignee
    of that issue. This ensures privacy and access control.

    Permissions:
        - Must be authenticated (TokenAuthentication)
        - Must be either the reporter or assignee of the issue
    """

    queryset = Issue.objects.select_related(
        'status',
        'category',
        'issue_type',
        'administrative_region',
        'reporter',
        'assignee',
        'category__assigned_department__department',
        'category__assigned_department__administrative_level',
        'category__assigned_appeal_department__department',
        'category__assigned_appeal_department__administrative_level',
        'category__assigned_escalation_department__department',
        'category__assigned_escalation_department__administrative_level',
    ).prefetch_related('category__parent')
    serializer_class = IssueSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsReporterOrAssigneePermission]
    lookup_field = 'id'

    @swagger_auto_schema(
        operation_summary="Retrieve a specific issue",
        operation_description="""
        Retrieve detailed information about a specific issue.

        **Access Control:**
        Only users who are either the reporter or assignee of the issue can access this endpoint.
        This ensures that sensitive issue information is only visible to authorized personnel.

        **Response Data:**
        Returns comprehensive issue details including:
        - Basic issue information (title, description, dates)
        - Status and category information
        - Administrative region details
        - Reporter and assignee information
        - Related metadata

        **Business Rules:**
        - User must be authenticated with a valid token
        - User must be either the issue reporter or assignee
        - Issue must exist in the system
        """,
        tags=['Issues'],
        security=[{'Token': []}],
        manual_parameters=[
            openapi.Parameter(
                'id',
                openapi.IN_PATH,
                description="Unique identifier of the issue to retrieve",
                type=openapi.TYPE_INTEGER,
                required=True,
                example=123,
            )
        ],
        responses={
            200: openapi.Response(
                description="Issue details retrieved successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'id': openapi.Schema(type=openapi.TYPE_INTEGER, example=1),
                        'tracking_code': openapi.Schema(type=openapi.TYPE_STRING, example="Tree254"),
                        'title': openapi.Schema(type=openapi.TYPE_STRING, example="Network connectivity issue"),
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
                                    example="2",
                                    description="Administrative region ID",
                                ),
                                'name': openapi.Schema(
                                    type=openapi.TYPE_STRING,
                                    example="ALIBORI",
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
                                'final_status': openapi.Schema(type=openapi.TYPE_BOOLEAN, example=False),
                                'initial_status': openapi.Schema(type=openapi.TYPE_BOOLEAN, example=False),
                                'rejected_status': openapi.Schema(type=openapi.TYPE_BOOLEAN, example=False),
                                'open_status': openapi.Schema(type=openapi.TYPE_BOOLEAN, example=True),
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
                                'id': openapi.Schema(type=openapi.TYPE_INTEGER, example=1, description="Issue type ID"),
                                'name': openapi.Schema(
                                    type=openapi.TYPE_STRING, example="Complaint", description="Type name"
                                ),
                            },
                            description="Issue type information",
                        ),
                    },
                ),
            ),
            401: openapi.Response(
                description="Unauthorized - Invalid or missing token",
                examples={"application/json": {"detail": "Invalid token."}},
            ),
            403: openapi.Response(description="Forbidden - User is not the reporter or assignee of this issue"),
            404: openapi.Response(description="Not Found - Issue with the specified ID does not exist"),
            500: openapi.Response(
                description="Internal Server Error - Unexpected server error",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'detail': openapi.Schema(
                            type=openapi.TYPE_STRING, example='An error occurred while retrieving the issue.'
                        )
                    },
                ),
            ),
        },
    )
    def get(self, request, *args, **kwargs):
        """
        Retrieve a specific Issue instance.

        This method handles the retrieval of a single issue with proper
        permission checking. Only reporters and assignees can access the issue.

        Args:
            request: HTTP request object

        Returns:
            Response: JSON response with issue details or error message
        """

        try:
            return super().get(request, *args, **kwargs)
        except (Http404, APIException):
            raise
        except Exception:
            return Response(
                {'detail': _('An error occurred while retrieving the issue.')},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


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
        operation_summary="List all issue statuses (paginated)",
        operation_description="Retrieve a paginated list of all issue statuses ordered by name.",
        tags=['Issue Statuses'],
        security=[{'Token': []}],
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


class IssueTypeListAPIView(ListAPIView):
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
        operation_summary="List Issue Types",
        operation_description="Retrieve a paginated list of all issue types ordered by name.",
        tags=['Issue Types'],
        security=[{'Token': []}],
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


class IssueCategoryListAPIView(ListAPIView):
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
        operation_summary="List Issue Categories",
        operation_description="Retrieve a paginated list of all issue categories ordered by name.",
        tags=['Issue Categories'],
        security=[{'Token': []}],
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


class IssueCommentCreateAPIView(CreateAPIView):
    """
    API View for creating new Comment objects related to a specific Issue.

    This view allows authenticated users to add comments to issues,
    but only if they are either the reporter or assignee of that issue.
    The comment is automatically associated with the specified issue and
    the authenticated user.

    Permissions:
        - Must be authenticated (TokenAuthentication)
        - Must be either the reporter or assignee of the issue
    """

    serializer_class = CommentCreateSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsReporterOrAssigneePermission]

    def get_issue(self):
        """
        Retrieve the Issue object based on the URL parameter.

        Returns:
            Issue: The issue object to which the comment will be added
        """
        issue_id = self.kwargs.get("id")
        return Issue.objects.select_related('reporter', 'assignee').get(id=issue_id)

    def get_object(self):
        """
        Get the Issue object for permission checking.

        This method is called by DRF's permission system to check
        object-level permissions.

        Returns:
            Issue: The issue object for permission validation
        """
        return self.get_issue()

    def perform_create(self, serializer):
        """
        Save the comment with the associated issue and user.

        Args:
            serializer: The validated comment serializer
        """
        issue = self.get_issue()
        instance = serializer.save(issue=issue, user=self.request.user)
        return instance

    def create(self, request, *args, **kwargs):
        """
        Override to return full CommentSerializer in the response.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = self.perform_create(serializer)
        data = CommentSerializer(instance).data
        headers = self.get_success_headers(data)
        return Response(
            {'message': _('Comment added successfully.'), 'data': data}, status=status.HTTP_201_CREATED, headers=headers
        )

    @swagger_auto_schema(
        operation_summary="Add a comment to a specific issue",
        operation_description="""
        Create a new comment associated with a specific issue.

        **Access Control:**
        Only users who are either the reporter or assignee of the issue can add comments.
        This ensures that only authorized personnel can participate in issue discussions.

        **Automatic Associations:**
        - The comment is automatically linked to the specified issue
        - The authenticated user is set as the comment author
        - The due_date is automatically set to the current timestamp

        **Business Rules:**
        - Issue must exist in the system
        - User must be authenticated with a valid token
        - User must be either the issue reporter or assignee
        - Comment text is required and cannot be empty
        """,
        tags=['Issues', 'Comments'],
        security=[{'Token': []}],
        manual_parameters=[
            openapi.Parameter(
                'id',
                openapi.IN_PATH,
                description="Unique identifier of the issue to add a comment to",
                type=openapi.TYPE_INTEGER,
                required=True,
                example=123,
            )
        ],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['comment'],
            properties={
                'comment': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='The comment text content',
                    example='This issue has been reviewed and requires additional information from the reporter.',
                    minLength=1,
                    maxLength=1000,
                ),
            },
        ),
        responses={
            201: openapi.Response(
                description="Comment created successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING, example='Comment added successfully.'),
                        'data': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'id': openapi.Schema(
                                    type=openapi.TYPE_INTEGER, description='Unique comment identifier', example=42
                                ),
                                'comment': openapi.Schema(
                                    type=openapi.TYPE_STRING,
                                    description='The comment text',
                                    example='This issue has been reviewed and requires additional information.',
                                ),
                                'user': openapi.Schema(
                                    type=openapi.TYPE_OBJECT,
                                    description='User who created the comment',
                                    properties={
                                        'id': openapi.Schema(type=openapi.TYPE_INTEGER, example=5),
                                        'name': openapi.Schema(type=openapi.TYPE_STRING, example='John Doe'),
                                    },
                                ),
                                'due_date': openapi.Schema(
                                    type=openapi.TYPE_STRING,
                                    format=openapi.FORMAT_DATETIME,
                                    description='When the comment was created',
                                    example='2024-08-28T10:30:45.123456Z',
                                ),
                            },
                        ),
                    },
                ),
            ),
            400: openapi.Response(
                description="Bad Request - Validation failed",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING, example='Validation failed.'),
                        'errors': openapi.Schema(
                            type=openapi.TYPE_OBJECT, description='Field-specific validation errors'
                        ),
                    },
                ),
            ),
            401: openapi.Response(
                description="Unauthorized - Invalid or missing token",
                examples={"application/json": {"detail": "Invalid token."}},
            ),
            403: openapi.Response(description="Forbidden - User is not the reporter or assignee of this issue"),
            404: openapi.Response(description="Not Found - Issue with the specified ID does not exist"),
            500: openapi.Response(
                description="Internal Server Error - Unexpected server error",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'detail': openapi.Schema(
                            type=openapi.TYPE_STRING, example='An error occurred while creating the comment.'
                        )
                    },
                ),
            ),
        },
    )
    def post(self, request, *args, **kwargs):
        """
        Create a new Comment for the specified Issue.

        This method handles the creation of a new comment with proper validation,
        permission checking, and error handling. The comment is automatically
        associated with the issue and the authenticated user.

        Args:
            request: HTTP request object containing comment data

        Returns:
            Response: JSON response with created comment data or error details
        """
        try:

            return super().post(request, *args, **kwargs)

        except Http404:
            return Response(
                {'detail': _('Not found.')},
                status=status.HTTP_404_NOT_FOUND,
            )
        except ValidationError as e:
            return Response(
                {
                    'message': _('Validation failed.'),
                    'errors': e.message_dict if hasattr(e, 'message_dict') else str(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            return Response(
                {'detail': _('An error occurred while creating the comment.')},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class IssueCommentDeleteAPIView(DestroyAPIView):
    """
    API View for deleting a specific Comment object related to an Issue.

    Only the reporter or assignee of the related issue can delete the comment.
    """

    queryset = Comment.objects.select_related("issue", "user")
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsReporterOrAssigneePermission]

    def get_issue(self):
        """
        Retrieve the Issue object based on the URL parameter.

        Returns:
            Issue: The issue object to which the comment will be deleted
        """
        comment_id = self.kwargs.get("id")
        comment = get_object_or_404(Comment.objects.select_related("issue"), id=comment_id)
        self.comment_instance = comment
        return comment.issue

    def get_object(self):
        """
        Override to return the Issue object for permission checks,
        while keeping a reference to the Comment for deletion.
        """
        issue = self.get_issue()
        return issue

    def perform_destroy(self, instance):
        """
        Actually delete the comment after permission check.
        """
        self.comment_instance.delete()

    @swagger_auto_schema(
        operation_summary="Delete a comment from a specific issue",
        operation_description="""
        Delete an existing comment from an issue.

        **Access Control:**
        - Only users who are either the reporter or assignee of the issue can delete comments.
        - Ensures that unauthorized users cannot remove comments from issues.

        **Business Rules:**
        - Comment must exist
        - User must be authenticated with a valid token
        - User must be either the issue reporter or assignee
        """,
        tags=["Issues", "Comments"],
        manual_parameters=[
            openapi.Parameter(
                "id",
                openapi.IN_PATH,
                description="Unique identifier of the comment to delete",
                type=openapi.TYPE_INTEGER,
                required=True,
                example=42,
            )
        ],
        responses={
            204: openapi.Response(description="Comment deleted successfully"),
            401: openapi.Response(
                description="Unauthorized - Invalid or missing token",
                examples={"application/json": {"detail": "Invalid token."}},
            ),
            403: openapi.Response(description="Forbidden - User is not the reporter or assignee of this issue"),
            404: openapi.Response(description="Not Found - Comment with the specified ID does not exist"),
            500: openapi.Response(
                description="Internal Server Error - Unexpected server error",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "detail": openapi.Schema(
                            type=openapi.TYPE_STRING, example="An error occurred while deleting the comment."
                        )
                    },
                ),
            ),
        },
    )
    def delete(self, request, *args, **kwargs):
        """
        Delete the specified Comment.

        Handles permission checks and returns appropriate status codes.
        """
        try:
            return super().delete(request, *args, **kwargs)
        except Http404:
            return Response({"detail": _("Not found.")}, status=status.HTTP_404_NOT_FOUND)
        except Exception:
            return Response(
                {"detail": _("An error occurred while deleting the comment.")},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class IssueCommentsListAPIView(ListAPIView):
    """
    API View for retrieving paginated comments related to a specific Issue.

    Permissions:
        - Must be authenticated
        - Must be the reporter or assignee of the issue
    """

    serializer_class = CommentSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsReporterOrAssigneePermission]

    def get_queryset(self):
        """
        Retrieve the queryset of comments for the specified Issue.

        Returns:
            QuerySet: All comments associated with the given Issue,
            ordered by due_date descending (as defined in Comment.Meta).
        """
        issue_id = self.kwargs.get("id")
        return Comment.objects.filter(issue_id=issue_id).select_related("user", "issue")

    @swagger_auto_schema(
        operation_summary="List comments of a specific issue",
        operation_description="""
        Retrieve a paginated list of comments associated with a specific issue.

        **Access Control:**
        Only users who are either the reporter or assignee of the issue can access this endpoint.
        """,
        tags=['Issues', 'Comments'],
        security=[{'Token': []}],
        manual_parameters=[
            openapi.Parameter(
                'id',
                openapi.IN_PATH,
                description="Unique identifier of the issue whose comments you want to retrieve",
                type=openapi.TYPE_INTEGER,
                required=True,
                example=123,
            )
        ],
        responses={
            200: openapi.Response(
                description="List of comments",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'count': openapi.Schema(type=openapi.TYPE_INTEGER, example=25),
                        'next': openapi.Schema(type=openapi.TYPE_STRING, example=None),
                        'previous': openapi.Schema(type=openapi.TYPE_STRING, example=None),
                        'results': openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            items=openapi.Schema(
                                type=openapi.TYPE_OBJECT,
                                properties={
                                    "id": openapi.Schema(type=openapi.TYPE_INTEGER, example=1),
                                    "comment": openapi.Schema(type=openapi.TYPE_STRING, example="This is a comment"),
                                    "user": openapi.Schema(
                                        type=openapi.TYPE_OBJECT,
                                        properties={
                                            "id": openapi.Schema(type=openapi.TYPE_INTEGER, example=42),
                                            "name": openapi.Schema(type=openapi.TYPE_STRING, example="John Doe"),
                                        },
                                    ),
                                    "due_date": openapi.Schema(
                                        type=openapi.TYPE_STRING,
                                        format=openapi.FORMAT_DATETIME,
                                        example="2025-09-01T10:30:45.123Z",
                                    ),
                                },
                            ),
                            description="List of comment objects",
                        ),
                    },
                ),
            ),
            403: openapi.Response(description="Forbidden - User is not the reporter or assignee of this issue"),
            404: openapi.Response(description="Not Found - Issue with the specified ID does not exist"),
        },
    )
    def get(self, request, *args, **kwargs):
        """
        Retrieve paginated list of Comment objects for a specific Issue.

        Returns a paginated list of comments associated with the given Issue.
        The list is ordered by due date in descending order (most recent first).

        Args:
            request: HTTP request object

        Returns:
            Response: JSON response with a paginated list of comments
                      related to the specified issue.
        """
        try:
            return super().get(request, *args, **kwargs)
        except (Http404, APIException):
            raise
        except Exception:
            return Response(
                {'detail': _('An error occurred while retrieving issue comments.')},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class IssueAttachmentCreateAPIView(CreateAPIView):
    """
    API View for creating new IssueAttachment objects related to a specific Issue.

    This view handles file uploads for a given issue and automatically
    sets the uploader.
    """

    serializer_class = IssueAttachmentCreateSerializer
    parser_classes = [MultiPartParser, FormParser]
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsReporterOrAssigneePermission]

    def get_issue(self):
        issue_id = self.kwargs.get("id")
        return get_object_or_404(Issue, id=issue_id)

    def perform_create(self, serializer):
        issue = self.get_issue()
        instance = serializer.save(issue=issue, uploaded_by=self.request.user)
        return instance

    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            instance = self.perform_create(serializer)

            data = IssueAttachmentSerializer(instance).data

            headers = self.get_success_headers(data)
            return Response(
                {'message': _('Attachment uploaded successfully.'), 'data': data},
                status=status.HTTP_201_CREATED,
                headers=headers,
            )
        except Http404:
            return Response(
                {'detail': _('Not found.')},
                status=status.HTTP_404_NOT_FOUND,
            )
        except ValidationError as e:
            return Response(
                {'message': _('Validation failed.'), 'errors': e.detail},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            return Response(
                {'detail': _('An error occurred during file upload.')},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @swagger_auto_schema(
        operation_summary="Add an attachment to a specific issue",
        operation_description="""
            Create a new attachment associated with a specific issue.

            **Access Control:**
            Only users who are either the reporter or assignee of the issue can add attachment.
            This ensures that only authorized personnel can participate in issue discussions.

            **Automatic Associations:**
            - The attachment is automatically linked to the specified issue
            - The authenticated user is set as the author
            - The created_date is automatically set to the current timestamp

            **Business Rules:**
            - Issue must exist in the system
            - User must be authenticated with a valid token
            - User must be either the issue reporter or assignee
            - Attachment URL is required and cannot be empty
            """,
        tags=['Issues', 'Attachments'],
        security=[{'Token': []}],
        responses={
            201: openapi.Response(
                description="Attachment created successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING, example='Attachment added successfully.'),
                        'data': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'id': openapi.Schema(
                                    type=openapi.TYPE_INTEGER, description='Unique attachment identifier', example=42
                                ),
                                'file': openapi.Schema(
                                    type=openapi.TYPE_FILE,
                                    description='The file',
                                ),
                                'uploaded_by': openapi.Schema(
                                    type=openapi.TYPE_OBJECT,
                                    description='User who created the comment',
                                    properties={
                                        'id': openapi.Schema(type=openapi.TYPE_INTEGER, example=5),
                                        'name': openapi.Schema(type=openapi.TYPE_STRING, example='John Doe'),
                                    },
                                ),
                                'created_date': openapi.Schema(
                                    type=openapi.TYPE_STRING,
                                    format=openapi.FORMAT_DATETIME,
                                    description='When the comment was created',
                                    example='2024-08-28T10:30:45.123456Z',
                                ),
                            },
                        ),
                    },
                ),
            ),
            400: openapi.Response(
                description="Bad Request - Validation failed",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING, example='Validation failed.'),
                        'errors': openapi.Schema(
                            type=openapi.TYPE_OBJECT, description='Field-specific validation errors'
                        ),
                    },
                ),
            ),
            401: openapi.Response(
                description="Unauthorized - Invalid or missing token",
                examples={"application/json": {"detail": "Invalid token."}},
            ),
            403: openapi.Response(description="Forbidden - User is not the reporter or assignee of this issue"),
            404: openapi.Response(description="Not Found - Issue with the specified ID does not exist"),
            500: openapi.Response(
                description="Internal Server Error - Unexpected server error",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'detail': openapi.Schema(
                            type=openapi.TYPE_STRING, example='An error occurred while creating the comment.'
                        )
                    },
                ),
            ),
        },
    )
    def post(self, request, *args, **kwargs):
        """
        Create a new Attachment for the specified Issue.

        This method handles the creation of a new attachment with proper validation,
        permission checking, and error handling. The comment is automatically
        associated with the issue and the authenticated user.

        Args:
            request: HTTP request object containing comment data

        Returns:
            Response: JSON response with created comment data or error details
        """
        try:

            return super().post(request, *args, **kwargs)

        except Http404:
            return Response(
                {'detail': _('Not found.')},
                status=status.HTTP_404_NOT_FOUND,
            )
        except ValidationError as e:
            return Response(
                {
                    'message': _('Validation failed.'),
                    'errors': e.message_dict if hasattr(e, 'message_dict') else str(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            return Response(
                {'detail': _('An error occurred while creating the comment.')},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class IssueAttachmentsListAPIView(ListAPIView):
    """
    API View for retrieving paginated attachments related to a specific Issue.

    Permissions:
        - Must be authenticated
        - Must be the reporter or assignee of the issue
    """

    serializer_class = IssueAttachmentSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsReporterOrAssigneePermission]

    def get_queryset(self):
        """
        Retrieve the queryset of attachments for the specified Issue.

        Returns:
            QuerySet: All attachments associated with the given Issue,
            ordered by created_date descending (as defined in Comment.Meta).
        """
        issue_id = self.kwargs.get("id")
        return IssueAttachment.objects.filter(issue_id=issue_id).select_related("uploaded_by", "issue")

    @swagger_auto_schema(
        operation_summary="List attachments of a specific issue",
        operation_description="""
        Retrieve a paginated list of attachments associated with a specific issue.

        **Access Control:**
        Only users who are either the reporter or assignee of the issue can access this endpoint.
        """,
        tags=['Issues', 'Attachments'],
        security=[{'Token': []}],
        manual_parameters=[
            openapi.Parameter(
                'id',
                openapi.IN_PATH,
                description="Unique identifier of the issue whose attachments you want to retrieve",
                type=openapi.TYPE_INTEGER,
                required=True,
                example=123,
            )
        ],
        responses={
            200: openapi.Response(
                description="List of comments",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'count': openapi.Schema(type=openapi.TYPE_INTEGER, example=25),
                        'next': openapi.Schema(type=openapi.TYPE_STRING, example=None),
                        'previous': openapi.Schema(type=openapi.TYPE_STRING, example=None),
                        'results': openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            items=openapi.Schema(
                                type=openapi.TYPE_OBJECT,
                                properties={
                                    'id': openapi.Schema(
                                        type=openapi.TYPE_INTEGER,
                                        description='Unique attachment identifier',
                                        example=42,
                                    ),
                                    'file': openapi.Schema(
                                        type=openapi.TYPE_FILE,
                                        description='The file',
                                    ),
                                    'uploaded_by': openapi.Schema(
                                        type=openapi.TYPE_OBJECT,
                                        description='User who created the comment',
                                        properties={
                                            'id': openapi.Schema(type=openapi.TYPE_INTEGER, example=5),
                                            'name': openapi.Schema(type=openapi.TYPE_STRING, example='John Doe'),
                                        },
                                    ),
                                    'created_date': openapi.Schema(
                                        type=openapi.TYPE_STRING,
                                        format=openapi.FORMAT_DATETIME,
                                        description='When the comment was created',
                                        example='2024-08-28T10:30:45.123456Z',
                                    ),
                                },
                            ),
                            description="List of comment objects",
                        ),
                    },
                ),
            ),
            403: openapi.Response(description="Forbidden - User is not the reporter or assignee of this issue"),
            404: openapi.Response(description="Not Found - Issue with the specified ID does not exist"),
        },
    )
    def get(self, request, *args, **kwargs):
        """
        Retrieve paginated list of Attachment objects for a specific Issue.

        Returns a paginated list of attachments associated with the given Issue.
        The list is ordered by due date in descending order (most recent first).

        Args:
            request: HTTP request object

        Returns:
            Response: JSON response with a paginated list of attachments
                      related to the specified issue.
        """
        try:
            return super().get(request, *args, **kwargs)
        except (Http404, APIException):
            raise
        except Exception:
            return Response(
                {'detail': _('An error occurred while retrieving issue attachments.')},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class IssueUpdateAPIView(UpdateAPIView):
    """
    API View for updating specific fields of Issue objects.

    This view handles partial updates (PATCH) of Issue instances allowing only
    specific fields to be modified: escalate_flag, reject_flag, rating,
    escalation_reason, status, and research_result.

    Requires Token authentication and validates that the user is either
    the reporter or assignee of the issue.
    """

    queryset = Issue.objects.all()
    serializer_class = IssueUpdateSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsReporterOrAssigneePermission]
    http_method_names = ['patch']
    lookup_field = 'id'

    @swagger_auto_schema(
        operation_summary="Update an issue",
        operation_description="""
        Partially update an issue. Only specific fields can be modified.

        **Access Control:**
        Only users who are either the reporter or assignee of the issue can access this endpoint.
        """,
        tags=['Issues'],
        security=[{'Token': []}],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'escalate_flag': openapi.Schema(
                    type=openapi.TYPE_BOOLEAN,
                    description='Flag indicating if the issue should be escalated',
                    example=True,
                ),
                'reject_flag': openapi.Schema(
                    type=openapi.TYPE_BOOLEAN,
                    description='Flag indicating if the issue is rejected',
                    example=False,
                ),
                'rating': openapi.Schema(
                    type=openapi.TYPE_INTEGER,
                    description='Rating for the issue resolution (1-5)',
                    minimum=1,
                    maximum=5,
                    example=4,
                ),
                'escalation_reason': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Reason for escalating the issue',
                    example='Issue requires higher level approval',
                ),
                'status': openapi.Schema(
                    type=openapi.TYPE_INTEGER,
                    description='ID of the new issue status',
                    example=2,
                ),
                'research_result': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Results of research conducted on the issue',
                    example='Investigation completed. Root cause identified.',
                ),
            },
        ),
        responses={
            200: openapi.Response(
                description="Issue updated successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING, example='Issue updated successfully.'),
                        'data': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'id': openapi.Schema(
                                    type=openapi.TYPE_INTEGER, description='Unique issue identifier', example=42
                                ),
                                'intake_date': openapi.Schema(
                                    type=openapi.TYPE_STRING,
                                    format=openapi.FORMAT_DATETIME,
                                    description='Date and time when the issue was reported',
                                    example='2024-08-28T10:30:00Z',
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
                                        'final_status': openapi.Schema(type=openapi.TYPE_BOOLEAN, example=False),
                                        'initial_status': openapi.Schema(type=openapi.TYPE_BOOLEAN, example=False),
                                        'rejected_status': openapi.Schema(type=openapi.TYPE_BOOLEAN, example=False),
                                        'open_status': openapi.Schema(type=openapi.TYPE_BOOLEAN, example=True),
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
                                        'parent_id': openapi.Schema(
                                            type=openapi.TYPE_INTEGER, description="Subtype ID", nullable=True
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
                            },
                        ),
                    },
                ),
            ),
            400: openapi.Response(
                description="Bad Request - Validation Failed",
                examples={
                    "application/json": {
                        "message": "Validation failed.",
                        "errors": {
                            "rating": [RATING_ERROR_MESSAGE],
                            "status": ["Invalid pk \"999\" - object does not exist."],
                        },
                    }
                },
            ),
            401: openapi.Response(
                description="Unauthorized - Invalid or missing token",
                examples={"application/json": {"detail": "Invalid token."}},
            ),
            403: openapi.Response(
                description="Forbidden - User is not reporter or assignee",
                examples={"application/json": {"detail": "You do not have permission to perform this action."}},
            ),
            404: openapi.Response(
                description="Not Found - Issue does not exist",
                examples={"application/json": {"detail": "Not found."}},
            ),
            500: openapi.Response(
                description="Internal Server Error",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'detail': openapi.Schema(
                            type=openapi.TYPE_STRING, example='An error occurred while updating the issue.'
                        )
                    },
                ),
            ),
        },
    )
    def patch(self, request, *args, **kwargs):
        """
        Partially update an Issue instance.

        Overrides the default update method to provide custom response format
        and error handling. Only allows updating specific permitted fields.

        Args:
            request: HTTP request object containing updated issue data
            *args: Variable length argument list
            **kwargs: Arbitrary keyword arguments (includes 'id' from URL)

        Returns:
            Response: JSON response with updated issue data or error details
        """
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data, partial=True)
            if serializer.is_valid():
                updated_issue = serializer.save()
                detail_serializer = IssueDetailSerializer(updated_issue)
                return Response(
                    {'message': _('Issue updated successfully.'), 'data': detail_serializer.data},
                    status=status.HTTP_200_OK,
                )
            else:
                return Response(
                    {'message': _('Validation failed.'), 'errors': serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except Issue.DoesNotExist:
            return Response(
                {'message': _('Not found.')},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {'message': _('An error occurred while updating the issue.'), 'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class CitizenGroupListAPIView(ListAPIView):
    """
    API View for listing CitizenGroup objects with pagination.

    This view provides a paginated read-only list of all available citizen groups.
    It requires Token authentication and returns paginated results.
    """

    queryset = CitizenGroup.objects.all()
    serializer_class = CitizenGroupSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="List Citizen Groups",
        operation_description="Retrieve a paginated list of all citizen groups.",
        tags=['Citizen Groups'],
        security=[{'Token': []}],
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
                description="Paginated list of citizen groups",
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
                                        type=openapi.TYPE_INTEGER, description="Unique identifier for the citizen group"
                                    ),
                                    'name': openapi.Schema(
                                        type=openapi.TYPE_STRING, description="Name of the citizen group"
                                    ),
                                    'type': openapi.Schema(
                                        type=openapi.TYPE_STRING, description="Type of the citizen group"
                                    ),
                                },
                            ),
                            description="List of citizen groups for current page",
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
    )
    def get(self, request, *args, **kwargs):
        """
        Retrieve paginated list of CitizenGroup objects.

        Returns a paginated list of all citizen groups available in the system.

        Args:
            request: HTTP request object

        Returns:
            Response: JSON response with paginated list of citizen groups
        """
        return super().get(request, *args, **kwargs)


class CitizenAgeGroupListAPIView(ListAPIView):
    """
    API View for listing CitizenAgeGroup objects with pagination.

    This view provides a paginated read-only list of all available citizen age groups.
    It requires Token authentication and returns paginated results.
    """

    queryset = CitizenAgeGroup.objects.all()
    serializer_class = CitizenAgeGroupSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="List Citizen Groups",
        operation_description="Retrieve a paginated list of all citizen age groups.",
        tags=['Citizen Age Groups'],
        security=[{'Token': []}],
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
                description="Paginated list of citizen age groups",
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
                                        type=openapi.TYPE_INTEGER, description="Unique identifier for the citizen group"
                                    ),
                                    'name': openapi.Schema(
                                        type=openapi.TYPE_STRING, description="Name of the citizen group"
                                    ),
                                },
                            ),
                            description="List of citizen age groups for current page",
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
    )
    def get(self, request, *args, **kwargs):
        """
        Retrieve paginated list of CitizenAgeGroup objects.

        Returns a paginated list of all citizen age groups available in the system.

        Args:
            request: HTTP request object

        Returns:
            Response: JSON response with paginated list of citizen age groups
        """
        return super().get(request, *args, **kwargs)


class SubProjectGroupListAPIView(ListAPIView):
    """
    API View for listing SubProjectGroup objects with pagination.

    This view provides a paginated read-only list of all available subproject groups.
    It requires Token authentication and returns paginated results.
    """

    queryset = SubProjectGroup.objects.all()
    serializer_class = SubProjectGroupSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="List Subproject Groups",
        operation_description="Retrieve a paginated list of all subproject groups.",
        tags=['Subproject Groups'],
        security=[{'Token': []}],
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
                description="Paginated list of subproject groups",
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
                                        description="Unique identifier for the subproject group",
                                    ),
                                    'name': openapi.Schema(
                                        type=openapi.TYPE_STRING, description="Name of the subproject group"
                                    ),
                                },
                            ),
                            description="List of subproject groups for current page",
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
    )
    def get(self, request, *args, **kwargs):
        """
        Retrieve paginated list of SubProjectGroup objects.

        Returns a paginated list of all subproject groups available in the system.

        Args:
            request: HTTP request object

        Returns:
            Response: JSON response with paginated list of subproject groups
        """
        return super().get(request, *args, **kwargs)
