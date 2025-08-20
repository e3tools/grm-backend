import logging

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.dateparse import parse_datetime

from authentication.models import User
from issues.models import (
    AdministrativeLevel,
    Citizen,
    IssueDepartmentAdministrativeLevel,
)

logger = logging.getLogger(__name__)


def process_administrative_region_data(data: list[dict]) -> list[dict]:
    """
    Process and normalize region data for database insertion or further processing.

    This function performs the following transformations on a list of dictionaries:
      1. Increments all numeric values of 'administrative_id' and 'parent_id' by 1.
      2. Replaces any 'administrative_id' or 'parent_id' equal to 'country' with the integer 1.
      3. Renames the 'administrative_id' key to 'id'.

    Args:
        data (list[dict]):
            A list of dictionaries, each representing a region with at least the keys:
            - 'administrative_id'
            - 'parent_id'
          Additional keys (e.g., 'name', 'latitude', 'longitude') are preserved.

    Returns:
        list[dict]:
            A new list of dictionaries with processed values.

    Behavior Details:
        - Numeric values in 'administrative_id' and 'parent_id' are incremented by +1.
        - Strings that can’t be converted to integers remain unchanged unless they are 'country'.
        - 'country' values for either field are set to 1.
        - The key 'administrative_id' is renamed to 'id'.
        - Items with non-numeric IDs are ordered after those with numeric IDs.

    Example:
        >>> data = [
        ...   {'id': '3', 'name': 'GOGOUNOU', 'parent_id': '1', ...},
        ...   {'id': 'country', 'name': 'PARAKOU', 'parent_id': '3', ...}
        ... ]
        >>> process_administrative_region_data(data)
        [
          {'id': '4', 'name': 'GOGOUNOU', 'parent_id': '2', ...},
          {'id': '1', 'name': 'PARAKOU', 'parent_id': '4', ...}
        ]
    """
    # Get all unique administrative level names
    admin_level_names = {item.get('administrative_level') for item in data if item.get('administrative_level')}

    # Load existing levels into a dictionary {name: id}
    existing_levels = dict(AdministrativeLevel.objects.values_list('name', 'id'))

    # Create the missing ones in a single bulk_create
    missing_levels = [AdministrativeLevel(name=name) for name in admin_level_names if name not in existing_levels]
    if missing_levels:
        AdministrativeLevel.objects.bulk_create(missing_levels)
        # Reload all to get the IDs
        existing_levels = dict(AdministrativeLevel.objects.filter(name__in=admin_level_names).values_list('name', 'id'))

    processed = []
    for item in data:
        new_item = item.copy()

        # --- Handle administrative_id ---
        administrative_id = new_item.get('administrative_id')
        if isinstance(administrative_id, str) and administrative_id.isdigit():
            new_item['administrative_id'] = int(administrative_id) + 1
        elif administrative_id == 'country':
            new_item['administrative_id'] = 1

        # --- Handle parent_id ---
        parent = new_item.get('parent_id')
        if isinstance(parent, str) and parent.isdigit():
            new_item['parent_id'] = int(parent) + 1
        elif parent == 'country':
            new_item['parent_id'] = 1

        # --- Handle administrative_level ---
        name = new_item.pop('administrative_level', None)
        if name:
            new_item['administrative_level_id'] = existing_levels.get(name)

        # --- Rename administrative_id → id ---
        new_item['id'] = new_item.pop('administrative_id')

        processed.append(new_item)

    return processed


def process_issue_department_data(data: list[dict]) -> list[dict]:
    # Get all unique user ids
    user_ids = set()
    user_data = {}

    for item in data:
        if item.get('head'):
            user_id = int(item.get('head').get('id'))
            user_ids |= {user_id}
            user_data[user_id] = item.get('head').get('name')

    # Load existing users
    existing_users = list(User.objects.values_list('id', flat=True))

    # Create the missing ones in a single bulk_create
    missing_users = []
    for user_id, name in user_data.items():
        if int(user_id) not in existing_users:
            name_data = name.split(' ') if name else ['']
            last_name = ''
            if len(name_data) > 1:
                last_name = name_data[1]
            missing_users.append(
                User(
                    id=user_id,
                    first_name=name_data[0],
                    last_name=last_name,
                    username=user_id,
                    email=f"{user_id}@fake.email",
                )
            )

    if missing_users:
        User.objects.bulk_create(missing_users)

        user_data = {}

        for item in data:
            if item.get('head'):
                user_id = int(item.get('head').get('id'))
                user_ids |= {user_id}
                user_data[user_id] = item.get('head').get('name')

    processed = []
    for item in data:
        new_item = item.copy()

        # --- Handle head ---
        head = new_item.pop('head', None)
        if head:
            new_item['head_id'] = head['id']

        processed.append(new_item)

    return processed


