'''
SPDX-License-Identifier: Apache-2.0
Copyright 2021 Red Hat, Inc
'''
import re
import math

from packaging import version

CURRENT_VERSION = "2.0"
VERSIONS = [
    "1.0",
    "2.0"
]
LATEST_VERSIONS = {
    "1": "1.0",
    "2": "2.0"
}

MINIMUM_VERSION = "1.0"

def current_version():
    return CURRENT_VERSION

def latest_minor_version(v):
    v_obj = version.parse(str(v))
    if not isinstance(v_obj, version.Version):
        return '0'
    major_v = str(v_obj.major)
    if major_v in LATEST_VERSIONS:
        return LATEST_VERSIONS[major_v]

    return '0'

def all_versions():
    return VERSIONS.copy()

def is_supported_version(v):
    v_obj = version.parse(str(v))
    next_major = math.floor(float(CURRENT_VERSION)) + 1
    try:
        float(str(v_obj))
    except:
        return False
    return float(MINIMUM_VERSION) <= float(str(v_obj)) < next_major

def normalize_version(v):
    v = str(v)
    v = v.strip('/')
    base_version = version.parse(v).base_version
    # if the base version is a single number, get the latest minor version
    if not "." in base_version:
        latest_minor = latest_minor_version(base_version)
        if latest_minor != '0':
            return latest_minor
    return base_version

def major(v):
    return version.parse(str(v)).major

def minor(v):
    return version.parse(str(v)).minor

def log_api_versions(logger):
    logger.info('Current API version %s', CURRENT_VERSION)
    versions = all_versions()
    versions.remove(CURRENT_VERSION)
    if versions:
        logger.info('Supported older API versions: ' + ", ".join(versions))


def validate_version(v: str) -> bool:
    pattern = re.compile(r"\d.\d")
    return re.fullmatch(pattern, v) is not None
