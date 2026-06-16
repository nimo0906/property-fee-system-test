#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Application version and update source configuration."""

import os

APP_VERSION = '2.0.4'
APP_BUILD = '2026.06.15'
DEFAULT_UPDATE_MANIFEST_URL = os.environ.get(
    'PM_UPDATE_MANIFEST_URL',
    'https://github.com/nimo0906/property-fee-system-test/releases/download/internal-latest/update_manifest.json',
)
