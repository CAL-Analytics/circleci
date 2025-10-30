#!/usr/bin/env python3
"""
loggy

Common code to force logging to the console for pipelines

Example Usage:
    from utils import loggy
"""
import logging
import sys

logging.basicConfig(
    stream=sys.stdout,
    format="%(levelname)s %(asctime)s - %(message)s",
    level=logging.INFO
)
loggy = logging.getLogger()
loggy.info("loggy Initialized")


def debug(msg):
    """
    debug()

    Log a DEBUG message to stdout
    """
    loggy.debug(msg)


def info(msg):
    """
    info()

    Log an INFO message to stdout
    """
    loggy.info(msg)


def warn(msg):
    """
    warn()

    Log a WARNING message to stdout
    """
    loggy.warning(msg)


def warning(msg):
    """
    warning()

    Log a WARNING message to stdout
    """
    loggy.warning(msg)


def error(msg):
    """
    error()

    Log an ERROR message to stdout
    """
    loggy.error(msg)
