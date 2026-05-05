import logging

from django.http import Http404
from django.utils.dateparse import parse_datetime
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import APIException, MethodNotAllowed, ValidationError
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
from rest_framework.views import APIView

from grm.constants import (
    ATTACHMENT_CREATE_ERROR_MESSAGE,
    ATTACHMENT_CREATE_SUCCESS_MESSAGE,
    ATTACHMENT_RETRIEVE_ERROR_MESSAGE,
    COMMENT_CREATE_ERROR_MESSAGE,
    COMMENT_CREATE_SUCCESS_MESSAGE,
    COMMENT_DELETE_ERROR_MESSAGE,
    COMMENT_RETRIEVE_ERROR_MESSAGE,
    CONTACT_INFO_EMAIL_ERROR_MESSAGE,
    CONTACT_MEDIUM_ERROR_MESSAGE,
    ISSUE_CREATE_ERROR_MESSAGE,
    ISSUE_CREATE_SUCCESS_MESSAGE,
    ISSUE_LIST_ERROR_MESSAGE,
    ISSUE_RETRIEVE_ERROR_MESSAGE,
    ISSUE_UPDATE_ERROR_MESSAGE,
    ISSUE_UPDATE_SUCCESS_MESSAGE,
    NOT_FOUND_MESSAGE,
    VALIDATION_FAILED_MESSAGE,
)
from grm.notifications import send_issue_notification
from issues.models import (
    AdministrativeRegion,
    CitizenAgeGroup,
    CitizenGroup,
    Comment,
    Component,
    Issue,
    IssueAttachment,
    IssueCategory,
    IssueStatus,
    IssueSubType,
    IssueType,
    SubComponent,
    SubProjectGroup,
)
from issues.permissions import IsReporterOrAssigneePermission
from issues.serializers import (
    AdministrativeRegionSerializer,
    CitizenAgeGroupSerializer,
    CitizenGroupSerializer,
    CommentCreateSerializer,
    CommentSerializer,
    ComponentSerializer,
    IssueAttachmentCreateSerializer,
    IssueAttachmentSerializer,
    IssueCategorySerializer,
    IssueCreateSerializer,
    IssueDetailSerializer,
    IssueSerializer,
    IssueStatusSerializer,
    IssueSubTypeSerializer,
    IssueTypeSerializer,
    IssueUpdateSerializer,
    SubComponentSerializer,
    SubProjectGroupSerializer,
)