def process_issue_data(data: list[dict]) -> list[dict]:
    # Load users into a dictionary {external_id: id}
    external_users = dict(User.objects.exclude(external_id=None).values_list('external_id', 'id'))
    all_users = list(User.objects.values_list('id', flat=True))

    def datetime_field_process(item_dict, name):
        field_data = item_dict.get(name)
        if isinstance(field_data, str) and 'T' in field_data and 'Z' in field_data:
            parsed = parse_datetime(field_data)
            if parsed:
                item_dict[name] = parsed
        else:
            item_dict[name] = None

    def user_field_process(item_dict, name):
        field_data = item_dict.get(name)
        if field_data and field_data.get('id'):
            user_id = field_data.get('id')
            if str(user_id).isdigit():
                user_id = int(user_id)
                if user_id not in all_users:
                    name_data = field_data.get('name').split(' ') if field_data.get('name') else ['']
                    last_name = None
                    if len(name_data) > 1:
                        last_name = name_data[1]
                    User.objects.create(
                        id=user_id,
                        first_name=name_data[0],
                        last_name=last_name,
                        username=user_id,
                        email=f"{user_id}@fake.email",
                    )
                    all_users.append(user_id)
            else:
                if user_id in external_users.keys():
                    user_id = external_users[user_id]
                else:
                    new_user = User.objects.create(
                        username=user_id, email=f"{user_id[-5:]}@fake.email", external_id=user_id
                    )
                    external_users[user_id] = new_user.id
                    user_id = new_user.id

            item_dict[f'{name}_id'] = user_id
            item_dict.pop(name)

    processed = []
    for item in data:
        new_item = item.copy()

        # --- Handle status ---
        status = new_item.get('status')
        if status and status.get('id'):
            new_item['status_id'] = int(status.get('id'))
            new_item.pop("status")

        # --- Handle category ---
        category = new_item.get('category')
        if category and category.get('id'):
            new_item['category_id'] = int(category.get('id'))
            new_item.pop("category")

        # --- Handle issue_type ---
        issue_type = new_item.get('issue_type')
        if issue_type and issue_type.get('id'):
            new_item['issue_type_id'] = int(issue_type.get('id'))
            new_item.pop("issue_type")

        # --- Handle administrative_region ---
        administrative_region = new_item.get('administrative_region')
        if administrative_region and administrative_region.get('administrative_id'):
            administrative_id = administrative_region.get('administrative_id')
            if isinstance(administrative_id, str) and administrative_id.isdigit():
                new_item['administrative_region_id'] = int(administrative_id) + 1
            elif administrative_id == 'country':
                new_item['administrative_region_id'] = 1
            new_item.pop("administrative_region")

        # --- Handle intake_date ---
        datetime_field_process(new_item, 'intake_date')

        # --- Handle reporter ---
        user_field_process(new_item, 'reporter')

        # --- Handle assignee ---
        user_field_process(new_item, 'assignee')

        # --- Handle citizen fields ---
        citizen_name = new_item.get('citizen')
        if citizen_name:
            citizen_type = new_item.get('citizen_type')
            citizen_age_group = new_item.get('citizen_age_group')
            citizen_age_group = citizen_age_group.get('id') if citizen_age_group else None
            citizen_group = new_item.get('citizen_group')
            citizen_group = citizen_group.get('id') if citizen_group else None
            citizen_group_2 = new_item.get('citizen_group')
            citizen_group_2 = citizen_group_2.get('id') if citizen_group_2 else None
            citizen, _ = Citizen.objects.get_or_create(
                name=citizen_name,
                type=citizen_type,
                age_group_id=citizen_age_group,
                group_id=citizen_group,
                group_2_id=citizen_group_2,
            )
            new_item['citizen_id'] = citizen.id
        if "citizen" in new_item:
            new_item.pop("citizen")

        # --- Handle location_info ---
        location_info = new_item.get('location_info')
        if location_info:
            issue_location = location_info.get('issue_location')
            administrative_id = issue_location.get('administrative_id')
            if isinstance(administrative_id, str) and administrative_id.isdigit():
                new_item['issue_location_id'] = int(administrative_id) + 1
            elif administrative_id == 'country':
                new_item['issue_location_id'] = 1
            new_item['location_description'] = location_info.get('location_description')

        # --- Handle component ---
        component = new_item.get('component')
        if component and component.get('id'):
            new_item['component_id'] = component.get('id')
            new_item.pop("component")

        # --- Handle sub_component ---
        component = new_item.get('sub_component')
        if component and component.get('id'):
            new_item['sub_component_id'] = component.get('id')
            new_item.pop("sub_component")

        # --- Handle issue_sub_type ---
        issue_sub_type = new_item.get('issue_sub_type')
        if issue_sub_type and issue_sub_type.get('id'):
            new_item['issue_sub_type_id'] = issue_sub_type.get('id')
            new_item.pop("issue_sub_type")

        # --- Handle created_date ---
        datetime_field_process(new_item, 'created_date')

        # --- Handle resolution_date ---
        datetime_field_process(new_item, 'resolution_date')

        # --- Handle contact_information ---
        contact_information = new_item.get('contact_information')
        if contact_information:
            new_item['contact_information'] = contact_information.get('contact')
            new_item['contact_method'] = contact_information.get('type')

        # --- Rename auto_increment_id → id ---
        new_item['id'] = new_item.pop('auto_increment_id')

        processed.append(new_item)

    return processed


