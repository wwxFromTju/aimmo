import django
import logging
import os
import sys
import time
from django.conf import settings
from shell_api import log, run_command, run_command_async

sys.path.append("/home/travis/build/ocadotechnology/aimmo")

try:
    if os.environ['CI'] == "true":
        ROOT_DIR_LOCATION = os.environ['TRAVIS_BUILD_DIR']
    else:
        ROOT_DIR_LOCATION = os.path.abspath(os.path.dirname((os.path.dirname(__file__))))
except KeyError:
    ROOT_DIR_LOCATION = os.path.abspath(os.path.dirname((os.path.dirname(__file__))))

_MANAGE_PY = os.path.join(ROOT_DIR_LOCATION, 'example_project', 'manage.py')
_SERVICE_PY = os.path.join(ROOT_DIR_LOCATION, 'aimmo-game-creator', 'service.py')
_FRONTEND_BUNDLER_JS = os.path.join(ROOT_DIR_LOCATION, 'game_frontend', 'djangoBundler.js')

PROCESSES = []


def create_superuser_if_missing(username, password):
    django.setup()

    from django.contrib.auth.models import User

    user = User.objects.filter(username=username)

    if not user.exists():
        print('Creating user 342')
        User.objects.create_superuser(username=username, email='admin@admin.com',
                                      password=password)
    else:
        assert(user.first().is_superuser)
        print('User made 342')
        user.first().refresh_from_db()
        print('Username: ' + user.first().username)
        print('Email: ' + user.first().email)
        print('Password: ' + user.first().password)

    user = User.objects.filter(username=username).first()
    with open('hashes.txt', 'a') as fp:
        fp.write(user.password + '\n')


def run(use_minikube, server_wait=True, capture_output=False, test_env=False):
    logging.basicConfig()
    if test_env:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "test_settings")
    else:
        sys.path.append(os.path.join(ROOT_DIR_LOCATION, 'example_project'))
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "example_project.settings")

    run_command(['pip', 'install', '-e', ROOT_DIR_LOCATION], capture_output=capture_output)

    if not test_env:
        run_command(['python', _MANAGE_PY, 'migrate', '--noinput'], capture_output=capture_output)
        run_command(['python', _MANAGE_PY, 'collectstatic', '--noinput'], capture_output=capture_output)

    create_superuser_if_missing(username='admin', password='admin')

    server_args = []
    if use_minikube:
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sys.path.append(os.path.join(parent_dir, 'aimmo_runner'))

        os.chdir(ROOT_DIR_LOCATION)
        run_command(['pip', 'install', '-r', os.path.join(ROOT_DIR_LOCATION, 'minikube_requirements.txt')],
                    capture_output=capture_output)

        # Import minikube here, so we can install the dependencies first
        from aimmo_runner import minikube
        minikube.start()

        server_args.append('0.0.0.0:8000')
        os.environ['AIMMO_MODE'] = 'minikube'
    else:
        time.sleep(2)
        game = run_command_async(['python', _SERVICE_PY, '127.0.0.1', '5000'], capture_output=capture_output)
        PROCESSES.append(game)
        os.environ['AIMMO_MODE'] = 'threads'

    os.environ['NODE_ENV'] = 'development' if settings.DEBUG else 'production'
    server = run_command_async(['python', _MANAGE_PY, 'runserver'] + server_args, capture_output=capture_output)
    frontend_bundler = run_command_async(['node', _FRONTEND_BUNDLER_JS], capture_output=capture_output)
    PROCESSES.append(server)
    PROCESSES.append(frontend_bundler)

    if server_wait is True:
        try:
            game.wait()
        except NameError:
            pass

        server.wait()

    return PROCESSES
