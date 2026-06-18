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
.receipt-mode-switch { margin: 6pt 0; font-size: 10pt; }
.receipt-mode-switch button { padding: 5pt 10pt; margin: 0 3pt; border: 1px solid #999; background: #fff; cursor: pointer; }
.receipt-mode-switch button.active { background: #222; color: #fff; border-color: #222; }
.receipt-mode-note { font-size: 9pt; color: #555; margin-bottom: 6pt; }
.receipt-print-marker { margin: 0 0 10pt; padding: 7pt 9pt; border: 1px solid #111; background: #fff; color: #000; font-size: 10pt; text-align: center; font-weight: bold; }
@media print { .print-toolbar, .receipt-print-marker { display: none !important; } }
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
body.receipt-print { max-width: 210mm; padding: 12mm; color: #000; }
body.receipt-print.receipt-paper { max-width: 241mm; padding: 6mm; }
body.receipt-print h1 { font-size: 16pt; margin-bottom: 4pt; letter-spacing: 2pt; }
body.receipt-print h2 { font-size: 13pt; margin-bottom: 8pt; color: #000; }
body.receipt-print .header-info { margin-bottom: 7pt; font-size: 10.5pt; color: #000; }
body.receipt-print .header-info td { padding: 1.5pt 4pt; }
body.receipt-print table.detail { margin: 6pt 0; font-size: 10.5pt; color: #000; }
body.receipt-print table.detail th { background: #fff; border: 1.4pt solid #000; padding: 4pt 4pt; }
body.receipt-print table.detail td { border: 1.4pt solid #000; padding: 3.5pt 4pt; }
body.receipt-print .total-row { background: #fff; }
body.receipt-print .signature { margin-top: 16pt; font-size: 10.5pt; }
body.receipt-print .signature td { border-top: 1.2pt solid #000; padding-top: 14pt; }
body.receipt-print .footer { color: #000; font-size: 8pt; margin-top: 8pt; }
@media print {
  body.receipt-print { max-width: none; padding: 0; print-color-adjust: exact; -webkit-print-color-adjust: exact; }
  body.receipt-print.receipt-paper { width: 229mm; page: receipt; }
  @page receipt { size: 241mm 140mm; margin: 5mm 6mm; }
}
"""


def _receipt_mode_controls():
    return '''
            <div class="receipt-mode-switch" data-receipt-mode-switch>
                <strong>收据打印模式：</strong>
                <button type="button" data-mode="a4" onclick="setReceiptPrintMode('a4')">普通A4</button>
                <button type="button" data-mode="paper" onclick="setReceiptPrintMode('paper')">收据纸</button>
            </div>
            <div class="receipt-mode-note" id="receiptModeNote">普通A4：不锁定纸张尺寸，可在系统打印框选择纵向或横向。</div>'''


def _receipt_mode_script():
    return '''
<script>
function setReceiptPrintMode(mode) {
  var body = document.body;
  var note = document.getElementById('receiptModeNote');
  body.classList.toggle('receipt-a4', mode === 'a4');
  body.classList.toggle('receipt-paper', mode === 'paper');
  document.querySelectorAll('[data-receipt-mode-switch] button').forEach(function (btn) {
    btn.classList.toggle('active', btn.getAttribute('data-mode') === mode);
  });
  if (note) {
    note.textContent = mode === 'paper'
      ? '收据纸：使用系统预设 241mm x 140mm 票据纸尺寸。'
      : '普通A4：不锁定纸张尺寸，可在系统打印框选择纵向或横向。';
  }
}
document.addEventListener('DOMContentLoaded', function () {
  setReceiptPrintMode(document.body.classList.contains('receipt-paper') ? 'paper' : 'a4');
});
</script>'''


def print_page(title, content, show_back=True, back_url='/', body_class=''):
    """Generate a self-contained print-friendly HTML page."""
    classes = body_class.split()
    is_receipt = 'receipt-print' in classes
    if is_receipt and 'receipt-a4' not in classes and 'receipt-paper' not in classes:
        classes.append('receipt-a4')
    receipt_controls = _receipt_mode_controls() if is_receipt else ''
    receipt_marker = ''
    if is_receipt:
        receipt_marker = '<div class="receipt-print-marker">收据纸模式：黑色加粗线条，建议纸张 241mm x 140mm，缩放 100%</div>'
    back_btn = ''
    if show_back:
        safe_back_url = html.escape(back_url, quote=True)
        back_btn = f'''
        <div class="print-toolbar">
            <div class="print-toolbar-tip"><strong>保存为PDF：</strong>点击打印后，在打印对话框中选择“保存为 PDF”。纸张名称：Letter=信纸，Legal=法律长纸，Tabloid=小报纸；日常账单建议选 A4。</div>
            {receipt_controls}
            <button onclick="window.print()" style="padding:6pt 18pt;font-size:11pt;cursor:pointer;margin-right:6pt">
                🖨️ 打印
            </button>
            <a href="{safe_back_url}" style="padding:6pt 18pt;font-size:11pt;border:1px solid #999;text-decoration:none;color:#222;margin-left:6pt">← 返回</a>
        </div>'''
    body_class = ' '.join(classes)
    body_attr = f' class="{html.escape(body_class, quote=True)}"' if body_class else ''
    receipt_script = _receipt_mode_script() if is_receipt else ''
    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>{title}</title>
<style>{PRINT_CSS}</style>
</head>
<body{body_attr}>
{back_btn}
{receipt_marker}
{content}
<div class="footer">物业收费管理系统 · 打印时间：{__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
{receipt_script}
</body></html>'''


def print_header_row(label, value):
    """Generate a header-info table row."""
    return f'<tr><td style="width:30%"><strong>{label}</strong></td><td style="width:20%">{value}</td></tr>'
