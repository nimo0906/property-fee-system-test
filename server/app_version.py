#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Application version and update source configuration."""

import os

APP_VERSION = '2.0.2'
APP_BUILD = '2026.06.01'
DEFAULT_UPDATE_MANIFEST_URL = os.environ.get(
    'PM_UPDATE_MANIFEST_URL',
    'https://raw.githubusercontent.com/nimo0906/property-fee-system-test/main/update_manifest.json',
)
