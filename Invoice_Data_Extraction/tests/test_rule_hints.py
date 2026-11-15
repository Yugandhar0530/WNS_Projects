from rule_hints import derive_rule_hints


def test_invoice_number_and_total():
    text = """
    Acme Supplies LLC
    Invoice No: INV-2024-991
    Date: 03/15/2024
    Total: $1,250.50
    """
    hints = derive_rule_hints(text)
    assert hints.get("invoice_number") == "INV-2024-991"
    assert hints.get("total_amount") == "1250.50"
    assert hints.get("vendor_name") == "Acme Supplies LLC"


def test_iso_date_and_currency():
    text = "Invoice # 88\n2024-11-01\nAmount due USD 99.00"
    hints = derive_rule_hints(text)
    assert hints.get("date") == "2024-11-01"
    assert hints.get("currency") == "USD"


def test_empty_text():
    assert derive_rule_hints("   \n") == {}