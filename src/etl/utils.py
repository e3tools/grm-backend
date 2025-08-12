import logging

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.dateparse import parse_datetime

from authentication.models import User
from issues.models import AdministrativeLevel, IssueDepartmentAdministrativeLevel

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
        AdministrativeLevel.objects.bulk_create(missing_levels, ignore_conflicts=True)
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
    existing_users = User.objects.all().values('id', 'first_name', 'last_name')

    # Create the missing ones in a single bulk_create
    missing_users = []
    for user_id, name in user_data.items():
        if user_id not in existing_users:
            name_data = name.split(' ')
            last_name = ''
            if len(name_data) > 1:
                last_name = name_data[1]
            missing_users.append(User(id=user_id, first_name=name_data[0], last_name=last_name))

    if missing_users:
        User.objects.bulk_create(missing_users, ignore_conflicts=True)

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
    processed = []
    for item in data:
        new_item = item.copy()

        # --- Handle intake_date ---
        intake_date = new_item.get('intake_date')
        if isinstance(intake_date, str) and 'T' in intake_date and 'Z' in intake_date:
            parsed = parse_datetime(intake_date)
            if parsed:
                new_item['intake_date'] = parsed

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


def bulk_create_or_update(model_class, data_list: list[dict], batch_size: int = 500) -> dict[str, int]:
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

    Returns:
        dict: Summary of the operation:
            {
                'total_created': X,
                'total_updated': Y,
                'total_processed': X + Y
            }

    Raises:
        ValidationError: If model validation fails for individual objects
                         (logged as warnings, processing continues)
        Exception: Database errors or other unexpected errors during batch processing
                   (logged as errors, processing continues with next batch)

    Performance Notes:
        - Uses separate bulk_create and bulk_update for optimal performance and clarity
        - Processes data in batches to avoid memory issues with large datasets
        - Each batch is wrapped in a database transaction for consistency
        - Failed batches don't affect other batches (error isolation)
        - Updates only fields that exist on the model (ignores extra dict keys)

    Database Operations per Batch:
        - 1 bulk_create operation for new objects
        - 1 bulk_update operation for existing objects
        - Significantly faster than individual save() or update_or_create() calls
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
                        # Validate the object according to model constraints except for unique fields
                        obj.full_clean(validate_unique=False)

                        if obj.id in existing_ids:
                            objects_to_update.append(obj)
                        else:
                            objects_to_create.append(obj)
                    except ValidationError as e:
                        # Log validation errors but continue processing other objects
                        logger.warning(f"Validation error: {e}")
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
            logger.error(f"Error in batch {i // batch_size + 1}: {e}")

    return {
        'total_created': total_created,
        'total_updated': total_updated,
        'total_processed': total_created + total_updated,
    }
