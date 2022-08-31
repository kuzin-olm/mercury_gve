import re
from typing import Optional

from merc_gve.settings import DELIVERY_CAR_NUMBERS, logger

__all__ = ['search_state_number']


def search_state_number(state_number: str, verified_state_numbers: list = DELIVERY_CAR_NUMBERS):
    state_number = _parse_state_number(state_number)

    if state_number:
        for verified_number in verified_state_numbers:
            if state_number.upper() in verified_number.upper():
                return verified_number

    return None


def _parse_state_number(state_number: str) -> Optional[str]:
    state_number = state_number.replace(" ", "")
    number = None

    try:
        if regex_car := re.search(r"(?<!\d)(\d{3})(?!\d{2})", state_number):
            start = regex_car.start()
            end = regex_car.end()
            number = state_number[start - 1:end + 2]

        if regex_trailer := re.search(r"(?<!\d{2})(\d{4})", state_number):
            start = regex_trailer.start()
            end = regex_trailer.end()
            number = state_number[start - 2:end]

    except IndexError as err:
        logger.error(err)

    return number


def _parse_state_number_non_re(state_number: str) -> Optional[str]:
    state_number = state_number.replace(" ", "")
    parsed_state_number = []
    for char in state_number:
        if not char.isdigit() and len(parsed_state_number):
            if 3 <= len(parsed_state_number):
                break

        if len(parsed_state_number) >= 4:
            break

        if not char.isdigit() and len(parsed_state_number) < 3:
            parsed_state_number.clear()

        if char.isdigit():
            parsed_state_number.append(char)

    parsed_state_number = "".join(parsed_state_number)

    start = state_number.index(parsed_state_number)

    try:
        # trailer
        if len(parsed_state_number) == 4:
            parsed_state_number = state_number[start - 2:start + 4]
        # car
        elif len(parsed_state_number) == 3:
            parsed_state_number = state_number[start - 1:start + 5]
    except IndexError as err:
        logger.error(err)
        return None

    return parsed_state_number
