import pytest  # noqa
from packaging.version import LegacyVersion, parse
from packaging import version

def newest(tags):
    return max(tags, key=lambda t: LegacyVersion(t))

def is_stable(tag):
    return not version.Version(tag).is_prerelease
