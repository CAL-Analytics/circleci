print("circleci_get_artifact(): BEGIN")

# 
# Every command should check and load any BASH_ENV exports set from other commands.
#
common.add_bash_exports_to_env()

_URL = os.environ.get('URL', None)
_OUTPUT_FILE = os.environ.get('OUTPUT_FILE', f"workspace/{_URL.split('/')[-1]}")
_PIPELINE_TRIGGER_TOKEN = os.environ.get('PIPELINE_TRIGGER_TOKEN')

if not _PIPELINE_TRIGGER_TOKEN:
    print("circleci_get_artifact(): PIPELINE_TRIGGER_TOKEN ENV var required. Please ensure the proper context has been set.")
    sys.exit(1)

print(f"circleci_get_artifact(): Attempting to retrieve ({_OUTPUT_FILE}) from {_URL}")

import requests
try:
    x = requests.get(
        _URL,
        headers={"content-type": "application/json", "Circle-Token": _PIPELINE_TRIGGER_TOKEN})

    if x.status_code != 200:
        print(f"circleci_get_artifact(): Get Artifacts failed. {x.text}")
        sys.exit(1)

    with open(_OUTPUT_FILE, "w") as _ARTIFACT:
        _ARTIFACT.write(x.text)        
except Exception as e:
    print(f"circleci_get_artifact(): Get Artificats failed. {str(e)}")
    sys.exit(1)

sys.exit(0)