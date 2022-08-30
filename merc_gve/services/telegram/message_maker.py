from typing import List

from merc_gve.dto import EnterpriseDTO
from merc_gve.settings import logger
from merc_gve.types import NotificationType

MESSAGE_LENGTH = 4096


def make_answer_by_enterprises(enterprises: List[EnterpriseDTO]) -> List[str]:

    text_answer = ""
    answers = []

    for enterprise in enterprises:
        try:
            for group_notify in enterprise.notifications:
                url = make_html_mercury_url(
                    title=f"<b>{group_notify.qty} событий ({group_notify.type.value})</b>",
                    url=group_notify.url
                )
                request_str = ""
                if group_notify.type == NotificationType.HS:
                    for idx, request in enumerate(enterprise.requests, start=1):
                        request_str += (
                            f"\n"
                            f"<b>Событие {idx}</b>\n"
                            f"Предприятие: {request.recipient_firm}\n"
                            f"Фирма: {request.recipient_prod}\n"
                            f"Продукт: {request.product}({request.product_mass})\n"
                            f"Тип продукта: {request.type_product}\n"
                            f"Транспорт доставки: {request.delivery_transport}\n"
                        )
                        if request.car_state_number:
                            status = make_emoji_status(request.car_state_number.is_verified)
                            request_str += f"{status}Машина: {request.car_state_number.value}\n"

                        if request.trailer_state_number:
                            status = make_emoji_status(request.trailer_state_number.is_verified)
                            request_str += f"{status}Прицеп: {request.trailer_state_number.value}\n"

                text_answer += (
                    f"{enterprise.name}:\n{url}\n"
                    f"{request_str}"
                    f"\n\n"
                )
        except IndexError:
            logger.error(enterprise.notifications)

    text_answer = text_answer or "нет новых событий"

    if len(text_answer) < MESSAGE_LENGTH:
        answers.append(text_answer)

    else:
        while len(text_answer) > 0:
            pre_answer = text_answer[:MESSAGE_LENGTH]

            pre_answer = pre_answer.split("\n\n")
            if len(text_answer) > MESSAGE_LENGTH:
                pre_answer = pre_answer[:-1]

            pre_answer = "\n\n".join(pre_answer)
            size_slice = len(pre_answer)

            answers.append(pre_answer)

            text_answer = text_answer[size_slice + 1:]
            text_answer = text_answer.strip("\n\n")

    return answers


def make_html_mercury_url(title, url):
    url = f"https://mercury.vetrf.ru/gve/{url}"
    url = f"<a href='{url}'>{title}</a>"
    return url


def make_emoji_status(status: bool) -> str:
    return "🍚🐈👰‍♀️" if status else "➖💯"
