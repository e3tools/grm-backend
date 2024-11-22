#!/bin/bash

show_help() {
    echo """
    Commands
    ---------------------------------------------------------
    bash          : run bash
    eval          : eval shell command
    django        : invoke django commands
    serve         : run web server as wsgi app
    test          : run all tests
    celery-worker : start celery worker
    celery-beat   : start celery beat
  """
}

case "$1" in
  
    bash )
        bash
    ;;

    eval )
        eval "${@:2}"
    ;;

    django )
        python ./manage.py "${@:2}"
    ;;

    serve )
        # apply migrations and collect static
        echo "Applying database migrations..."
        python manage.py migrate --noinput
        echo "Collecting static files..."
        python manage.py collectstatic --noinput

        # launch Gunicorn
        echo "Starting Gunicorn server..."
        gunicorn grm.wsgi:application \
        --bind 0.0.0.0:9000 \
        --workers 4 \
        --timeout 600
    ;;

    celery-worker )
        echo "Starting Celery worker..."
        celery -A grm worker --loglevel=info
    ;;

    celery-beat )
        echo "Starting Celery beat..."
        celery -A grm beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
    ;;

    test )
        echo "Running tests..."
        pytest --cov=app --cov-report=xml
    ;;

    * )
        show_help
    ;;

esac
