import json

from yarl import URL

from merc_gve.settings import logger
from merc_gve.dto import User as MercuryAuthUser
from merc_gve.database import User, Config
from merc_gve.services.mercury.aioparser import VetRF


class MercuryDB(VetRF):

    def __init__(self, telegram_user: User, auth_user: MercuryAuthUser):
        super().__init__()
        self.user: User = telegram_user
        self.auth_user: MercuryAuthUser = auth_user

    async def authenticate_by_login(self, login, password):
        login = self.auth_user.login
        password = self.auth_user.password

        is_authenticate = await super().authenticate_by_login(login, password)
        return is_authenticate
    
    def read_cookies(self, file=None) -> None:
        user_config = self._get_user_config_from_db()
        logger.debug(user_config)

        cookies = json.loads(user_config.mercury_cookies)
        self.session.cookie_jar.update_cookies(cookies)

    def save_cookies(self, file=None) -> None:
        user_config = self._get_user_config_from_db()

        cookies = self.session.cookie_jar.filter_cookies(URL(self._url))

        output_cookies = dict()
        for _, cookie in cookies.items():
            output_cookies[cookie.key] = cookie.value

        user_config.mercury_cookies = json.dumps(output_cookies)
        user_config.save()

    def _get_user_config_from_db(self) -> Config:
        user_config, _ = Config.get_or_create(
            user=self.user,
            mercury_login=self.auth_user.login,
            defaults=dict(mercury_password=self.auth_user.password),
        )
        return user_config
    