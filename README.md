# grm-backend
Run the App
`cd grm-backend	`
## Setup 
Activate Python environment
`python3.10 -m venv venv`

Activate Python Environment
`source venv/bin/activate`

Install application
`pip install -r requirements.txt`

Start Application
`python3.10 src/manage.py runserver`


## Key functions

### Run Manual CELERY Jobs
Run `python3.10 src/manage.py shell`
Run `from dashboard.tasks import check_issues`
Run `check_issues()`
### Create Administrative levels in CouchDB
Run `python3.10 src/manage.py shell`
Run `from grm.utils import create_facilitators_per_administrative_level`
Run `create_facilitators_per_administrative_level()`

### Create Goverment Workers
Run `python3.10 src/manage.py shell`
Run `from authentication.utils import create_government_workers`
Run `create_government_workers()`


### Download full list of App User with Activation Code
Ru  `python3.10 src/manage.py shell`
Run `from authentication.utils import get_facilitators_with_code`
RUn `get_facilitators_with_code()`