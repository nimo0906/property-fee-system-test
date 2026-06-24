#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Small form parser for desktop server uploads.

Avoids the removed stdlib cgi module so Windows builds work on Python 3.13+.
"""

from dataclasses import dataclass
from email import policy
from email.parser import BytesParser
import io
import urllib.parse


@dataclass
class FormField:
    value: object
    filename: str = ""
    type: str = ""

    def __bool__(self):
        return bool(self.value)

    @property
    def file(self):
        data = self.value if isinstance(self.value, bytes) else str(self.value or "").encode("utf-8")
        return io.BytesIO(data)


class ParsedForm:
    def __init__(self):
        self._fields = {}

    def add(self, name, value, filename="", content_type=""):
        self._fields.setdefault(name, []).append(FormField(value, filename, content_type))

    def getvalue(self, name, default=None):
        items = self._fields.get(name)
        if not items:
            return default
        return items[0].value

    def getfirst(self, name, default=None):
        return self.getvalue(name, default)

    def __getitem__(self, name):
        return self._fields[name][0]

    def __contains__(self, name):
        return name in self._fields

    def get(self, name, default=None):
        items = self._fields.get(name)
        if not items:
            return default
        return [item.value for item in items]

    def items(self):
        for name, items in self._fields.items():
            yield name, [item.value for item in items]

    def keys(self):
        return self._fields.keys()


class FormParseError(ValueError):
    pass


def parse_form_data(rfile, headers):
    content_type = headers.get("Content-Type", "")
    try:
        content_length = int(headers.get("Content-Length", "0") or 0)
    except ValueError as exc:
        raise FormParseError("invalid content length") from exc
    body = rfile.read(content_length)
    if content_type.startswith("multipart/form-data"):
        return _parse_multipart(content_type, body)
    if content_type.startswith("application/x-www-form-urlencoded"):
        return _parse_urlencoded(body)
    raise FormParseError("unsupported form content type")


def _parse_urlencoded(body):
    form = ParsedForm()
    text = body.decode("utf-8", errors="replace")
    for name, values in urllib.parse.parse_qs(text, keep_blank_values=True).items():
        for value in values:
            form.add(name, value)
    return form


def _parse_multipart(content_type, body):
    raw = (
        f"Content-Type: {content_type}\r\n"
        "MIME-Version: 1.0\r\n\r\n"
    ).encode("utf-8") + body
    message = BytesParser(policy=policy.default).parsebytes(raw)
    if not message.is_multipart():
        raise FormParseError("invalid multipart body")
    form = ParsedForm()
    for part in message.iter_parts():
        disposition = part.get("Content-Disposition", "")
        if not disposition.startswith("form-data"):
            continue
        params = dict(part.get_params(header="content-disposition") or [])
        name = params.get("name")
        if not name:
            continue
        filename = params.get("filename", "") or ""
        payload = part.get_payload(decode=True) or b""
        if filename:
            form.add(name, payload, filename, part.get_content_type())
        else:
            charset = part.get_content_charset() or "utf-8"
            form.add(name, payload.decode(charset, errors="replace"))
    return form
