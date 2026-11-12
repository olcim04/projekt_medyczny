import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

from django.core.management import execute_from_command_line


if __name__ == '__main__':
    execute_from_command_line([sys.argv[0], 'create_clinician', *sys.argv[1:]])
