#!/usr/bin/env python3
"""
git_changes

Check for changes in git for specific paths. If no changes, cancel pipeline, unless
no_cancel option has been specified.

"""
import os
import sys

sys.path.insert(0, '/home/circleci/bin')

import loggy
from common import add_bash_exports_to_env, get_environ, cancel_workflow
from git import changes_by_path

loggy.info("git_changes(): BEGIN")

#
# Every command should check and load any BASH_ENV exports set from other commands.
#
add_bash_exports_to_env()
_TRIGGER_FILES = get_environ('TRIGGER_FILES')
if not _TRIGGER_FILES:
    loggy.info("Pipeline error. TRIGGER_FILES not set on environment.")
    loggy.info("Dumping available ENV vars for debugging:")
    for key, value in os.environ.items():
        loggy.info(f"{key}={value}")
    sys.exit(1)

_NO_CANCEL = get_environ('NO_CANCEL')

if not changes_by_path(path=_TRIGGER_FILES):
    if not _NO_CANCEL:
        loggy.info("git_changes(): No changes found that match regex pattern. Cancelling workflow.")
        if not cancel_workflow():
            loggy.info(f"git_changes(): ERROR canceling workflow. Killing workflow.")
            sys.exit(1)

        #
        # The request above could take up to 5-10 seconds to actually cancel the pipeline
        # which means other steps after this might kick off. To avoid it, let's sleep 30 seconds.
        #
        import time
        time.sleep(30)

    loggy.info(f"git_changes(): Failing job to prevent requires jobs from running.")
    sys.exit(1)

sys.exit(0)