logger = logging.getLogger(__name__)


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
                'issue_type': openapi.Schema(type=openapi.TYPE_INTEGER, description='ID of the issue type', example=1),
                'issue_sub_type': openapi.Schema(
                    type=openapi.TYPE_INTEGER, description='ID of the issue sub type', example=1
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
                'reporter': openapi.Schema(
                    type=openapi.TYPE_INTEGER, description='ID of the user who reported the issue', example=7
                ),
                'assignee': openapi.Schema(
                    type=openapi.TYPE_INTEGER, description='ID of the user assigned to handle the issue', example=7
                ),
            },
        ),
        responses={
            201: openapi.Response(
                description="Issue created successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING, example=ISSUE_CREATE_SUCCESS_MESSAGE),
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
                                'appeal_status': openapi.Schema(
                                    type=openapi.TYPE_BOOLEAN,
                                    description='Flag indicating if the issue is under appeal',
                                    example=False,
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
                                        'created_date': openapi.Schema(
                                            type=openapi.TYPE_STRING,
                                            format=openapi.FORMAT_DATETIME,
                                            example='2024-08-28T10:30:45.123456Z',
                                        ),
                                        'updated_date': openapi.Schema(
                                            type=openapi.TYPE_STRING,
                                            format=openapi.FORMAT_DATETIME,
                                            example='2024-08-28T10:30:45.123456Z',
                                        ),
                                    },
                                    description="Administrative region information",
                                ),
                                'created_date': openapi.Schema(
                                    type=openapi.TYPE_STRING,
                                    format=openapi.FORMAT_DATETIME,
                                    example='2024-08-28T10:30:45.123456Z',
                                ),
                                'updated_date': openapi.Schema(
                                    type=openapi.TYPE_STRING,
                                    format=openapi.FORMAT_DATETIME,
                                    example='2024-08-28T10:30:45.123456Z',
                                ),
                            },
                        ),
                    },
                ),
            ),
            400: openapi.Response(
                description="Bad Request - Validation Failed",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING, example=VALIDATION_FAILED_MESSAGE),
                        'errors': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            description='Field-specific validation errors',
                            properties={
                                'category': openapi.Schema(
                                    type=openapi.TYPE_ARRAY,
                                    items=openapi.Schema(type=openapi.TYPE_STRING),
                                    example=["This field is required."],
                                ),
                                'issue_type': openapi.Schema(
                                    type=openapi.TYPE_ARRAY,
                                    items=openapi.Schema(type=openapi.TYPE_STRING),
                                    example=["This field is required."],
                                ),
                                'administrative_region': openapi.Schema(
                                    type=openapi.TYPE_ARRAY,
                                    items=openapi.Schema(type=openapi.TYPE_STRING),
                                    example=["This field is required."],
                                ),
                                'contact_method': openapi.Schema(
                                    type=openapi.TYPE_ARRAY,
                                    items=openapi.Schema(type=openapi.TYPE_STRING),
                                    example=[CONTACT_MEDIUM_ERROR_MESSAGE],
                                ),
                                'contact_information': openapi.Schema(
                                    type=openapi.TYPE_ARRAY,
                                    items=openapi.Schema(type=openapi.TYPE_STRING),
                                    example=[CONTACT_INFO_EMAIL_ERROR_MESSAGE],
                                ),
                            },
                        ),
                    },
                ),
            ),
            401: openapi.Response(
                description="Unauthorized - Invalid or missing token",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={'detail': openapi.Schema(type=openapi.TYPE_STRING, example="Invalid token.")},
                ),
            ),
            500: openapi.Response(
                description="Internal Server Error",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={'detail': openapi.Schema(type=openapi.TYPE_STRING, example=ISSUE_CREATE_ERROR_MESSAGE)},
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

                # Update last_activity for issue creation
                request.user.update_last_activity()

                # Send number creation notification
                try:
                    send_issue_notification(issue, 'created')
                except Exception as e:
                    # Log error but don't fail the issue creation
                    logger.error(f"Failed to send creation notification for issue {issue.id}: {str(e)}")

                detail_serializer = IssueDetailSerializer(issue)
                return Response(
                    {'message': ISSUE_CREATE_SUCCESS_MESSAGE, 'data': detail_serializer.data},
                    status=status.HTTP_201_CREATED,
                )
            else:
                return Response(
                    {'message': VALIDATION_FAILED_MESSAGE, 'errors': serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except Exception as e:
            return Response(
                {'message': ISSUE_CREATE_ERROR_MESSAGE, 'error': str(e)},
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
        operation_description=(
            "Retrieve a paginated list of issues where the authenticated user is the assignee.\n\n"
            "Optional filters:\n"
            "- `created_date`: Only include issues created after the given datetime.\n"
            "- `updated_date`: Only include issues updated after the given datetime."
        ),
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
            openapi.Parameter(
                'created_date',
                openapi.IN_QUERY,
                description="Filter issues created after this datetime (ISO 8601 format, e.g. 2021-03-23T10:30:45Z)",
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_DATETIME,
                required=False,
            ),
            openapi.Parameter(
                'updated_date',
                openapi.IN_QUERY,
                description="Filter issues updated after this datetime (ISO 8601 format, e.g. 2021-03-23T10:30:45Z)",
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_DATETIME,
                required=False,
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
                                    'description': openapi.Schema(
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
                                    'created_date': openapi.Schema(
                                        type=openapi.TYPE_STRING,
                                        format=openapi.FORMAT_DATETIME,
                                        example='2024-08-28T10:30:45.123456Z',
                                    ),
                                    'updated_date': openapi.Schema(
                                        type=openapi.TYPE_STRING,
                                        format=openapi.FORMAT_DATETIME,
                                        example='2024-08-28T10:30:45.123456Z',
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
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={'detail': openapi.Schema(type=openapi.TYPE_STRING, example="Invalid token.")},
                ),
            ),
            500: openapi.Response(description="Internal server error"),
        },
    )
    def get(self, request, *args, **kwargs):
        """
        Retrieve paginated list of Issue objects.

        Returns a paginated list of issues assigned to the authenticated user.
        The list is ordered by intake date in descending order (most recent first).

        Query Parameters:
        - created_date: Filter issues created after this datetime (ISO 8601).
        - updated_date: Filter issues updated after this datetime (ISO 8601).

        Args:
            request: HTTP request object

        Returns:
            Response: JSON response with paginated list of issues
        """
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        qs = Issue.objects.select_related(
            'status', 'category', 'issue_type', 'administrative_region', 'reporter', 'assignee'
        ).filter(assignee=self.request.user, confirmed=True)
        created_date = self.request.query_params.get("created_date")
        if created_date:
            dt = parse_datetime(created_date)
            if not dt:
                raise ValidationError({"created_date": ISSUE_LIST_ERROR_MESSAGE})
            qs = qs.filter(created_date__gt=dt)
        updated_date = self.request.query_params.get("updated_date")
        if updated_date:
            dt = parse_datetime(updated_date)
            if not dt:
                raise ValidationError({"updated_date": ISSUE_LIST_ERROR_MESSAGE})
            qs = qs.filter(updated_date__gt=dt)
        return qs.order_by("-intake_date")


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
        operation_description=(
            "Retrieve a paginated list of issues where the authenticated user is the reporter.\n\n"
            "Optional filters:\n"
            "- `created_date`: Only include issues created after the given datetime.\n"
            "- `updated_date`: Only include issues updated after the given datetime."
        ),
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
            openapi.Parameter(
                'created_date',
                openapi.IN_QUERY,
                description="Filter issues created after this datetime (ISO 8601 format, e.g. 2021-03-23T10:30:45Z)",
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_DATETIME,
                required=False,
            ),
            openapi.Parameter(
                'updated_date',
                openapi.IN_QUERY,
                description="Filter issues updated after this datetime (ISO 8601 format, e.g. 2021-03-23T10:30:45Z)",
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_DATETIME,
                required=False,
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
                                    'description': openapi.Schema(
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
                                    'created_date': openapi.Schema(
                                        type=openapi.TYPE_STRING,
                                        format=openapi.FORMAT_DATETIME,
                                        example='2024-08-28T10:30:45.123456Z',
                                    ),
                                    'updated_date': openapi.Schema(
                                        type=openapi.TYPE_STRING,
                                        format=openapi.FORMAT_DATETIME,
                                        example='2024-08-28T10:30:45.123456Z',
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
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={'detail': openapi.Schema(type=openapi.TYPE_STRING, example="Invalid token.")},
                ),
            ),
            500: openapi.Response(description="Internal server error"),
        },
    )
    def get(self, request, *args, **kwargs):
        """
        Retrieve paginated list of Issue objects.

        Returns a paginated list of issues reported by the authenticated user.
        The list is ordered by intake date in descending order (most recent first).

        Query Parameters:
        - created_date: Filter issues created after this datetime (ISO 8601).
        - updated_date: Filter issues updated after this datetime (ISO 8601).

        Args:
            request: HTTP request object

        Returns:
            Response: JSON response with paginated list of issues
        """
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        qs = Issue.objects.select_related(
            'status', 'category', 'issue_type', 'administrative_region', 'reporter', 'assignee'
        ).filter(reporter=self.request.user, confirmed=True)
        created_date = self.request.query_params.get("created_date")
        if created_date:
            dt = parse_datetime(created_date)
            if not dt:
                raise ValidationError({"created_date": ISSUE_LIST_ERROR_MESSAGE})
            qs = qs.filter(created_date__gt=dt)
        updated_date = self.request.query_params.get("updated_date")
        if updated_date:
            dt = parse_datetime(updated_date)
            if not dt:
                raise ValidationError({"updated_date": ISSUE_LIST_ERROR_MESSAGE})
            qs = qs.filter(updated_date__gt=dt)
        return qs.order_by("-intake_date")


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

    queryset = (
        Issue.objects.select_related(
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
        )
        .prefetch_related('category__parent')
        .filter(confirmed=True)
    )
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
                        'description': openapi.Schema(type=openapi.TYPE_STRING, example="Network connectivity issue"),
                        'research_result': openapi.Schema(
                            type=openapi.TYPE_STRING,
                            example="Final resolution applied.",
                            description="Resolution text entered when closing the issue (may be empty).",
                        ),
                        'rating': openapi.Schema(
                            type=openapi.TYPE_INTEGER,
                            example=4,
                            description="Citizen rating for the issue resolution (1-5).",
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
                                'id': openapi.Schema(type=openapi.TYPE_INTEGER, example=1, description="Issue type ID"),
                                'name': openapi.Schema(
                                    type=openapi.TYPE_STRING, example="Complaint", description="Type name"
                                ),
                            },
                            description="Issue type information",
                        ),
                        'created_date': openapi.Schema(
                            type=openapi.TYPE_STRING,
                            format=openapi.FORMAT_DATETIME,
                            example='2024-08-28T10:30:45.123456Z',
                        ),
                        'updated_date': openapi.Schema(
                            type=openapi.TYPE_STRING,
                            format=openapi.FORMAT_DATETIME,
                            example='2024-08-28T10:30:45.123456Z',
                        ),
                    },
                ),
            ),
            401: openapi.Response(
                description="Unauthorized - Invalid or missing token",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={'detail': openapi.Schema(type=openapi.TYPE_STRING, example="Invalid token.")},
                ),
            ),
            403: openapi.Response(description="Forbidden - User is not the reporter or assignee of this issue"),
            404: openapi.Response(description="Not Found - Issue with the specified ID does not exist"),
            500: openapi.Response(
                description="Internal Server Error - Unexpected server error",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'detail': openapi.Schema(type=openapi.TYPE_STRING, example=ISSUE_RETRIEVE_ERROR_MESSAGE)
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
                {'detail': ISSUE_RETRIEVE_ERROR_MESSAGE},
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
        operation_description="Retrieve a paginated list of all issue statuses ordered by id.",
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
                                    'created_date': openapi.Schema(
                                        type=openapi.TYPE_STRING,
                                        format=openapi.FORMAT_DATETIME,
                                        example='2024-08-28T10:30:45.123456Z',
                                    ),
                                    'updated_date': openapi.Schema(
                                        type=openapi.TYPE_STRING,
                                        format=openapi.FORMAT_DATETIME,
                                        example='2024-08-28T10:30:45.123456Z',
                                    ),
                                },
                            ),
                            description="List of issue statuses for current page",
                        ),
                    },
                ),
            ),
            400: openapi.Response(description="Bad request - Invalid query parameters"),
            401: openapi.Response(
                description="Unauthorized - Invalid or missing token",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={'detail': openapi.Schema(type=openapi.TYPE_STRING, example="Invalid token.")},
                ),
            ),
            500: openapi.Response(description="Internal server error"),
        },
    )
    def get(self, request, *args, **kwargs):
        """
        Retrieve paginated list of IssueStatus objects.

        Returns a paginated list of all issue statuses available in the system.
        The list is ordered ascending by status id.

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
                                    'created_date': openapi.Schema(
                                        type=openapi.TYPE_STRING,
                                        format=openapi.FORMAT_DATETIME,
                                        example='2024-08-28T10:30:45.123456Z',
                                    ),
                                    'updated_date': openapi.Schema(
                                        type=openapi.TYPE_STRING,
                                        format=openapi.FORMAT_DATETIME,
                                        example='2024-08-28T10:30:45.123456Z',
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
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={'detail': openapi.Schema(type=openapi.TYPE_STRING, example="Invalid token.")},
                ),
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
                                        type=openapi.TYPE_STRING, description="Confidentiality level"
                                    ),
                                    'redirection_protocol': openapi.Schema(
                                        type=openapi.TYPE_STRING, description="Redirection protocol number"
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
                                    'created_date': openapi.Schema(
                                        type=openapi.TYPE_STRING,
                                        format=openapi.FORMAT_DATETIME,
                                        example='2024-08-28T10:30:45.123456Z',
                                    ),
                                    'updated_date': openapi.Schema(
                                        type=openapi.TYPE_STRING,
                                        format=openapi.FORMAT_DATETIME,
                                        example='2024-08-28T10:30:45.123456Z',
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
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={'detail': openapi.Schema(type=openapi.TYPE_STRING, example="Invalid token.")},
                ),
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

        # Update last_activity for comment creation
        self.request.user.update_last_activity()

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
            {'message': COMMENT_CREATE_SUCCESS_MESSAGE, 'data': data}, status=status.HTTP_201_CREATED, headers=headers
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
                ),
            },
        ),
        responses={
            201: openapi.Response(
                description="Comment created successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING, example=COMMENT_CREATE_SUCCESS_MESSAGE),
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
                                'created_date': openapi.Schema(
                                    type=openapi.TYPE_STRING,
                                    format=openapi.FORMAT_DATETIME,
                                    example='2024-08-28T10:30:45.123456Z',
                                ),
                                'updated_date': openapi.Schema(
                                    type=openapi.TYPE_STRING,
                                    format=openapi.FORMAT_DATETIME,
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
                        'message': openapi.Schema(type=openapi.TYPE_STRING, example=VALIDATION_FAILED_MESSAGE),
                        'errors': openapi.Schema(
                            type=openapi.TYPE_OBJECT, description='Field-specific validation errors'
                        ),
                    },
                ),
            ),
            401: openapi.Response(
                description="Unauthorized - Invalid or missing token",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={'detail': openapi.Schema(type=openapi.TYPE_STRING, example="Invalid token.")},
                ),
            ),
            403: openapi.Response(description="Forbidden - User is not the reporter or assignee of this issue"),
            404: openapi.Response(description="Not Found - Issue with the specified ID does not exist"),
            500: openapi.Response(
                description="Internal Server Error - Unexpected server error",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'detail': openapi.Schema(type=openapi.TYPE_STRING, example=COMMENT_CREATE_ERROR_MESSAGE)
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
                {'detail': NOT_FOUND_MESSAGE},
                status=status.HTTP_404_NOT_FOUND,
            )
        except ValidationError as e:
            return Response(
                {
                    'message': VALIDATION_FAILED_MESSAGE,
                    'errors': e.detail,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            return Response(
                {'detail': COMMENT_CREATE_ERROR_MESSAGE},
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
                                    'created_date': openapi.Schema(
                                        type=openapi.TYPE_STRING,
                                        format=openapi.FORMAT_DATETIME,
                                        example='2024-08-28T10:30:45.123456Z',
                                    ),
                                    'updated_date': openapi.Schema(
                                        type=openapi.TYPE_STRING,
                                        format=openapi.FORMAT_DATETIME,
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
            500: openapi.Response(
                description="Internal Server Error - Unexpected server error",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'detail': openapi.Schema(type=openapi.TYPE_STRING, example=COMMENT_RETRIEVE_ERROR_MESSAGE)
                    },
                ),
            ),
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
                {'detail': COMMENT_RETRIEVE_ERROR_MESSAGE},
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

        # Update last_activity for comment deletion
        self.request.user.update_last_activity()

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
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={'detail': openapi.Schema(type=openapi.TYPE_STRING, example="Invalid token.")},
                ),
            ),
            403: openapi.Response(description="Forbidden - User is not the reporter or assignee of this issue"),
            404: openapi.Response(description="Not Found - Comment with the specified ID does not exist"),
            500: openapi.Response(
                description="Internal Server Error - Unexpected server error",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "detail": openapi.Schema(type=openapi.TYPE_STRING, example=COMMENT_DELETE_ERROR_MESSAGE)
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
            return Response({"detail": NOT_FOUND_MESSAGE}, status=status.HTTP_404_NOT_FOUND)
        except Exception:
            return Response(
                {"detail": COMMENT_DELETE_ERROR_MESSAGE},
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

        # Update last_activity for attachment creation
        self.request.user.update_last_activity()

        return instance

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = self.perform_create(serializer)
        data = IssueAttachmentSerializer(instance).data
        headers = self.get_success_headers(data)
        return Response(
            {'message': ATTACHMENT_CREATE_SUCCESS_MESSAGE, 'data': data},
            status=status.HTTP_201_CREATED,
            headers=headers,
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
                        'message': openapi.Schema(type=openapi.TYPE_STRING, example=ATTACHMENT_CREATE_SUCCESS_MESSAGE),
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
                                    example='2024-08-28T10:30:45.123456Z',
                                ),
                                'updated_date': openapi.Schema(
                                    type=openapi.TYPE_STRING,
                                    format=openapi.FORMAT_DATETIME,
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
                        'message': openapi.Schema(type=openapi.TYPE_STRING, example=VALIDATION_FAILED_MESSAGE),
                        'errors': openapi.Schema(
                            type=openapi.TYPE_OBJECT, description='Field-specific validation errors'
                        ),
                    },
                ),
            ),
            401: openapi.Response(
                description="Unauthorized - Invalid or missing token",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={'detail': openapi.Schema(type=openapi.TYPE_STRING, example="Invalid token.")},
                ),
            ),
            403: openapi.Response(description="Forbidden - User is not the reporter or assignee of this issue"),
            404: openapi.Response(description="Not Found - Issue with the specified ID does not exist"),
            500: openapi.Response(
                description="Internal Server Error - Unexpected server error",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'detail': openapi.Schema(type=openapi.TYPE_STRING, example=ATTACHMENT_CREATE_ERROR_MESSAGE)
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
                {'detail': NOT_FOUND_MESSAGE},
                status=status.HTTP_404_NOT_FOUND,
            )
        except ValidationError as e:
            return Response(
                {
                    'message': VALIDATION_FAILED_MESSAGE,
                    'errors': e.detail,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            return Response(
                {'detail': ATTACHMENT_CREATE_ERROR_MESSAGE},
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
        qs = IssueAttachment.objects.filter(issue_id=issue_id).select_related("uploaded_by", "issue")
        created_date = self.request.query_params.get("created_date")
        if created_date:
            dt = parse_datetime(created_date)
            if not dt:
                raise ValidationError({"created_date": ISSUE_LIST_ERROR_MESSAGE})
            qs = qs.filter(created_date__gt=dt)
        updated_date = self.request.query_params.get("updated_date")
        if updated_date:
            dt = parse_datetime(updated_date)
            if not dt:
                raise ValidationError({"updated_date": ISSUE_LIST_ERROR_MESSAGE})
            qs = qs.filter(updated_date__gt=dt)
        deleted_date = self.request.query_params.get("deleted_date")
        if deleted_date:
            dt = parse_datetime(deleted_date)
            if not dt:
                raise ValidationError({"deleted_date": ISSUE_LIST_ERROR_MESSAGE})
            qs = qs.filter(deleted_date__gt=dt)
        return qs

    @swagger_auto_schema(
        operation_summary="List attachments of a specific issue",
        operation_description="""
        Retrieve a paginated list of attachments associated with a specific issue.
        Optional filters:
        - `created_date`: Only include issues created after the given datetime.
        - `updated_date`: Only include issues updated after the given datetime.
        - `deleted_date`: Only include issues deleted after the given datetime.

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
            ),
            openapi.Parameter(
                'created_date',
                openapi.IN_QUERY,
                description="Filter attachments created after this datetime (ISO 8601 format, e.g. 2021-03-23T10:30:45Z)",
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_DATETIME,
                required=False,
            ),
            openapi.Parameter(
                'updated_date',
                openapi.IN_QUERY,
                description="Filter attachments updated after this datetime (ISO 8601 format, e.g. 2021-03-23T10:30:45Z)",
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_DATETIME,
                required=False,
            ),
            openapi.Parameter(
                'deleted_date',
                openapi.IN_QUERY,
                description="Filter attachments deleted after this datetime (ISO 8601 format, e.g. 2021-03-23T10:30:45Z)",
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_DATETIME,
                required=False,
            ),
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
                                        example='2024-08-28T10:30:45.123456Z',
                                    ),
                                    'updated_date': openapi.Schema(
                                        type=openapi.TYPE_STRING,
                                        format=openapi.FORMAT_DATETIME,
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
            500: openapi.Response(
                description="Internal Server Error - Unexpected server error",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'detail': openapi.Schema(type=openapi.TYPE_STRING, example=ATTACHMENT_RETRIEVE_ERROR_MESSAGE)
                    },
                ),
            ),
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
                {'detail': ATTACHMENT_RETRIEVE_ERROR_MESSAGE},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class IssueAttachmentDeleteAPIView(DestroyAPIView):
    """
    API View for deleting a specific IssueAttachment object related to an Issue.

    Only the reporter or assignee of the related issue can delete the attachment.
    """

    queryset = IssueAttachment.objects.select_related("issue", "uploaded_by")
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsReporterOrAssigneePermission]

    def get_issue(self):
        """
        Retrieve the Issue object based on the attachment.

        Returns:
            Issue: The issue object to which the attachment will be deleted
        """
        attachment_id = self.kwargs.get("id")
        attachment = get_object_or_404(IssueAttachment.objects.select_related("issue"), id=attachment_id)
        self.attachment_instance = attachment
        return attachment.issue

    def get_object(self):
        """
        Override to return the Issue object for permission checks,
        while keeping a reference to the Attachment for deletion.
        """
        issue = self.get_issue()
        return issue

    def perform_destroy(self, instance):
        """
        Actually delete the attachment after permission check.
        """
        self.attachment_instance.delete()

        # Update last_activity for attachment deletion
        self.request.user.update_last_activity()

    @swagger_auto_schema(
        operation_summary="Delete an attachment from a specific issue",
        operation_description="""
        Delete an existing attachment from an issue.

        **Access Control:**
        - Only users who are either the reporter or assignee of the issue can delete attachments.
        - Ensures that unauthorized users cannot remove attachments from issues.

        **Business Rules:**
        - Attachment must exist
        - User must be authenticated with a valid token
        - User must be either the issue reporter or assignee
        """,
        tags=["Issues", "Attachments"],
        security=[{'Token': []}],
        manual_parameters=[
            openapi.Parameter(
                "id",
                openapi.IN_PATH,
                description="Unique identifier of the attachment to delete",
                type=openapi.TYPE_INTEGER,
                required=True,
                example=42,
            )
        ],
        responses={
            204: openapi.Response(description="Attachment deleted successfully"),
            401: openapi.Response(
                description="Unauthorized - Invalid or missing token",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={'detail': openapi.Schema(type=openapi.TYPE_STRING, example="Invalid token.")},
                ),
            ),
            403: openapi.Response(description="Forbidden - User is not the reporter or assignee of this issue"),
            404: openapi.Response(description="Not Found - Attachment with the specified ID does not exist"),
            500: openapi.Response(
                description="Internal Server Error - Unexpected server error",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "detail": openapi.Schema(type=openapi.TYPE_STRING, example=ATTACHMENT_CREATE_ERROR_MESSAGE)
                    },
                ),
            ),
        },
    )
    def delete(self, request, *args, **kwargs):
        """
        Delete the specified Attachment.

        Handles permission checks and returns appropriate status codes.
        """
        try:
            return super().delete(request, *args, **kwargs)
        except Http404:
            return Response({"detail": NOT_FOUND_MESSAGE}, status=status.HTTP_404_NOT_FOUND)
        except Exception:
            return Response(
                {"detail": ATTACHMENT_CREATE_ERROR_MESSAGE},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class IssueUpdateAPIView(UpdateAPIView):
    """
    API View for updating specific fields of Issue objects.

    This view handles partial updates (PATCH) of Issue instances allowing only
    specific fields to be modified.

    Requires Token authentication and validates that the user is either
    the reporter or assignee of the issue.
    """

    # Only confirmed issues can be updated via this API
    queryset = Issue.objects.filter(confirmed=True)
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

        **Field-specific restrictions:**
        - `status` and `appeal_status`: Only assignees can modify
        - `rating`: Only reporters can modify
        - Other fields: Both reporters and assignees can modify
        """,
        tags=['Issues'],
        security=[{'Token': []}],
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'appeal_reason': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Reason for appeal',
                    example='The issue occurred in another village.',
                ),
                'appeal_status': openapi.Schema(
                    type=openapi.TYPE_BOOLEAN,
                    description='Flag indicating if the issue is under appeal',
                    example=False,
                ),
                'escalate_flag': openapi.Schema(
                    type=openapi.TYPE_BOOLEAN,
                    description='Flag indicating if the issue should be escalated',
                    example=True,
                ),
                'escalation_reason': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Reason for escalating the issue',
                    example='Issue requires higher level approval',
                ),
                'rating': openapi.Schema(
                    type=openapi.TYPE_INTEGER,
                    description='Rating for the issue resolution (1-5)',
                    minimum=1,
                    maximum=5,
                    example=4,
                ),
                'reject_flag': openapi.Schema(
                    type=openapi.TYPE_BOOLEAN,
                    description='Flag indicating if the issue is rejected',
                    example=False,
                ),
                'reject_reason': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Reason for rejecting the issue',
                    example='Issue requires higher level approval',
                ),
                'research_result': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    description='Results of research conducted on the issue',
                    example='Investigation completed. Root cause identified.',
                ),
                'status': openapi.Schema(
                    type=openapi.TYPE_INTEGER,
                    description='ID of the new issue status',
                    example=2,
                ),
            },
        ),
        responses={
            200: openapi.Response(
                description="Issue updated successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING, example=ISSUE_UPDATE_SUCCESS_MESSAGE),
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
                                'appeal_status': openapi.Schema(
                                    type=openapi.TYPE_BOOLEAN,
                                    example=False,
                                    description="Flag indicating if the issue is under appeal",
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
                                'created_date': openapi.Schema(
                                    type=openapi.TYPE_STRING,
                                    format=openapi.FORMAT_DATETIME,
                                    example='2024-08-28T10:30:45.123456Z',
                                ),
                                'updated_date': openapi.Schema(
                                    type=openapi.TYPE_STRING,
                                    format=openapi.FORMAT_DATETIME,
                                    example='2024-08-28T10:30:45.123456Z',
                                ),
                            },
                        ),
                    },
                ),
            ),
            400: openapi.Response(
                description="Bad Request - Validation Failed",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING, example=VALIDATION_FAILED_MESSAGE),
                        'errors': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'rating': openapi.Schema(
                                    type=openapi.TYPE_ARRAY,
                                    items=openapi.Schema(type=openapi.TYPE_STRING),
                                    example=["Ensure this value is less than or equal to 5."],
                                ),
                                'status': openapi.Schema(
                                    type=openapi.TYPE_ARRAY,
                                    items=openapi.Schema(type=openapi.TYPE_STRING),
                                    example=["Invalid pk \"999\" - object does not exist."],
                                ),
                            },
                        ),
                    },
                ),
            ),
            401: openapi.Response(
                description="Unauthorized - Invalid or missing token",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={'detail': openapi.Schema(type=openapi.TYPE_STRING, example="Invalid token.")},
                ),
            ),
            403: openapi.Response(
                description="Forbidden - User is not reporter or assignee, or lacks permission for specific field",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'detail': openapi.Schema(
                            type=openapi.TYPE_STRING, example="You do not have permission to perform this action."
                        )
                    },
                ),
            ),
            404: openapi.Response(
                description="Not Found - Issue does not exist",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={'detail': openapi.Schema(type=openapi.TYPE_STRING, example=NOT_FOUND_MESSAGE)},
                ),
            ),
            500: openapi.Response(
                description="Internal Server Error",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={'detail': openapi.Schema(type=openapi.TYPE_STRING, example=ISSUE_UPDATE_ERROR_MESSAGE)},
                ),
            ),
        },
    )
    def patch(self, request, *args, **kwargs):
        """
        Partially update an Issue instance.

        Overrides the default update method to provide custom response format
        and error handling. Only allows updating specific permitted fields.

        Role-based restrictions:
        - Only assignees can edit 'status' and 'appeal_status'
        - Only reporters can edit 'rating'
        - Both reporters and assignees can edit other fields

        Args:
            request: HTTP request object containing updated issue data
            *args: Variable length argument list
            **kwargs: Arbitrary keyword arguments (includes 'id' from URL)

        Returns:
            Response: JSON response with updated issue data or error details
        """
        try:
            instance = self.get_object()
            # Save the previous status and appeal_status to detect changes
            old_status_id = instance.status_id if instance.status else None
            old_appeal_status = instance.appeal_status

            serializer = self.get_serializer(instance, data=request.data, partial=True)
            if serializer.is_valid():
                updated_issue = serializer.save()

                # Update last_activity for issue modification
                request.user.update_last_activity()

                # Send notification if there was a change in status
                new_status_id = updated_issue.status_id if updated_issue.status else None
                if old_status_id != new_status_id:
                    try:
                        send_issue_notification(updated_issue, 'status_changed')
                    except Exception as e:
                        # Log error but don't fail the update
                        logger.error(
                            f"Failed to send status change notification for issue {updated_issue.id}: {str(e)}"
                        )

                # Send notification if change appeal_status to True
                if not old_appeal_status and updated_issue.appeal_status:
                    try:
                        send_issue_notification(updated_issue, 'appealed')
                    except Exception as e:
                        # Log error but don't fail the update
                        logger.error(
                            f"Failed to send appeal status change notification for issue {updated_issue.id}: {str(e)}"
                        )

                detail_serializer = IssueDetailSerializer(updated_issue)
                return Response(
                    {'message': ISSUE_UPDATE_SUCCESS_MESSAGE, 'data': detail_serializer.data},
                    status=status.HTTP_200_OK,
                )
            else:
                return Response(
                    {'message': VALIDATION_FAILED_MESSAGE, 'errors': serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except MethodNotAllowed as e:
            return Response(
                {'message': str(e.detail)},
                status=status.HTTP_405_METHOD_NOT_ALLOWED,
            )
        except Issue.DoesNotExist:
            return Response(
                {'message': NOT_FOUND_MESSAGE},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {'message': ISSUE_UPDATE_ERROR_MESSAGE, 'error': str(e)},
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
                                    'created_date': openapi.Schema(
                                        type=openapi.TYPE_STRING,
                                        format=openapi.FORMAT_DATETIME,
                                        example='2024-08-28T10:30:45.123456Z',
                                    ),
                                    'updated_date': openapi.Schema(
                                        type=openapi.TYPE_STRING,
                                        format=openapi.FORMAT_DATETIME,
                                        example='2024-08-28T10:30:45.123456Z',
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
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={'detail': openapi.Schema(type=openapi.TYPE_STRING, example="Invalid token.")},
                ),
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
                                    'created_date': openapi.Schema(
                                        type=openapi.TYPE_STRING,
                                        format=openapi.FORMAT_DATETIME,
                                        example='2024-08-28T10:30:45.123456Z',
                                    ),
                                    'updated_date': openapi.Schema(
                                        type=openapi.TYPE_STRING,
                                        format=openapi.FORMAT_DATETIME,
                                        example='2024-08-28T10:30:45.123456Z',
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
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={'detail': openapi.Schema(type=openapi.TYPE_STRING, example="Invalid token.")},
                ),
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
                                    'created_date': openapi.Schema(
                                        type=openapi.TYPE_STRING,
                                        format=openapi.FORMAT_DATETIME,
                                        example='2024-08-28T10:30:45.123456Z',
                                    ),
                                    'updated_date': openapi.Schema(
                                        type=openapi.TYPE_STRING,
                                        format=openapi.FORMAT_DATETIME,
                                        example='2024-08-28T10:30:45.123456Z',
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
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={'detail': openapi.Schema(type=openapi.TYPE_STRING, example="Invalid token.")},
                ),
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


class ComponentListAPIView(ListAPIView):
    """
    API View for listing Component objects with pagination.

    This view provides a paginated read-only list of all available components.
    It requires Token authentication and returns paginated results.
    """

    queryset = Component.objects.all()
    serializer_class = ComponentSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="List Components",
        operation_description="Retrieve a paginated list of all components.",
        tags=['Components'],
        security=[{'Token': []}],
        manual_parameters=[
            openapi.Parameter(
                'page',
                openapi.IN_QUERY,
                description="Page number for pagination",
                type=openapi.TYPE_INTEGER,
                default=1,
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
                description="Paginated list of components",
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
                                        description="Unique identifier for the component",
                                    ),
                                    'name': openapi.Schema(
                                        type=openapi.TYPE_STRING, description="Name of the component"
                                    ),
                                    'description': openapi.Schema(
                                        type=openapi.TYPE_STRING,
                                        description='Detailed description of the component',
                                        example='Community investments to strengthen local resilience and inclusion.',
                                    ),
                                    'created_date': openapi.Schema(
                                        type=openapi.TYPE_STRING,
                                        format=openapi.FORMAT_DATETIME,
                                        example='2024-08-28T10:30:45.123456Z',
                                    ),
                                    'updated_date': openapi.Schema(
                                        type=openapi.TYPE_STRING,
                                        format=openapi.FORMAT_DATETIME,
                                        example='2024-08-28T10:30:45.123456Z',
                                    ),
                                },
                            ),
                            description="List of components for current page",
                        ),
                    },
                ),
            ),
            400: openapi.Response(description="Bad request - Invalid query parameters"),
            401: openapi.Response(
                description="Unauthorized - Invalid or missing token",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={'detail': openapi.Schema(type=openapi.TYPE_STRING, example="Invalid token.")},
                ),
            ),
            500: openapi.Response(description="Internal server error"),
        },
    )
    def get(self, request, *args, **kwargs):
        """
        Retrieve paginated list of Component objects.

        Returns a paginated list of all components available in the system.

        Args:
            request: HTTP request object

        Returns:
            Response: JSON response with paginated list of components
        """
        return super().get(request, *args, **kwargs)


class SubComponentListAPIView(ListAPIView):
    """
    API View for listing SubComponent objects with pagination.

    This view provides a paginated read-only list of all available subcomponents.
    It requires Token authentication and returns paginated results.
    """

    queryset = SubComponent.objects.all()
    serializer_class = SubComponentSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="List Subcomponents",
        operation_description="Retrieve a paginated list of all subcomponents.",
        tags=['Subcomponents'],
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
                description="Paginated list of subcomponents",
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
                                        description="Unique identifier for the subcomponent",
                                    ),
                                    'name': openapi.Schema(
                                        type=openapi.TYPE_STRING, description="Name of the subcomponent"
                                    ),
                                    'description': openapi.Schema(
                                        type=openapi.TYPE_STRING,
                                        description='Detailed description of the subcomponent',
                                        example='Community investments to strengthen local resilience and inclusion.',
                                    ),
                                    'parent': openapi.Schema(
                                        type=openapi.TYPE_OBJECT,
                                        properties={
                                            'id': openapi.Schema(type=openapi.TYPE_INTEGER, description="Component ID"),
                                            'name': openapi.Schema(
                                                type=openapi.TYPE_STRING, description="Component name"
                                            ),
                                            'description': openapi.Schema(
                                                type=openapi.TYPE_STRING,
                                                description='Detailed description of the component',
                                                example='Investing in community resilience and inclusion.',
                                            ),
                                        },
                                    ),
                                    'created_date': openapi.Schema(
                                        type=openapi.TYPE_STRING,
                                        format=openapi.FORMAT_DATETIME,
                                        example='2024-08-28T10:30:45.123456Z',
                                    ),
                                    'updated_date': openapi.Schema(
                                        type=openapi.TYPE_STRING,
                                        format=openapi.FORMAT_DATETIME,
                                        example='2024-08-28T10:30:45.123456Z',
                                    ),
                                },
                            ),
                            description="List of subcomponents for current page",
                        ),
                    },
                ),
            ),
            400: openapi.Response(description="Bad request - Invalid query parameters"),
            401: openapi.Response(
                description="Unauthorized - Invalid or missing token",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={'detail': openapi.Schema(type=openapi.TYPE_STRING, example="Invalid token.")},
                ),
            ),
            500: openapi.Response(description="Internal server error"),
        },
    )
    def get(self, request, *args, **kwargs):
        """
        Retrieve paginated list of SubComponent objects.

        Returns a paginated list of all subcomponents available in the system.

        Args:
            request: HTTP request object

        Returns:
            Response: JSON response with paginated list of subcomponents
        """
        return super().get(request, *args, **kwargs)


class IssueSubTypeListAPIView(ListAPIView):
    """
    API View for listing IssueSubType objects with pagination.

    This view provides a paginated read-only list of all available issue subtypes.
    It requires Token authentication and returns paginated results.
    """

    queryset = IssueSubType.objects.select_related('parent')
    serializer_class = IssueSubTypeSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="List Subtypes",
        operation_description="Retrieve a paginated list of all issue subtypes ordered by name.",
        tags=['Issue Subtypes'],
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
                description="Paginated list of issue subtypes",
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
                                        description="Unique identifier for the issue subtype",
                                    ),
                                    'name': openapi.Schema(
                                        type=openapi.TYPE_STRING, description="Name of the issue subtype"
                                    ),
                                    'parent': openapi.Schema(
                                        type=openapi.TYPE_OBJECT,
                                        properties={
                                            'id': openapi.Schema(type=openapi.TYPE_INTEGER, description="IssueType ID"),
                                            'name': openapi.Schema(
                                                type=openapi.TYPE_STRING, description="IssueType name"
                                            ),
                                            'created_date': openapi.Schema(
                                                type=openapi.TYPE_STRING,
                                                format=openapi.FORMAT_DATETIME,
                                                example='2024-08-28T10:30:45.123456Z',
                                            ),
                                            'updated_date': openapi.Schema(
                                                type=openapi.TYPE_STRING,
                                                format=openapi.FORMAT_DATETIME,
                                                example='2024-08-28T10:30:45.123456Z',
                                            ),
                                        },
                                    ),
                                    'created_date': openapi.Schema(
                                        type=openapi.TYPE_STRING,
                                        format=openapi.FORMAT_DATETIME,
                                        example='2024-08-28T10:30:45.123456Z',
                                    ),
                                    'updated_date': openapi.Schema(
                                        type=openapi.TYPE_STRING,
                                        format=openapi.FORMAT_DATETIME,
                                        example='2024-08-28T10:30:45.123456Z',
                                    ),
                                },
                            ),
                            description="List of issue subtypes for current page",
                        ),
                    },
                ),
            ),
            400: openapi.Response(description="Bad request - Invalid query parameters"),
            401: openapi.Response(
                description="Unauthorized - Invalid or missing token",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={'detail': openapi.Schema(type=openapi.TYPE_STRING, example="Invalid token.")},
                ),
            ),
            500: openapi.Response(description="Internal server error"),
        },
    )
    def get(self, request, *args, **kwargs):
        """
        Retrieve paginated list of IssueSubType objects.

        Returns a paginated list of all issue subtypes available in the system.
        The list is ordered alphabetically by status name.

        Args:
            request: HTTP request object

        Returns:
            Response: JSON response with paginated list of issue subtypes
        """
        return super().get(request, *args, **kwargs)


class AdministrativeRegionChildrenAPIView(APIView):
    """
    API View for listing AdministrativeRegion child objects (no pagination).

    This view retrieves all administrative regions that are children of a given parent.
    If 'parent' is not provided or is null, it returns all regions with no parent (top-level regions).
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="List child administrative regions (no pagination)",
        operation_description=(
            "Retrieve all administrative regions that are children of the specified parent.\n"
            "If 'parent' is not provided or is null, returns all regions with no parent."
        ),
        tags=['Administrative Regions'],
        manual_parameters=[
            openapi.Parameter(
                'parent',
                openapi.IN_QUERY,
                description='Parent AdministrativeRegion ID (use null or omit to fetch top-level regions)',
                type=openapi.TYPE_INTEGER,
                required=False,
            ),
        ],
        responses={200: AdministrativeRegionSerializer(many=True)},
    )
    def get(self, request):
        parent_id = request.query_params.get('parent')
        if parent_id in (None, '', 'null'):
            queryset = AdministrativeRegion.objects.filter(parent__isnull=True)
        else:
            queryset = AdministrativeRegion.objects.filter(parent_id=parent_id)
        serializer = AdministrativeRegionSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AdministrativeRegionListAPIView(ListAPIView):
    """
    API View for listing all AdministrativeRegion objects (paginated).

    This view provides a paginated list of all administrative regions in the system.
    """

    queryset = AdministrativeRegion.objects.all().order_by('name')
    serializer_class = AdministrativeRegionSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="List all administrative regions (paginated)",
        operation_description="Retrieve a paginated list of all administrative regions ordered by name.",
        tags=['Administrative Regions'],
        manual_parameters=[
            openapi.Parameter(
                'page',
                openapi.IN_QUERY,
                description="Page number for pagination",
                type=openapi.TYPE_INTEGER,
                default=1,
            ),
            openapi.Parameter(
                'page_size',
                openapi.IN_QUERY,
                description="Number of results per page (max: 100)",
                type=openapi.TYPE_INTEGER,
                default=20,
            ),
        ],
        responses={200: AdministrativeRegionSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
