# from settings import MERCURY_LOGIN, MERCURY_PASSWORD
#
# from bs4 import BeautifulSoup as BS
#
# from merc_gve.dto import User, EnterpriseRequestDTO
# from merc_gve.services.mercury.parser import VetRF
#
# user = User(login=MERCURY_LOGIN, password=MERCURY_PASSWORD)
#
# mercury_gve = VetRF()
#
#
# is_auth = mercury_gve.authenticate_by_login(login=user.login, password=user.password)
#
#
# if is_auth:
#     mercury_gve.set_enterprise_by_pk(enterprise_pk=701176)
#     # mercury_gve.set_enterprise_by_pk(enterprise_pk=1880700)
#
#     page = mercury_gve.session.post(mercury_gve.url, params={
#         "_action": "listTransactionAjax",
#         "status": 4,
#         "formed": "false",
#         "all": "true",
#         "template": "false",
#         "request": "true"
#     })
#     # url = (
#     #     "https://mercury.vetrf.ru/gve/operatorui?"
#     #     "_action=listTransactionAjax"
#     #     "&formed=false"
#     #     "&status=4"
#     #     "&pageList=1"
#     #     "&all=true"
#     #     "&request=true"
#     #     "&template=false"
#     #     "&timestamp=1661262903265"
#     # )
#     # page = mercury_gve.session.post(url)
#     print(page.text)
#     bs = BS(page.text, "lxml")
#     html_content = bs.body.htmldata.listcontent
#
#     # выхлоп
#     enterprise_requests = []
#
#     for row in html_content.find_all("tr")[1:]:
#         html_items = row.find_all("td")
#         content = [column.text.strip() for column in html_items[:-1]]
#
#         transaction_pk = int(content[0])
#
#         enterprise_request = EnterpriseRequestDTO(pk=transaction_pk)
#
#         html = mercury_gve.session.get(mercury_gve.url, params={
#             '_action': 'showTransactionForm',
#             'transactionPk': transaction_pk,
#         })
#         transaction_extra_info = BS(html.text, "html5lib")
#         transaction_extra_info = transaction_extra_info.find_all("table", {"class": "innerForm"})
#         transaction_extra_info_editable = transaction_extra_info[2]
#
#         info_editable = transaction_extra_info_editable.find_all("td", {"class": "value"})
#         info_editable = [value.string for value in info_editable]
#
#         # полезные данные
#         enterprise_request.auto_number = info_editable[5]
#         enterprise_request.type_product = info_editable[6]
#
#         info_recipient = transaction_extra_info[3]
#         _info_recipient = info_recipient.find_all("td", {"class": "tbody"})
#
#         # полезные данные
#         enterprise_request.recipient_prod = _info_recipient[0].a.string
#         enterprise_request.recipient_firm = _info_recipient[1].a.string
#         enterprise_request.recipient_ttn_number = _info_recipient[2].string
#         enterprise_request.recipient_ttn_date = _info_recipient[3].string
#
#         product = info_recipient.find("a", {"title": "просмотр сведений"})
#
#         # полезные данные
#         product, product_mass = product.string.strip().split("-")
#         enterprise_request.product = product
#         enterprise_request.product_mass = product_mass
#
#         enterprise_requests.append(enterprise_request)
#         # break
#
#     for enterprise_request in enterprise_requests:
#         print(enterprise_request)
