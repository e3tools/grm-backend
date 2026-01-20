# Requirements Cleanup Summary

## Overview
This document summarizes the cleanup of `requirements.txt` and identifies packages that are not directly needed in the production environment.

## Packages Removed (Not Found in Codebase)

### 1. **beautifulsoup4==4.11.1** and **soupsieve==2.1**
   - **Status**: NOT USED
   - **Reason**: No imports or usage found for HTML parsing
   - **Action**: REMOVED

### 2. **pandas==2.2.0**
   - **Status**: NOT USED
   - **Reason**: Only `openpyxl` is used for Excel file processing, not pandas
   - **Action**: REMOVED

### 3. **python-crontab==3.2.0**
   - **Status**: NOT USED
   - **Reason**: Celery beat scheduler is used instead (django_celery_beat)
   - **Action**: REMOVED

### 4. **cron-descriptor==1.4.5**
   - **Status**: NOT USED
   - **Reason**: No usage found for cron expression parsing
   - **Action**: REMOVED

### 5. **pycryptodomex==3.15.0**
   - **Status**: NOT USED
   - **Reason**: The project uses `cryptocode` for encryption, not pycryptodomex
   - **Action**: REMOVED

### 6. **PyJWT==2.3.0**
   - **Status**: NOT USED
   - **Reason**: Django REST Framework's TokenAuthentication is used instead of JWT
   - **Action**: REMOVED

### 7. **gevent==24.10.3** and **greenlet==3.1.1**
   - **Status**: NOT USED
   - **Reason**: Gunicorn is used in default mode, not with gevent workers
   - **Action**: REMOVED

### 8. **mccabe==0.6.1**, **pycodestyle==2.6.0**, **pyflakes==2.2.0**
   - **Status**: DEVELOPMENT DEPENDENCIES
   - **Reason**: These are sub-dependencies of flake8 (which is also a dev tool)
   - **Note**: flake8 is commented out in clean requirements as it should be in dev requirements

## Development Dependencies (Should be in requirements.dev.txt)

The following packages are development/testing tools and should ideally be in `requirements.dev.txt`:

- **flake8==3.8.4** - Code linting
- **pre-commit==2.9.3** - Git pre-commit hooks
- **pytest==8.4.1** - Testing framework
- **pytest-django==4.1.0** - Django testing plugin
- **factory-boy==3.2.0** - Test fixtures
- **Faker==5.4.0** - Fake data generation
- **parameterized==0.8.1** - Parameterized tests

**Note**: In the clean requirements file, I've included pytest-related packages but commented out flake8 and pre-commit as they are clearly dev-only tools.

## Packages Kept (Used in Codebase)

### Core Framework
- Django and Django extensions (confirmed in settings.py and imports)
- Django REST Framework (used for API views)
- drf-yasg (used for API documentation)

### Task Queue
- Celery and all its dependencies (celery, amqp, billiard, kombu, vine)

### Database
- psycopg2-binary (PostgreSQL adapter)
- dj-database-url (database URL parsing)

### Services
- **cloudant** - Used in `client.py` for CouchDB connections
- **twilio** - Used in `sms_client.py` for SMS sending
- **openpyxl** - Used in `wizard/utils.py` and `dashboard/other_utils.py` for Excel processing
- **cryptocode** - Used in `issues/models.py` and `grm/tasks.py` for encryption
- **shortuuid** - Used in authentication and issues models
- **pinecone** - Used in `common/utils/pinecone_connector.py`
- **sentence-transformers** - Used in `common/utils/embeddings.py`

### Web Server
- **gunicorn** - Used in `run.sh` for serving the application

### Image Processing
- **pillow** - Required by Django for ImageField usage in models

## Statistics

- **Original packages**: 94
- **Clean packages**: ~78 (including transitive dependencies)
- **Directly removed**: 8 packages
- **Moved to dev (recommended)**: 2 packages

## Recommendations

1. **Separate Dev Dependencies**: Consider moving pytest, factory-boy, Faker, and parameterized to `requirements.dev.txt`

2. **Review Transitive Dependencies**: Some packages in the clean file are transitive dependencies (automatically installed by other packages). You could further optimize by running:
   ```bash
   pip freeze > requirements_current.txt
   ```
   And comparing dependencies.

3. **Test After Cleanup**: Before deploying, ensure all functionality works:
   ```bash
   pip install -r requirements_clean.txt
   pytest  # Run all tests
   python manage.py check  # Django system check
   ```

4. **Consider pip-tools**: Use `pip-compile` from `pip-tools` to manage dependencies more efficiently and track transitive dependencies automatically.