def process_category_data(data: list[dict]) -> list[dict]:
    # Get all unique department level relation ids
    department_level_relations = set()

    for item in data:
        for field in ('assigned_department', 'assigned_appeal_department', 'assigned_escalation_department'):
            department = item.get(field)['id']
            level = item.get(field)['administrative_level']
            department_level_relations |= {(department, level)}

    # Load existing department level relations into a dictionary
    existing_department_levels = {}
    for item in IssueDepartmentAdministrativeLevel.objects.select_related('administrative_level'):
        existing_department_levels[f'{item.department}{item.administrative_level.name}'] = item.id

    # Load existing administrative levels {name: id}
    existing_levels = dict(AdministrativeLevel.objects.values_list('name', 'id'))

    # Create the missing ones in a single bulk_create
    missing_department_levels = []
    for item in department_level_relations:
        if item not in existing_department_levels:
            missing_department_levels.append(
                IssueDepartmentAdministrativeLevel(
                    department_id=item[0], administrative_level_id=existing_levels[item[1]]
                )
            )

    if missing_department_levels:
        IssueDepartmentAdministrativeLevel.objects.bulk_create(missing_department_levels, ignore_conflicts=True)
        # Reload all to get the IDs
        for item in IssueDepartmentAdministrativeLevel.objects.select_related('administrative_level'):
            existing_department_levels[f'{item.department}{item.administrative_level.name}'] = item.id

    processed = []
    for item in data:
        new_item = item.copy()

        for field in ('assigned_department', 'assigned_appeal_department', 'assigned_escalation_department'):
            # --- Handle field ---
            field_data = new_item.pop(field, None)
            new_item[f'{field}_id'] = existing_department_levels.get(
                f"{field_data['name']}{field_data['administrative_level']}"
            )

        processed.append(new_item)

    return processed


