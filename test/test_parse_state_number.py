from merc_gve.services.mercury.state_number_parser import _parse_state_number


def test_car_state_number():
    assert _parse_state_number("123") is None
    assert _parse_state_number("м123а") is None
    assert _parse_state_number("м123ам") == "м123ам"
    assert _parse_state_number("м123ам123") == "м123ам"
    assert _parse_state_number("м123ам123rus") == "м123ам"
    assert _parse_state_number("м 123 ам 555 rus") == "м123ам"
    assert _parse_state_number("м 1234 ам 555 rus") != "м123ам"
    assert _parse_state_number("вм 123 ам rus 555") == "м123ам"


def test_trailer_state_number():
    assert _parse_state_number("1234") is None
    assert _parse_state_number("ам1234") == "ам1234"
    assert _parse_state_number("ам123499") == "ам1234"
    assert _parse_state_number("ам 1234") == "ам1234"
    assert _parse_state_number("ам 123499") == "ам1234"
    assert _parse_state_number("ам 1234 99") == "ам1234"
    assert _parse_state_number("ам 1234 rus 99") == "ам1234"
    assert _parse_state_number("м123499") is None
