from rest_framework import serializers
from rest_framework.exceptions import MethodNotAllowed

from authentication.serializers import UserBasicSerializer
from grm.constants import (
    ALERT_CHOICE,
    CONTACT_INFO_EMAIL_ERROR_MESSAGE,
    CONTACT_INFO_NO_EMAIL_ERROR_MESSAGE,
    CONTACT_MEDIUM_ERROR_MESSAGE,
    EMAIL_CHOICE,
    ISSUE_UPDATE_RATING_ERROR_MESSAGE,
    ISSUE_UPDATE_STATUS_ERROR_MESSAGE,
)
from grm.utils import email_is_valid
from issues.models import (
    AdministrativeRegion,
    Citizen,
    CitizenAgeGroup,
    CitizenGroup,
    Comment,
    Component,
    Issue,
    IssueAttachment,
    IssueCategory,
    IssueDepartment,
    IssueDepartmentAdministrativeLevel,
    IssueStatus,
    IssueSubType,
    IssueType,
    SubComponent,
    SubProjectGroup,
)


class AdministrativeRegionBasicSerializer(serializers.ModelSerializer):
    """
    Basic serializer for AdministrativeRegion objects.
    Provides read-only representation of administrative region information.

    Displays the administrative region with custom field names as required.
    """

    administrative_id = serializers.CharField(source='id', read_only=True)
    name = serializers.CharField(read_only=True)

    class Meta:
        model = AdministrativeRegion
        fields = ['administrative_id', 'name', 'created_date', 'updated_date']
        read_only_fields = ['administrative_id', 'name', 'created_date', 'updated_date']


class IssueCategoryBasicSerializer(serializers.ModelSerializer):
    """
    Basic serializer for IssueCategory objects.
    """

    class Meta:
        model = IssueCategory
        fields = ['id', 'name', 'created_date', 'updated_date']


class ComponentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Component
        fields = ['id', 'name', 'description', 'created_date', 'updated_date']


class SubComponentSerializer(serializers.ModelSerializer):
    parent = ComponentSerializer(read_only=True)

    class Meta:
        model = SubComponent
        fields = ['id', 'name', 'description', 'parent', 'created_date', 'updated_date']


class SubProjectGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubProjectGroup
        fields = ['id', 'name', 'created_date', 'updated_date']


class IssueTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = IssueType
        fields = ['id', 'name', 'created_date', 'updated_date']


class IssueSubTypeSerializer(serializers.ModelSerializer):
    parent = IssueTypeSerializer(read_only=True)

    class Meta:
        model = IssueSubType
        fields = ['id', 'name', 'parent', 'created_date', 'updated_date']


class CitizenAgeGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = CitizenAgeGroup
        fields = ['id', 'name', 'created_date', 'updated_date']


class CitizenGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = CitizenGroup
        fields = ['id', 'name', 'type', 'created_date', 'updated_date']


class IssueStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = IssueStatus
        fields = [
            'id',
            'name',
            'final_status',
            'initial_status',
            'rejected_status',
            'open_status',
            'created_date',
            'updated_date',
        ]


class IssueSerializer(serializers.ModelSerializer):
    """
    Serializer for the Issue model.

    This serializer provides a complete representation of the issue with nested
    user information for assignee and reporter fields, and properly formatted
    datetime fields.

    Read-only fields:
        - id: Primary key, automatically generated
        - intake_date: Automatically set on creation, formatted as ISO string
        - assignee: Nested User object
        - reporter: Nested User object
        - status: Nested IssueStatus object
        - description: Brief text describing the issue
    """

    description = serializers.CharField(read_only=True)
    intake_date = serializers.DateTimeField(format='%Y-%m-%dT%H:%M:%S.%fZ', read_only=True)
    assignee = UserBasicSerializer(read_only=True)
    reporter = UserBasicSerializer(read_only=True)
    administrative_region = AdministrativeRegionBasicSerializer(read_only=True)
    status = IssueStatusSerializer(read_only=True)
    category = IssueCategoryBasicSerializer(read_only=True)
    issue_type = IssueTypeSerializer(
        read_only=True,
    )

    class Meta:
        model = Issue
        fields = [
            'id',
            'description',
            'tracking_code',
            'intake_date',
            'administrative_region',
            'reporter',
            'assignee',
            'status',
            'category',
            'issue_type',
            'created_date',
            'updated_date',
        ]
        read_only_fields = [
            'id',
            'intake_date',
            'reporter',
            'assignee',
            'administrative_region',
            'created_date',
            'updated_date',
        ]


