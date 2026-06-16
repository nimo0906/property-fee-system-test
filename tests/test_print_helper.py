from server.print_helper import PRINT_CSS, print_page


def test_print_page_can_render_receipt_paper_class():
    html = print_page("收款收据", "<main>content</main>", body_class="receipt-print")

    assert '<body class="receipt-print">' in html
    assert "收据纸增强版" in html


def test_receipt_print_css_uses_receipt_paper_friendly_rules():
    assert "body.receipt-print" in PRINT_CSS
    assert "size: 241mm 140mm" in PRINT_CSS
    assert "border: 1.4pt solid #000" in PRINT_CSS
    assert "page: receipt" in PRINT_CSS
    assert "@page receipt" in PRINT_CSS
