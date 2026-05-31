#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Project boundary for future multi-community / multi-project support."""

from server.db import get_db


class ProjectError(Exception):
    """Project business error safe for UI/API responses."""


class ProjectService:
    def list_projects(self, include_inactive=False):
        db = get_db()
        try:
            sql = 'SELECT * FROM projects'
            params = []
            if not include_inactive:
                sql += ' WHERE is_active=1'
            sql += ' ORDER BY id'
            rows = db.execute(sql, params).fetchall()
            return {'items': [self._format(row) for row in rows]}
        finally:
            db.close()

    def default_project(self):
        db = get_db()
        try:
            row = db.execute("SELECT * FROM projects WHERE code='default' LIMIT 1").fetchone()
            if not row:
                raise ProjectError('默认项目不存在')
            return self._format(row)
        finally:
            db.close()

    def get_project(self, project_id):
        db = get_db()
        try:
            row = db.execute('SELECT * FROM projects WHERE id=?', (int(project_id),)).fetchone()
            if not row:
                raise ProjectError('项目不存在')
            return self._format(row)
        finally:
            db.close()

    def _format(self, row):
        data = dict(row)
        return {
            'id': data['id'],
            'code': data['code'],
            'name': data['name'],
            'is_active': int(data['is_active'] or 0),
            'notes': data.get('notes') or '',
            'created_at': data.get('created_at') or '',
        }