class DepartmentAdministrativeLevelSerializer(serializers.ModelSerializer):
    """
    Serializer for IssueDepartmentAdministrativeLevel model.

    This serializer extracts and formats the department and administrative level
    information for use in IssueCategory serialization.
    """

    name = serializers.CharField(source='department.name', read_only=True)
    id = serializers.IntegerField(source='department.id', read_only=True)
    administrative_level = serializers.CharField(source='administrative_level.name', read_only=True)

    class Meta:
        model = IssueDepartmentAdministrativeLevel
        fields = ['name', 'id', 'administrative_level', 'created_date', 'updated_date']


class IssueDepartmentSerializer(serializers.ModelSerializer):
    """
    Serializer for IssueDepartment objects.
    Provides complete representation of department information.
    """

    class Meta:
        model = IssueDepartment
        fields = ['id', 'name', 'head', 'created_date', 'updated_date']
        read_only_fields = ['id', 'name', 'head', 'created_date', 'updated_date']


class IssueCategorySerializer(serializers.ModelSerializer):
    """
    Serializer for IssueCategory model with custom department serialization.

    This serializer provides detailed information about issue categories including
    their assigned departments with administrative levels, and adds convenience
    fields 'label' and 'value' for frontend usage.
    """

    # Custom serialization for department fields
    assigned_department = DepartmentAdministrativeLevelSerializer(read_only=True)
    assigned_appeal_department = DepartmentAdministrativeLevelSerializer(read_only=True)
    assigned_escalation_department = DepartmentAdministrativeLevelSerializer(read_only=True)

    # Additional convenience fields
    label = serializers.CharField(source='name', read_only=True)
    value = serializers.IntegerField(source='id', read_only=True)
    parent_id = serializers.IntegerField(source='parent.id', read_only=True, allow_null=True)

    class Meta:
        model = IssueCategory
        fields = [
            'id',
            'name',
            'abbreviation',
            'assigned_department',
            'assigned_appeal_department',
            'assigned_escalation_department',
            'parent_id',
            'confidentiality_level',
            'redirection_protocol',
            'label',
            'value',
            'created_date',
            'updated_date',
        ]
        read_only_fields = ['id', 'created_date', 'updated_date']


class AdministrativeRegionSerializer(serializers.ModelSerializer):
    """
    Serializer for AdministrativeRegion model.
    """

    class Meta:
        model = AdministrativeRegion
        fields = ['id', 'name', 'administrative_level', 'parent', 'created_date', 'updated_date']


class CitizenSerializer(serializers.ModelSerializer):
    class Meta:
        model = Citizen
        fields = '__all__'


class IssueDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for detailed Issue representation.
    Includes nested serializers for related objects.
    """

    status = IssueStatusSerializer(read_only=True)
    category = IssueCategorySerializer(read_only=True)
    issue_type = IssueTypeSerializer(read_only=True)
    administrative_region = AdministrativeRegionSerializer(read_only=True)

    class Meta:
        model = Issue
        fields = [
            'id',
            'intake_date',
            'status',
            'category',
            'issue_type',
            'administrative_region',
            'created_date',
            'updated_date',
        ]


class IssueCreateSerializer(serializers.ModelSerializer):
    category = serializers.IntegerField(required=True)
    issue_type = serializers.IntegerField(required=True)
    issue_sub_type = serializers.IntegerField(required=True)
    citizen = CitizenSerializer(required=False)
    administrative_region = serializers.PrimaryKeyRelatedField(
        queryset=AdministrativeRegion.objects.all(), required=True
    )

    class Meta:
        model = Issue
        fields = [
            'description',
            'category',
            'issue_type',
            'issue_sub_type',
            'contact_medium',
            'contact_method',
            'contact_information',
            'tracking_code',
            'intake_date',
            'ongoing_issue',
            'location_description',
            'status',
            'administrative_region',
            'component',
            'sub_component',
            'citizen',
            'reporter',
            'assignee',
        ]
        extra_kwargs = {
            "contact_medium": {"required": True, "allow_null": False, "allow_blank": False},
            "contact_information": {"required": True, "allow_null": True, "allow_blank": True},
            "description": {"required": True, "allow_null": False, "allow_blank": False},
            "intake_date": {"required": True, "allow_null": False},
            "ongoing_issue": {"required": False, "default": False},
        }

    def create(self, validated_data):
        citizen_data = validated_data.pop('citizen')
        citizen = Citizen(
            name=citizen_data['name'],
            age_group=citizen_data['age_group'],
            type=citizen_data['type'],
            group=citizen_data['group'],
            group_2=citizen_data['group_2'],
        )
        citizen.save()
        category_data = validated_data.pop('category')
        issue_type_data = validated_data.pop('issue_type')
        issue_sub_type_data = validated_data.pop('issue_sub_type')

        issue = Issue(
            citizen_id=citizen.id,
            category_id=category_data,
            issue_type_id=issue_type_data,
            issue_sub_type_id=issue_sub_type_data,
            **validated_data
        )
        issue.save()
        return issue

    def validate(self, data):
        """
        Performs object-level validation for cross-field dependencies.
        """
        contact_medium = data.get('contact_medium')
        contact_method = data.get('contact_method')
        contact_information = data.get('contact_information')

        if contact_medium == ALERT_CHOICE and not contact_method:
            raise serializers.ValidationError({"contact_method": CONTACT_MEDIUM_ERROR_MESSAGE})

        elif contact_method == EMAIL_CHOICE and not email_is_valid(contact_information):
            raise serializers.ValidationError({"contact_information": CONTACT_INFO_EMAIL_ERROR_MESSAGE})

        elif contact_method != EMAIL_CHOICE and email_is_valid(contact_information):
            raise serializers.ValidationError({"contact_information": CONTACT_INFO_NO_EMAIL_ERROR_MESSAGE})
        return data


class IssueUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating specific fields of an Issue.

    Only allows updating the fields that are permitted for modification:
    escalate_flag, reject_flag, rating, escalation_reason, status, research_result

    Includes role-based field restrictions:
    - Only assignees can edit 'status'
    - Only reporters can edit 'rating'
    - Both can edit if user is both reporter and assignee
    """

    class Meta:
        model = Issue
        fields = ['escalate_flag', 'reject_flag', 'rating', 'escalation_reason', 'status', 'research_result']

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('context', {}).get('request')
        super().__init__(*args, **kwargs)

    def validate(self, attrs):
        """Validate role-based field restrictions."""
        if not self.request or not hasattr(self.request, 'user'):
            return attrs

        user = self.request.user
        issue = self.instance

        if not issue:
            return attrs

        # Check status field restriction
        if 'status' in attrs and user.id != getattr(issue, "assignee_id", None):
            raise MethodNotAllowed(method='PATCH', detail=ISSUE_UPDATE_STATUS_ERROR_MESSAGE)

        # Check rating field restriction
        if 'rating' in attrs and user.id != issue.reporter.id:
            raise MethodNotAllowed(method='PATCH', detail=ISSUE_UPDATE_RATING_ERROR_MESSAGE)

        return attrs


class CommentSerializer(serializers.ModelSerializer):
    """
    Serializer for Comment objects.
    Provides read-only representation of user information.
    """

    user = UserBasicSerializer(read_only=True)

    class Meta:
        model = Comment
        fields = [
            'id',
            'comment',
            'user',
            'issue',
            'due_date',
            'created_date',
            'updated_date',
        ]


class CommentCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating Comment objects.

    This serializer is used specifically for comment creation and only
    includes the comment text field. The issue and user are set automatically
    in the view.
    """

    class Meta:
        model = Comment
        fields = ['comment']


class IssueAttachmentSerializer(serializers.ModelSerializer):
    """
    Serializer for the IssueAttachment model, following the project's conventions.

    This serializer provides a representation of the attachment, including a read-only
    'url' field derived from the file field.

    Read-only fields:
        - id: Primary key
        - url: The URL of the uploaded file
        - uploaded_by: Nested User object (assuming a UserBasicSerializer is available)
        - created_date: Datetime field, automatically set on creation
        - updated_date: Datetime field, automatically set on edit
    """

    issue = IssueSerializer(read_only=True)
    url = serializers.CharField(source='file.url', read_only=True)
    uploaded_by = UserBasicSerializer(read_only=True)

    class Meta:
        model = IssueAttachment
        fields = [
            'id',
            'url',
            'issue',
            'file',
            'uploaded_by',
            'created_date',
            'updated_date',
        ]
        read_only_fields = ['id', 'url', 'uploaded_by', 'created_date', 'updated_date']


class IssueAttachmentCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating IssueAttachment objects.

    This serializer is used specifically for handling file uploads. The 'uploaded_by'
    field is not included here as it will be set automatically by the view.
    """

    class Meta:
        model = IssueAttachment
        fields = ['file']
