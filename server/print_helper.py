#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared print/export helpers — self-contained HTML with inline CSS, no CDN dependency.

Usage:
    from server.print_helper import print_page, PRINT_CSS
    html = print_page("标题", "内容", show_back=True)
"""
import html

PRINT_CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: "SimSun", "STSong", "PingFang SC", serif;
       font-size: 12pt; color: #222; background: #fff; padding: 20pt; max-width: 210mm; margin: auto; }
@media print { @page { margin: 1.5cm; } body { padding: 0; } .no-print { display: none !important; } }
.print-toolbar { text-align: center; margin-bottom: 10pt; padding: 8pt; border: 1px solid #ddd; background: #fafafa; }
.print-toolbar-tip { font-size: 9pt; color: #555; margin-bottom: 6pt; }
@media print { .print-toolbar { display: none !important; } }
h1 { text-align: center; font-size: 18pt; margin-bottom: 6pt; letter-spacing: 4pt; }
h2 { text-align: center; font-size: 14pt; margin-bottom: 16pt; color: #333; }
.header-info { width: 100%; margin-bottom: 14pt; font-size: 10pt; }
.header-info td { padding: 2pt 6pt; }
table.detail { width: 100%; border-collapse: collapse; margin: 10pt 0; font-size: 10pt; }
table.detail th { background: #f0f0f0; border: 1px solid #333; padding: 5pt 6pt; text-align: center; font-weight: bold; }
table.detail td { border: 1px solid #333; padding: 4pt 6pt; text-align: center; }
table.detail .amt { text-align: right; }
.total-row { font-weight: bold; background: #f8f8f8; }
.amount-box { border: 2px solid #333; padding: 12pt; margin: 12pt 0; text-align: center; }
.amount-box .label { font-size: 10pt; color: #555; }
.amount-box .number { font-size: 24pt; font-weight: bold; letter-spacing: 2pt; }
.signature { width: 100%; margin-top: 28pt; font-size: 10pt; }
.signature td { text-align: center; padding-top: 24pt; border-top: 1px solid #999; }
.footer { text-align: center; margin-top: 16pt; font-size: 9pt; color: #888; }
.page-break { page-break-after: always; }
"""


def print_page(title, content, show_back=True, back_url='/'):
    """Generate a self-contained print-friendly HTML page."""
    back_btn = ''
    if show_back:
        safe_back_url = html.escape(back_url, quote=True)
        back_btn = f'''
        <div class="print-toolbar">
            <div class="print-toolbar-tip"><strong>保存为PDF：</strong>点击打印后，在打印对话框中选择“保存为 PDF”。</div>
            <button onclick="window.print()" style="padding:6pt 18pt;font-size:11pt;cursor:pointer;margin-right:6pt">
                🖨️ 打印
            </button>
            <a href="{safe_back_url}" style="padding:6pt 18pt;font-size:11pt;border:1px solid #999;text-decoration:none;color:#222;margin-left:6pt">← 返回</a>
        </div>'''
    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>{title}</title>
<style>{PRINT_CSS}</style>
</head>
<body>
{back_btn}
{content}
<div class="footer">物业管理收费系统 · 打印时间：{__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
</body></html>'''


def print_header_row(label, value):
    """Generate a header-info table row."""
    return f'<tr><td style="width:30%"><strong>{label}</strong></td><td style="width:20%">{value}</td></tr>'
