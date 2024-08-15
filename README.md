# grm-backend
## Setup Using Docker Locally
Create your Environment Variable
`cp src/grm/.env.example  src/grm/.env`

## Run Docker 
`docker compose up -d`

### Run the App Without Docker
`cd grm-backend	`
### Setup 
Activate Python environment (use python 3)
`python -m venv venv`

Activate Python Environment
`source venv/bin/activate`

Install application
`pip install -r requirements.txt`

Start Application
`python3.10 src/manage.py runserver`
