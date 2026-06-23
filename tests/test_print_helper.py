from server.print_helper import PRINT_CSS, print_page


def test_print_page_can_render_receipt_mode_switcher_defaulting_to_a4():
    html = print_page("收款收据", "<main>content</main>", body_class="receipt-print")

    assert '<body class="receipt-print receipt-a4">' in html
    assert "普通A4" in html
    assert "收据纸 241×140" in html
    assert "收据纸 241×92" in html
    assert "可在系统打印框选择纵向或横向" in html
    assert "setReceiptPrintMode" in html


def test_receipt_print_css_keeps_receipt_paper_as_optional_mode():
    assert "body.receipt-print" in PRINT_CSS
    assert "body.receipt-print.receipt-paper" in PRINT_CSS
    assert "body.receipt-print.receipt-paper-92" in PRINT_CSS
    assert "size: 241mm 140mm" in PRINT_CSS
    assert "size: 241mm 92mm" in PRINT_CSS
    assert "border: 1.4pt solid #000" in PRINT_CSS
    assert "page: receipt140" in PRINT_CSS
    assert "page: receipt92" in PRINT_CSS
    assert "@page receipt140" in PRINT_CSS
    assert "@page receipt92" in PRINT_CSS


def test_receipt_a4_mode_does_not_force_receipt_paper_page():
    html = print_page("收款收据", "<main>content</main>", body_class="receipt-print receipt-a4")

    assert '<body class="receipt-print receipt-a4">' in html
    assert "setReceiptPrintMode('a4')" in html
    assert "setReceiptPrintMode('paper')" in html
    assert "setReceiptPrintMode('paper92')" in html