def bulk_create_or_update(
    model_class, data_list: list[dict], batch_size: int = 500, validate: bool = True
) -> dict[str, int]:
    """
    Efficiently create or update model instances using bulk operations.

    This function performs upsert operations (insert or update) on Django model instances
    by splitting the process into two steps per batch:
        1. Create new objects with bulk_create
        2. Update existing objects with bulk_update

    Extra keys in each `data_dict` that do not correspond to fields on `model_class`
    are ignored automatically.

    The function assumes all objects in `data_list` have an 'id' field.
    If an object with the given ID already exists in the database, its fields will be updated.
    If the ID doesn't exist, a new object will be created.

    Requirements:
        - Django 4.2+ (for bulk_update improvements)
        - All dictionaries in `data_list` must contain an 'id' key
        - The model must have an 'id' field as the unique identifier

    Args:
        model_class: The Django model class to perform upsert operations on.
                    Must be a subclass of django.db.models.Model.
        data_list: List of dictionaries containing the data for each object.
                   Each dictionary must include an 'id' key and can contain
                   any other fields that exist on the model.
        batch_size: Number of objects to process in each database operation.
                    Defaults to 500. Larger batches are more efficient but use
                    more memory. Should not exceed database-specific limits.
        validate: Boolean flag to control model validation. Defaults to True.
                 When True, performs full_clean() validation on each object
                 before bulk operations (excludes unique field validation).
                 When False, skips validation for better performance but
                 may allow invalid data to be stored in the database.

    Returns:
        dict: Summary of the operation:
            {
                'total_created': X,
                'total_updated': Y,
                'total_processed': X + Y
            }

    Raises:
        ValidationError: If model validation fails for individual objects
                         (logged as warnings, processing continues).
                         Only raised when validate=True.
        Exception: Database errors or other unexpected errors during batch processing
                   (logged as errors, processing continues with next batch)

    Performance Notes:
        - Uses separate bulk_create and bulk_update for optimal performance and clarity
        - Processes data in batches to avoid memory issues with large datasets
        - Each batch is wrapped in a database transaction for consistency
        - Failed batches don't affect other batches (error isolation)
        - Updates only fields that exist on the model (ignores extra dict keys)
        - Setting validate=False improves performance by skipping model validation
        - Validation skipping is useful for trusted data sources or when validation
          has already been performed elsewhere

    Database Operations per Batch:
        - 1 bulk_create operation for new objects
        - 1 bulk_update operation for existing objects
        - Significantly faster than individual save() or update_or_create() calls

    Validation Behavior:
        - When validate=True (default): Performs full_clean(validate_unique=False)
          on each object, ensuring model field constraints are respected
        - When validate=False: Skips validation entirely, allowing faster processing
          but potentially permitting invalid data
    """
    total_created = 0
    total_updated = 0

    # Get all model fields except 'id' for update operations (ignore reverse relations & M2M for bulk_create)
    model_fields = {
        attr for f in model_class._meta.get_fields() if hasattr(f, 'attname') for attr in (f.name, f.attname)
    }
    update_fields = [f for f in model_fields if f != 'id']

    # Process data in batches to optimize memory usage and database performance
    for i in range(0, len(data_list), batch_size):
        batch = data_list[i : i + batch_size]

        try:
            # Use atomic transaction to ensure batch consistency
            with transaction.atomic():
                objects_to_create = []
                objects_to_update = []

                # Get all IDs in the current batch
                batch_ids = [int(item['id']) for item in batch if 'id' in item]

                # Query existing IDs in DB
                existing_ids = set(model_class.objects.filter(id__in=batch_ids).values_list('id', flat=True))

                # Validate and prepare objects for bulk operation
                for data_dict in batch:
                    try:
                        # Filter only fields that exist in the model
                        filtered_data = {k: v for k, v in data_dict.items() if k in model_fields}
                        # Create model instance from dictionary data
                        obj = model_class(**filtered_data)

                        # Perform validation only if validate parameter is True
                        if validate:
                            # Validate the object according to model constraints except for unique fields
                            obj.full_clean(validate_unique=False)

                        if obj.id in existing_ids:
                            objects_to_update.append(obj)
                        else:
                            objects_to_create.append(obj)
                    except ValidationError as e:
                        # Log validation errors but continue processing other objects
                        # This exception only occurs when validate=True
                        logger.warning(
                            f"Validation error: {e}. Document {data_dict['type']} with _id {data_dict['_id']}"
                        )
                        continue

                # Bulk insert new records
                if objects_to_create:
                    model_class.objects.bulk_create(objects_to_create, batch_size=batch_size)
                    total_created += len(objects_to_create)

                # Bulk update existing records
                if objects_to_update:
                    model_class.objects.bulk_update(objects_to_update, update_fields, batch_size=batch_size)
                    total_updated += len(objects_to_update)

        except Exception as e:
            # Log batch errors but continue with next batch
            logger.error(
                f"Error in batch {i // batch_size + 1}: {e}. "
                f"Document {data_dict['type']} with _id {data_dict['_id']}"
            )

    return {
        'total_created': total_created,
        'total_updated': total_updated,
        'total_processed': total_created + total_updated,
    }


def process_adl_data(data: list[dict]) -> list[dict]:
    processed = []
    for item in data:
        new_item = item.copy()

        # --- Handle external_id ---
        new_item['external_id'] = new_item.get('_id')

        representative_data = new_item.get('representative')

        # --- Handle id ---
        new_item['id'] = representative_data.get('id')

        # --- Handle first_name and last_name ---
        name_data = representative_data.get('name').split(' ') if representative_data.get('name') else ['']
        new_item['first_name'] = name_data[0]
        if len(name_data) > 1:
            new_item['last_name'] = name_data[1]

        # --- Handle username and email ---
        email = representative_data.get('email')
        new_item['username'] = email
        new_item['email'] = email

        # --- Handle phone_number ---
        new_item['phone_number'] = representative_data.get('phone')

        # --- Handle is_active ---
        new_item['is_active'] = representative_data.get('is_active')

        # --- Handle password ---
        new_item['password'] = representative_data.get('password')

        processed.append(new_item)

    return processed


def process_citizen_group_data(data: list[dict]) -> list[dict]:

    processed = []
    for item in data:
        new_item = item.copy()

        # --- Handle type ---
        new_item['type'] = 'citizen_group'

        processed.append(new_item)

    return processed
