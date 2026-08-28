import sys, importlib.util, os
print('CWD:', os.getcwd())
print('sys.path[0]:', sys.path[0])
print('PYTHONPATH:', os.environ.get('PYTHONPATH'))
print("find_spec('config'):", importlib.util.find_spec('config'))
