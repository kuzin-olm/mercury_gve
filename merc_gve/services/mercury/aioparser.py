# -*- coding: utf-8 -*-
import json
from uuid import uuid4
from typing import Optional, List

import aiohttp

from bs4 import BeautifulSoup as BSoup
from yarl import URL

from merc_gve.dto import MercuryUserDTO, EnterpriseDTO, EnterpriseNotificationDTO, EnterpriseRequestDTO
from merc_gve.dto.mercury import NotificationType
from merc_gve.settings import EXTRA_ENTERPRISE_LIST, PATH_COOKIES, logger


class VetRF:
    """
    для работы с сайтом 'mercury.vetrf.ru/gve/' личный кабинет
    """
    HEADERS = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7,zh-TW;q=0.6,zh;q=0.5",
        "Cache-Control": "max-age=0",
        "Connection": "keep-alive",
        "Origin": "https://idp.vetrf.ru",
        "sec-ch-ua": '"Not A;Brand";v="99", "Chromium";v="96", "Google Chrome";v="96"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
    }

    def __init__(self, path_cookies: str = PATH_COOKIES):

        self._url = "https://mercury.vetrf.ru/gve/operatorui"

        self.session = aiohttp.ClientSession(headers=self.HEADERS)

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

    async def close(self):
        await self.session.close()

    @property
    def url(self):
        return self._url

    async def authenticate_by_login(self, login, password):
        """
        до запроса к системе авторизации меркурии,
        проверим куки от предыдущей авторизации, чтобы заново не авторизовываться
        """
        try:
            self.read_cookies()
        except FileNotFoundError:
            logger.debug("файл с куками не найден")

        start_page = await self.get_start_page()
        self.is_authenticate = self.check_authenticate(start_page)
        if self.is_authenticate:
            logger.debug("имеющиеся куки действительны")
            return self.is_authenticate

        try:
            self.session.cookie_jar.clear()
            self.is_authenticate = await self._authenticate_by_login(login, password)
        except Exception as err:
            self.is_authenticate = False
            await self.session.close()
            logger.error(err)

        return self.is_authenticate

    async def _authenticate_by_login(self, login, password):
        logger.info("старт авторизации по логину и паролю")

        login_url = "https://mercury.vetrf.ru/gve"

        async with self.session.get(login_url) as resp:
            content = await resp.text()

        soup = BSoup(content, "html5lib")

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
        async with self.session.post(form["action"], data=form_data) as resp:
            content = await resp.text()

        # из текущей странницы нам нужна ссылка из формы по которой отправить авторизационные данные
        soup = BSoup(content, "html5lib")
        form = soup.find("form")

        # добавляем данные для авторизации
        logger.debug("добавляем данные для аторизации")
        form_data["j_username"] = login
        form_data["j_password"] = password
        form_data["_eventId_proceed"] = ""
        form_data["ksid"] = str(uuid4())

        # запрос к системе авторизации по специальной ссылке с данными для авторизации
        logger.debug("запрос к системе авторизации")
        async with self.session.post(f"https://idp.vetrf.ru{form['action']}", data=form_data) as resp:
            content = await resp.text()

        # теперь у нас должен появиться SAMLResponse (который мы поставим вместо SAMLRequest)
        soup = BSoup(content, "html5lib")
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
            async with self.session.post("https://mercury.vetrf.ru/gve/saml/SSO/alias/gve", data=form_data) as resp:
                content = await resp.text()

        except KeyError:
            logger.error("неудачная авторизация, отсутствует SAMLResponse")

        start_page = await self.get_start_page()
        _is_auth = self.check_authenticate(start_page)
        if _is_auth:
            self.save_cookies()
            logger.debug("куки сохранены")

        return _is_auth

    async def authenticate_by_cookies(self, session_id, srv_id):
        cookies = {"JSESSIONID": session_id, "srv_id": srv_id}
        self.session.cookie_jar.update_cookies(cookies)

        start_page = await self.get_start_page()
        self.is_authenticate = self.check_authenticate(start_page)
        return self.is_authenticate

    async def get_notify_enterprises(
            self,
            types: List[NotificationType],
            parents: list = None,
            only_new: bool = False,
    ) -> List[EnterpriseDTO]:

        parents = parents or []
        result = []

        page_with_enterprise = await self.get_page_with_change_enterprise()
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
                    enterprise.requests = await self.get_enterprise_requests(enterprise_pk=enterprise.pk)

                result.append(enterprise)

        return result

    async def get_enterprise_requests(self, enterprise_pk: int) -> List[EnterpriseRequestDTO]:
        await self.set_enterprise_by_pk(enterprise_pk=enterprise_pk)

        async with self.session.post(self._url, params={
            "_action": "listTransactionAjax",
            "status": 4,
            "formed": "false",
            "all": "true",
            "template": "false",
            "request": "true",
        }) as response:
            content = await response.text()

        bs = BSoup(content, "lxml")
        html_content = bs.body.htmldata.listcontent

        # выхлоп
        enterprise_requests = []

        for row in html_content.find_all("tr")[1:]:
            html_items = row.find_all("td")
            content = [column.text.strip() for column in html_items[:-1]]

            transaction_pk = int(content[0])

            enterprise_request = EnterpriseRequestDTO(pk=transaction_pk)

            async with self.session.get(self._url, params={
                '_action': 'showTransactionForm',
                'transactionPk': transaction_pk,
            }) as response:
                content = await response.text()

            transaction_extra_info = BSoup(content, "html5lib")
            transaction_extra_info = transaction_extra_info.find_all("table", {"class": "innerForm"})
            transaction_extra_info_editable = transaction_extra_info[2]

            info_editable = transaction_extra_info_editable.find_all("td", {"class": "value"})
            info_editable = [value.string for value in info_editable]

            # полезные данные
            enterprise_request.delivery_transport = info_editable[5]
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

    async def run_parse_vetdocument(self, date_begin, date_end, filter_by_fio: list) -> list:

        if not self.is_authenticate:
            raise ValueError("Не авторизованно.")

        if len(filter_by_fio) == 0:
            raise ValueError("Фильтр по ФИО не может быть пустым.")

        result_parse = []

        self._data_with_result_parse = {action: [] for action in self._actions}

        # получили список предприятий
        page_with_change_enterprises = await self.get_page_with_change_enterprise()
        enterprise_list = self.get_enterprise_list_from_page(page_with_change_enterprises)

        size_enterprise_list = len(enterprise_list)
        if size_enterprise_list == 0:
            return result_parse

        # для каждого предприятия
        for num, enterprise in enumerate(enterprise_list, start=1):
            logger.info(f"{num}/{size_enterprise_list}: {enterprise}")
            try:
                await self.parse_vet_doc_from_enterprise(enterprise, date_begin, date_end, filter_by_fio)
            except (ValueError, AttributeError) as err:
                logger.error(enterprise)
                logger.error(err)

        # для уточнения по номерам вет.док, чтобы узнать какой конкретно он формы
        # встаем на любое (конкретно тут первое) предприятие, чтобы можно было юзать форму Меркурия
        await self.set_enterprise_by_pk(enterprise_list[0].pk)
        for action in self._data_with_result_parse.keys():
            # переходим к странице с нужным типом action`а
            await self._go_to_action_page(action)
            # запрашиваем уточнение
            result_parse += await self._parse_vet_doc_pks(
                self._data_with_result_parse[action], mod_handler=False
            )
            # все это складывается в список, который передали при вызове

        logger.debug("закончили парсинг")
        return result_parse

    async def parse_vet_doc_from_enterprise(
        self, enterprise, date_begin, date_end, filter_by_fio
    ) -> None:
        enterprise_pk = enterprise.pk
        enterprise_name = enterprise.name

        # выберем его основным
        await self.set_enterprise_by_pk(enterprise_pk)

        # пройдем по предприятию по списку ФИО в фильтре
        for user in filter_by_fio:

            mercury_user = await self.get_user_info_from_mercury_filter(user)
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
                        ] += await self._parse_doc_numbers_from_action(
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
                    ] += await self._parse_doc_numbers_from_action(
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
        await self.get_page_with_change_enterprise()

    @staticmethod
    def get_enterprise_list_from_page(response: str) -> List[EnterpriseDTO]:
        """
        получает имя предприятия и его id(value) с home или start
        """
        enterprise_list = []

        response = BSoup(response, "html5lib")
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

    async def get_page_with_change_enterprise(self) -> str:
        async with self.session.get(
                self._url,
                params={"_action": "changeServicedEnterprise", "_language": "ru"}
        ) as resp:
            return await resp.text()

    async def set_enterprise_by_pk(self, enterprise_pk) -> None:
        await self.session.get(
            self._url,
            params={
                "enterprisePk": enterprise_pk,
                "_action": "chooseServicedEnterprise",
                "_language": "ru",
            },
        )
        logger.debug(f"Выбрано предприятие: {enterprise_pk}")

    async def get_user_info_from_mercury_filter(self, name) -> Optional[MercuryUserDTO]:
        """
        получаем ФИО и id из системы
        """
        async with self.session.post(
            self._url,
            params={"_action": "listVUUsersJson", "_language": "ru"},
            data={"template": name, "pageList": ""},
        ) as response:
            resp_json = await response.json()

        res = resp_json["results"]
        if len(res) > 0:
            return MercuryUserDTO(id=res[0]["id"], name=res[0]["text"])

        return None

    async def _parse_doc_numbers_from_action(
        self,
        enterprise_pk,
        enterprise_name,
        action,
        date_begin,
        date_end,
        user_id="null",
        extra_enterprise_pk="",
        extra_enterprise_name="",
    ) -> list:

        await self._go_to_action_page(action)

        page_with_find_docs = await self._find_doc_on_action_page(
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

                page_with_find_docs = await self._find_doc_on_action_page(
                    enterprise_name,
                    date_begin,
                    date_end,
                    action,
                    page,
                    user_id,
                    extra_enterprise_pk,
                    extra_enterprise_name,
                )

                __current_parse_doc_number = self._parse_doc_number_from_page(page_with_find_docs)
                if __current_parse_doc_number:
                    list_with_doc_number += __current_parse_doc_number

                word_next = self._check_word_next(page_with_find_docs)
                if not word_next:
                    break
                page += 1

        return list_with_doc_number

    async def _go_to_action_page(self, action) -> None:
        """
        переход на страницу вет документов/производственных/молочки по action
        """
        await self.session.post(
            self._url,
            params={"_action": action, "all": "true"},
            data={"rows": "100", "_action": "list" + action, "_language": "ru"},
        )
        await self.session.post(
            self._url,
            data={"rows": "100", "_action": "list" + action, "_language": "ru"},
        )

    async def _find_doc_on_action_page(
        self,
        enterprise_name,
        date_begin,
        date_end,
        action,
        page=1,
        user_id="null",
        extra_enterprise_pk="",
        extra_enterprise_name="",
    ) -> str:
        """
        поиск документов среди одного предприятия по дате,виду action, и возм. ФИО
        """

        if action == "RawMilkVetDocumentAjax":
            async with self.session.post(
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
            ) as response:
                return await response.text()

        elif action in ["VetDocumentAjax", "ProducedVetDocumentAjax"]:
            async with self.session.post(
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
            ) as response:
                return await response.text()

    @staticmethod
    def _parse_doc_number_from_page(page_with_docs) -> list:
        """
        со страницы ответа поисковика выцепляет все номера вет.доков
        """
        list_doc_numbers = []

        list_with_doc = BSoup(page_with_docs, "html5lib").find_all(
            "input", {"name": "vetDocumentPk"}
        )

        if list_with_doc:
            [list_doc_numbers.append(item.get("value")) for item in list_with_doc]
        return list_doc_numbers

    @staticmethod
    def _check_word_next(page_with_doc) -> bool:
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

    async def _parse_vet_doc_pks(self, vet_doc_numbers: list, mod_handler=False) -> list:
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
                result += await self._parse_vet_doc_pks_by_batch(
                    vet_doc_numbers[i * 1000 - 1000 : i * 1000], mod_handler=mod_handler
                )

            if size_list % 1000 > 0:
                result += await self._parse_vet_doc_pks_by_batch(
                    vet_doc_numbers[ish * 1000 :], mod_handler=mod_handler
                )

        else:
            result += await self._parse_vet_doc_pks_by_batch(
                vet_doc_numbers, mod_handler=mod_handler
            )

        return result

    async def _parse_vet_doc_pks_by_batch(self, vet_doc_numbers: list, mod_handler=False) -> list:
        """
        Обработка пачек вет номеров
        """
        async with self.session.post(
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
        ) as response:
            content = await response.text()

        table = (
            BSoup(content, "html5lib")
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

    async def get_start_page(self) -> str:
        try:
            async with self.session.get(self._url, params={"_action": "login", "_language": "ru"}) as resp:
                return await resp.text()
        except Exception as err:
            logger.error(f"Error while getting start page: {err}")
            return ""

    async def go_to_home_page(self) -> None:
        await self.session.get(self._url, params={"_action": "home", "_language": "ru"})

    def check_authenticate(self, html: str) -> bool:
        user_info = self.get_authenticated_user_info_from_page(html)

        if user_info:
            return True
        return False

    @staticmethod
    def get_authenticated_user_info_from_page(html: str) -> str:
        user_info = None

        logged_as = BSoup(html, "html5lib").find("div", {"id": "loggedas"})
        if logged_as:
            _user_info = logged_as.text.split()
            user_info = " ".join(_user_info[1:5])
        return user_info

    def read_cookies(self, file=None) -> None:
        file = file or self._path_cookies

        with open(file, "r") as f:
            self.session.cookie_jar.update_cookies(json.load(f))

    def save_cookies(self, file=None) -> None:
        file = file or self._path_cookies

        cookies = self.session.cookie_jar.filter_cookies(URL(self._url))

        output_cookies = dict()
        for _, cookie in cookies.items():
            output_cookies[cookie.key] = cookie.value

        with open(file, "w") as f:
            json.dump(output_cookies, f, indent=4)
