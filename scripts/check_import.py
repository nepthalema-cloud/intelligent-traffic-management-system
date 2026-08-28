import sys
import importlib
import os

print('CWD:', os.getcwd())
print('PYTHONPATH env:', os.environ.get('PYTHONPATH'))
print('sys.path[0]:', sys.path[0])
print('\n'.join(sys.path))
print('\nimportlib.util.find_spec("config") ->', importlib.util.find_spec('config'))
