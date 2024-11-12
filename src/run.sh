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
        # Appliquer les migrations et collecter les fichiers statiques
        echo "Applying database migrations..."
        python manage.py migrate --noinput
        echo "Collecting static files..."
        python manage.py collectstatic --noinput

        # Lancer Gunicorn
        echo "Starting Gunicorn server..."
        gunicorn cdd.wsgi:application \
        --bind 0.0.0.0:9000 \
        --workers 4 \
        --timeout 600
    ;;

    test )
        echo "Running tests..."
        pytest --cov=app --cov-report=xml
    ;;

    * )
        show_help
    ;;

esac
