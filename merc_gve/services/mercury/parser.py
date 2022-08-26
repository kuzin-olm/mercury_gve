# -*- coding: utf-8 -*-
from typing import Optional, List

from requests import Response
from requests.exceptions import ConnectionError, ConnectTimeout

from bs4 import BeautifulSoup as BSoup

from merc_gve.dto import MercuryUserDTO, EnterpriseDTO, EnterpriseNotificationDTO, EnterpriseRequestDTO
from merc_gve.dto.mercury import NotificationType
from merc_gve.services.mercury.base_session import BaseSession
from merc_gve.settings import EXTRA_ENTERPRISE_LIST, PATH_COOKIES, logger


# ---------------------------------------------------------------------------------------------------------------------
# Главный класс для парсинга вет номеров
# ---------------------------------------------------------------------------------------------------------------------
class VetRF:
    """
    для работы с сайтом 'mercury.vetrf.ru/gve/' личный кабинет
    """

    def __init__(
        self, path_cookies: str = PATH_COOKIES, session_cert_verify: bool = True
    ):

        self._url = "https://mercury.vetrf.ru/gve/operatorui"

        self.session = BaseSession()
        self.session.verify = session_cert_verify

        self.is_authenticate = False
        self._path_cookies = path_cookies

        # типы вет док-ов
        self._actions = [
            "VetDocumentAjax",
            "ProducedVetDocumentAjax",
            "RawMilkVetDocumentAjax",
        ]
        # для каждого action подготовим пустой список, чтобы складывать туда спарсенные номера документов
        self._data_with_result_parse = {action: [] for action in self._actions}

    @property
    def url(self):
        return self._url

    def authenticate_by_login(self, login, password):
        """
        до запроса к системе авторизации меркурии,
        проверим куки от предыдущей авторизации, чтобы заново не авторизовываться
        """
        try:
            self.session.read_cookies(file=self._path_cookies)
        except FileNotFoundError:
            logger.debug("файл с куками не найден")

        self.is_authenticate = self.check_authenticate(self.get_start_page())
        if self.is_authenticate:
            logger.debug("имеющиеся куки действительны")
            return self.is_authenticate

        try:
            self.is_authenticate = self._authenticate_by_login(login, password)
        except (ConnectionError, ConnectTimeout) as err:
            self.is_authenticate = False
            logger.error(err)

        return self.is_authenticate

    def _authenticate_by_login(self, login, password):
        logger.info("старт авторизации по логину и паролю")

        login_url = "https://mercury.vetrf.ru/gve"

        page = self.session.fetch(login_url)
        soup = BSoup(page.content, "html5lib")

        # находим скрытую форму
        form = soup.find("form")
        login_fields = form.findAll("input")

        # тут получим первый SAMLRequest из странницы
        logger.debug("получаем SAMLRequest")
        form_data = dict(
            (field.get("name"), field.get("value"))
            for field in login_fields
            if field.get("name") is not None
        )

        # запрос к системе авторизации с уже известным SAMLRequest
        page = self.session.fetch(form["action"], data=form_data)

        # из текущей странницы нам нужна ссылка из формы по которой отправить авторизационные данные
        soup = BSoup(page.content, "html5lib")
        form = soup.find("form")

        # добавляем данные для авторизации
        logger.debug("добавляем данные для аторизации")
        form_data["j_username"] = login
        form_data["j_password"] = password
        form_data["_eventId_proceed"] = ""
        form_data["ksid"] = "lolkek"

        # запрос к системе авторизации по специальной ссылке с данными для авторизации
        logger.debug("запрос к системе авторизации")
        page = self.session.fetch(
            f"https://idp.vetrf.ru{form['action']}", data=form_data
        )

        # теперь у нас должен появиться SAMLResponse (который мы поставим вместо SAMLRequest)
        soup = BSoup(page.content, "html5lib")
        form = soup.find("form")
        login_fields = form.findAll("input")
        temp_data = dict(
            (field.get("name"), field.get("value"))
            for field in login_fields
            if field.get("name") is not None
        )

        # SAMLResponse мы поставим вместо SAMLRequest
        try:
            form_data["SAMLResponse"] = temp_data["SAMLResponse"]
            del form_data["SAMLRequest"]
            logger.debug("SAMLResponse есть в ответе от системы")

            # и отправляем по ссылке (где ее спарсить!?!?! блэд) для подтверждения данных
            logger.debug("отправляем полный набор данных для авторизации в систему")
            self.session.fetch(
                "https://mercury.vetrf.ru/gve/saml/SSO/alias/gve", data=form_data
            )

        except KeyError:
            logger.error("неудачная авторизация, отсутствует SAMLResponse")

        _is_auth = self.check_authenticate(self.get_start_page())
        if _is_auth:
            self.session.save_cookies(file=self._path_cookies)
            logger.debug("куки сохранены")

        return _is_auth

    def authenticate_by_cookies(self, session_id, srv_id):
        cookies = {"JSESSIONID": session_id, "srv_id": srv_id}
        self.session.cookies.update(cookies)

        self.is_authenticate = self.check_authenticate(self.get_start_page())
        return self.is_authenticate

    def get_notify_enterprises(self, types: List[NotificationType], parents: list = None, only_new: bool = False):
        parents = parents or []
        result = []

        page_with_enterprise = self.get_page_with_change_enterprise()
        enterprise_list = self.get_enterprise_list_from_page(
            response=page_with_enterprise
        )

        if parents:
            enterprise_list = [
                enterprise
                for enterprise in enterprise_list
                for parent in parents
                if parent.lower() in enterprise.name.lower()
            ]

        for enterprise in enterprise_list:

            for group_notify in enterprise.notifications:
                if group_notify.type not in types:
                    enterprise.notifications.remove(group_notify)

            if only_new:
                notifications = any([
                    any(map(lambda notify: notify.type == notify_type and notify.new, enterprise.notifications))
                    for notify_type in types
                ])
            else:
                notifications = any([
                    any(map(lambda notify: notify.type == notify_type, enterprise.notifications))
                    for notify_type in types
                ])

            if notifications:
                if NotificationType.HS in types:
                    enterprise.requests = self.get_enterprise_requests(enterprise_pk=enterprise.pk)

                result.append(enterprise)

        return result

    def get_enterprise_requests(self, enterprise_pk: int) -> List[EnterpriseRequestDTO]:
        self.set_enterprise_by_pk(enterprise_pk=enterprise_pk)

        page = self.session.post(self._url, params={
            "_action": "listTransactionAjax",
            "status": 4,
            "formed": "false",
            "all": "true",
            "template": "false",
            "request": "true",
        })

        bs = BSoup(page.text, "lxml")
        html_content = bs.body.htmldata.listcontent

        # выхлоп
        enterprise_requests = []

        for row in html_content.find_all("tr")[1:]:
            html_items = row.find_all("td")
            content = [column.text.strip() for column in html_items[:-1]]

            transaction_pk = int(content[0])

            enterprise_request = EnterpriseRequestDTO(pk=transaction_pk)

            html = self.session.get(self._url, params={
                '_action': 'showTransactionForm',
                'transactionPk': transaction_pk,
            })
            transaction_extra_info = BSoup(html.text, "html5lib")
            transaction_extra_info = transaction_extra_info.find_all("table", {"class": "innerForm"})
            transaction_extra_info_editable = transaction_extra_info[2]

            info_editable = transaction_extra_info_editable.find_all("td", {"class": "value"})
            info_editable = [value.string for value in info_editable]

            # полезные данные
            enterprise_request.car_number = info_editable[5]
            enterprise_request.type_product = info_editable[6]

            info_recipient = transaction_extra_info[3]
            _info_recipient = info_recipient.find_all("td", {"class": "tbody"})

            # полезные данные
            enterprise_request.recipient_prod = _info_recipient[0].a.string
            enterprise_request.recipient_firm = _info_recipient[1].a.string
            enterprise_request.recipient_ttn_number = _info_recipient[2].string
            enterprise_request.recipient_ttn_date = _info_recipient[3].string

            product = info_recipient.find("a", {"title": "просмотр сведений"})

            # полезные данные
            product, product_mass = product.string.strip().split("-")
            enterprise_request.product = product
            enterprise_request.product_mass = product_mass

            enterprise_requests.append(enterprise_request)

        return enterprise_requests

    def run_parse_vetdocument(self, date_begin, date_end, filter_by_fio: list) -> list:

        if not self.is_authenticate:
            raise ValueError("Не авторизованно.")

        if len(filter_by_fio) == 0:
            raise ValueError("Фильтр по ФИО не может быть пустым.")

        result_parse = []

        self._data_with_result_parse = {action: [] for action in self._actions}

        # получили список предприятий
        enterprise_list = self.get_enterprise_list_from_page(
            self.get_page_with_change_enterprise()
        )

        size_enterprise_list = len(enterprise_list)
        if size_enterprise_list == 0:
            return result_parse

        # для каждого предприятия
        for num, enterprise in enumerate(enterprise_list, start=1):
            logger.info(f"{num}/{size_enterprise_list}: {enterprise}")
            try:
                self.parse_vet_doc_from_enterprise(
                    enterprise, date_begin, date_end, filter_by_fio
                )
            except (ValueError, AttributeError) as err:
                logger.error(enterprise)
                logger.error(err)

        # для уточнения по номерам вет.док, чтобы узнать какой конкретно он формы
        # встаем на любое (конкретно тут первое) предприятие, чтобы можно было юзать форму Меркурия
        self.set_enterprise_by_pk(enterprise_list[0].pk)
        for action in self._data_with_result_parse.keys():
            # переходим к странице с нужным типом action`а
            self._go_to_action_page(action)
            # запрашиваем уточнение
            result_parse += self._parse_vet_doc_pks(
                self._data_with_result_parse[action], mod_handler=False
            )
            # все это складывается в список, который передали при вызове

        logger.debug("закончили парсинг")
        return result_parse

    def parse_vet_doc_from_enterprise(
        self, enterprise, date_begin, date_end, filter_by_fio
    ) -> None:
        enterprise_pk = enterprise.pk
        enterprise_name = enterprise.name

        # выберем его основным
        self.set_enterprise_by_pk(enterprise_pk)

        # пройдем по предприятию по списку ФИО в фильтре
        for user in filter_by_fio:

            mercury_user = self.get_user_info_from_mercury_filter(user)
            if not mercury_user:
                logger.info(f"Пользователь {user} в системе меркурии не найден.")
                continue

            logger.debug(
                f"Фильтрация по ФИО: {mercury_user.name} (id в системе = {mercury_user.id})"
            )

            # если предприятие требуется расширить по доп списку то
            if enterprise_pk in EXTRA_ENTERPRISE_LIST.keys():
                # для каждого из этого списка
                for extra_enterprise_pk, extra_enterprise_name in EXTRA_ENTERPRISE_LIST[
                    enterprise_pk
                ].items():

                    # запустить сборщик номеров документов расширенный
                    for action in self._data_with_result_parse.keys():
                        self._data_with_result_parse[
                            action
                        ] += self._parse_doc_numbers_from_action(
                            enterprise_pk=enterprise_pk,
                            enterprise_name=enterprise_name,
                            action=action,
                            date_begin=date_begin,
                            date_end=date_end,
                            user_id=str(mercury_user.id),
                            extra_enterprise_pk=extra_enterprise_pk,
                            extra_enterprise_name=extra_enterprise_name,
                        )

            else:
                # сборщик номеров документов стандартный
                for action in self._data_with_result_parse.keys():
                    self._data_with_result_parse[
                        action
                    ] += self._parse_doc_numbers_from_action(
                        enterprise_pk=enterprise_pk,
                        enterprise_name=enterprise_name,
                        action=action,
                        date_begin=date_begin,
                        date_end=date_end,
                        user_id=str(mercury_user.id),
                        extra_enterprise_pk="",
                        extra_enterprise_name="",
                    )

        # переход на страницу смены предприятия
        self.get_page_with_change_enterprise()

    # получает имя предприятия и его id(value) с home или start
    @staticmethod
    def get_enterprise_list_from_page(response: Response) -> List[EnterpriseDTO]:
        enterprise_list = []

        response = BSoup(response.text, "html5lib")
        table = response.find_all("tbody")[0].find("tr").find_all("tr")

        if table:
            for item in table:
                name = ""
                item = item.find_all("td")
                value = item[0].find("input").get("value")
                name_1 = item[1].text.strip().split()
                while True:
                    if ")" in name_1[-1]:
                        name = " ".join(name_1)
                        break
                    else:
                        name_1 = name_1[:-1]
                        if len(name_1) == 0:
                            break

                enterprise = EnterpriseDTO(pk=value, name=name)

                notifications = item[1].find_all("a")
                for notification in notifications:
                    title = notification.get("title")
                    href = notification.get("href")
                    qty = int(notification.get_text().strip())

                    notify = EnterpriseNotificationDTO(title=title, url=href, qty=qty)
                    enterprise.notifications.append(notify)

                enterprise_list.append(enterprise)

        logger.debug(f"список предприятий: {len(enterprise_list)}")
        return enterprise_list

    def get_page_with_change_enterprise(self) -> Response:
        return self.session.get(
            self._url, params={"_action": "changeServicedEnterprise", "_language": "ru"}
        )

    def set_enterprise_by_pk(self, enterprise_pk) -> None:
        self.session.get(
            self._url,
            params={
                "enterprisePk": enterprise_pk,
                "_action": "chooseServicedEnterprise",
                "_language": "ru",
            },
        )
        logger.debug(f"Выбрано предприятие: {enterprise_pk}")

    # получаем ФИО и id из системы
    def get_user_info_from_mercury_filter(self, name) -> Optional[MercuryUserDTO]:
        response = self.session.post(
            self._url,
            params={"_action": "listVUUsersJson", "_language": "ru"},
            data={"template": name, "pageList": ""},
        )

        res = response.json()["results"]
        if len(res) > 0:
            return MercuryUserDTO(id=res[0]["id"], name=res[0]["text"])

        return None

    def _parse_doc_numbers_from_action(
        self,
        enterprise_pk,
        enterprise_name,
        action,
        date_begin,
        date_end,
        user_id="null",
        extra_enterprise_pk="",
        extra_enterprise_name="",
    ):

        self._go_to_action_page(action)

        page_with_find_docs = self._find_doc_on_action_page(
            enterprise_name,
            date_begin,
            date_end,
            action,
            page=1,
            user_id=user_id,
            extra_enterprise_pk=extra_enterprise_pk,
            extra_enterprise_name=extra_enterprise_name,
        )

        list_with_doc_number = self._parse_doc_number_from_page(page_with_find_docs)

        word_next = self._check_word_next(page_with_find_docs)
        if word_next:
            page = 2
            while True:
                logger.debug(f"{enterprise_name[:30]}... [{action}] на странице {page}")

                page_with_find_docs = self._find_doc_on_action_page(
                    enterprise_name,
                    date_begin,
                    date_end,
                    action,
                    page,
                    user_id,
                    extra_enterprise_pk,
                    extra_enterprise_name,
                )

                __current_parse_doc_number = self._parse_doc_number_from_page(
                    page_with_find_docs
                )
                if __current_parse_doc_number:
                    list_with_doc_number += __current_parse_doc_number

                word_next = self._check_word_next(page_with_find_docs)
                if not word_next:
                    break
                page += 1

        return list_with_doc_number

    # переход на страницу вет документов/производственных/молочки по action
    def _go_to_action_page(self, action) -> None:
        self.session.post(
            self._url,
            params={"_action": action, "all": "true"},
            data={"rows": "100", "_action": "list" + action, "_language": "ru"},
        )
        self.session.post(
            self._url,
            data={"rows": "100", "_action": "list" + action, "_language": "ru"},
        )

    # поиск документов среди одного предприятия по дате,виду action, и возм. ФИО
    def _find_doc_on_action_page(
        self,
        enterprise_name,
        date_begin,
        date_end,
        action,
        page=1,
        user_id="null",
        extra_enterprise_pk="",
        extra_enterprise_name="",
    ):

        if action == "RawMilkVetDocumentAjax":
            return self.session.post(
                self._url,
                data={
                    "senderEnterprise.name": enterprise_name,
                    "firm": extra_enterprise_pk,
                    "traffic.firm.name": extra_enterprise_name,
                    "findStateSet": [1, 7, 3],
                    "vetDocumentDate": date_begin,
                    "vetDocumentDateTo": date_end,
                    "whoGeneral": user_id,
                    "findUserSet": [4, 2, 3],
                    "productType": 5,
                    "product": 26,
                    "pageList": page,
                    "find": "true",
                    "_action": "find" + action,
                    "request": "false",
                    "_language": "ru",
                },
            ).text
        elif action in ["VetDocumentAjax", "ProducedVetDocumentAjax"]:
            return self.session.post(
                self._url,
                data={
                    "senderEnterprise.name": enterprise_name,
                    "firm": extra_enterprise_pk,
                    "traffic.firm.name": extra_enterprise_name,
                    "findStateSet": [1, 7, 3],
                    "vetDocumentDate": date_begin,
                    "vetDocumentDateTo": date_end,
                    "whoGeneral": user_id,
                    "findUserSet": [4, 2],
                    "pageList": page,
                    "find": "true",
                    "_action": "find" + action,
                    "request": "false",
                    "_language": "ru",
                },
            ).text

    # со страницы ответа поисковика выцепляет все номера вет.доков
    @staticmethod
    def _parse_doc_number_from_page(page_with_docs) -> list:
        list_doc_numbers = []

        list_with_doc = BSoup(page_with_docs, "html5lib").find_all(
            "input", {"name": "vetDocumentPk"}
        )

        if list_with_doc:
            [list_doc_numbers.append(item.get("value")) for item in list_with_doc]
        return list_doc_numbers

    @staticmethod
    def _check_word_next(page_with_doc):
        """
        на странице поиска ищет слово "Следующая"
        """
        doc_page = BSoup(page_with_doc, "html5lib").find(
            "div", {"class": "pagenavBlock"}
        )
        if doc_page:
            if doc_page.find("a"):
                word_next = doc_page.find_all("a")[-1].text
                if word_next.lower() == "следующая":
                    return True
        return False

    def _parse_vet_doc_pks(self, vet_doc_numbers: list, mod_handler=False):
        """
        У меркурия через говноАПИ можно запросить детализацию по ветномерам,
        но не более 1000 за раз (а через парсинг веба только по 100 :D)

        подготавливаем пачки по 1000 номеров
        """
        result = []

        size_list = len(vet_doc_numbers)
        if size_list > 1000:

            ish = size_list // 1000
            for i in range(1, ish + 1):
                result += self._parse_vet_doc_pks_by_batch(
                    vet_doc_numbers[i * 1000 - 1000 : i * 1000], mod_handler=mod_handler
                )

            if size_list % 1000 > 0:
                result += self._parse_vet_doc_pks_by_batch(
                    vet_doc_numbers[ish * 1000 :], mod_handler=mod_handler
                )

        else:
            result += self._parse_vet_doc_pks_by_batch(
                vet_doc_numbers, mod_handler=mod_handler
            )

        return result

    def _parse_vet_doc_pks_by_batch(self, vet_doc_numbers: list, mod_handler=False):
        """
        Обработка пачек вет номеров
        """
        response = self.session.post(
            self._url,
            data={
                "printScope": "currentPage",
                "printType": 1,
                "printAction": 2,
                "printSchemaSelect": "null",
                "number": "printField",
                "sender": "printField",
                "service": "printField",
                "_action": "printSelectedVetDocuments",
                "_language": "ru",
                "printForm": "vetDocumentPrintForm",
                "selectedVetDocumentPk": vet_doc_numbers,
            },
        )

        table = (
            BSoup(response.text, "html5lib")
            .find("td", {"class": "data"})
            .find("tbody")
            .find_all("tr")
        )
        result_table = []

        row = 3 if mod_handler else 2
        for item in table:
            item = item.find_all("td")

            result_table.append(
                {
                    "vetDoc": item[1].text,
                    "name_corp": item[row].text,
                    "owner_product": item[2].text,
                    "type_service": " ".join(item[4].text.split()),
                }
            )
        return result_table

    def get_start_page(self) -> Optional[Response]:
        try:
            return self.session.get(
                self._url, params={"_action": "login", "_language": "ru"}
            )
        except UnicodeEncodeError:
            return None

    def go_to_home_page(self) -> None:
        self.session.get(self._url, params={"_action": "home", "_language": "ru"})

    def check_authenticate(self, html) -> bool:
        user_info = self.get_authenticated_user_info_from_page(html)

        if user_info:
            return True
        return False

    @staticmethod
    def get_authenticated_user_info_from_page(html) -> str:
        user_info = None

        logged_as = BSoup(html.text, "html5lib").find("div", {"id": "loggedas"})
        if logged_as:
            _user_info = logged_as.text.split()
            user_info = " ".join(_user_info[1:5])
        return user_info
