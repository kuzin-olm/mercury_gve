import re
from typing import List
from dataclasses import dataclass, field

from merc_gve.types import NotificationType
from merc_gve.services.mercury.state_number_parser import search_state_number


CAR_RUS_MINI_REGEX = r"(?i)^[АВЕКМНОРСТУХ]\d{3}(?<!000)[АВЕКМНОРСТУХ]{2}$"
CAR_RUS_FULL_REGEX = r"(?i)^[АВЕКМНОРСТУХ]\d{3}(?<!000)[АВЕКМНОРСТУХ]{2} *\d{2,3}$"
TRAILERS_RUS_MINI_REGEX = r"(?i)^[АВЕКМНОРСТУХ]{2}\d{4}(?<!0000)$"
TRAILERS_RUS_FULL_REGEX = r"(?i)^[АВЕКМНОРСТУХ]{2}\d{4}(?<!0000) *\d{2,3}$"


@dataclass(frozen=True)
class User:
    login: str
    password: str


@dataclass
class VerifiedValue:
    value: str
    is_verified: bool = False


@dataclass(frozen=True)
class MercuryUserDTO:
    id: int
    name: str


@dataclass
class EnterpriseNotificationDTO:
    title: str
    url: str
    qty: int
    new: bool = field(default=False)
    type: NotificationType = field(default=None)

    def __post_init__(self):
        if "есть новые" in self.title.lower():
            self.new = True

        if NotificationType.HS.value in self.title.lower():
            self.type = NotificationType.HS
        elif NotificationType.VSD.value in self.title.lower():
            self.type = NotificationType.VSD


@dataclass
class EnterpriseRequestDTO:
    pk: int
    type: str = None
    _delivery_transport: str = None
    product: str = None
    product_mass: str = None
    type_product: str = None
    recipient_prod: str = None
    recipient_firm: str = None
    recipient_ttn_number: str = None
    recipient_ttn_date: str = None

    car_state_number: VerifiedValue = None
    trailer_state_number: VerifiedValue = None

    @property
    def delivery_transport(self):
        return self._delivery_transport

    @delivery_transport.setter
    def delivery_transport(self, val: str):
        if not isinstance(val, str):
            raise ValueError('Value must be a string')
        self._delivery_transport = val

        numbers = [number.strip() for number in val.split("/")]

        if len(numbers) > 0:
            self.car_state_number = VerifiedValue(value=numbers[0])

            if car := search_state_number(numbers[0]):
                self.car_state_number = VerifiedValue(value=car, is_verified=True)

        if len(numbers) > 1:
            self.trailer_state_number = VerifiedValue(value=numbers[1])

            if trailer := search_state_number(numbers[1]):
                self.trailer_state_number = VerifiedValue(value=trailer, is_verified=True)


@dataclass
class EnterpriseDTO:
    pk: int
    name: str
    notifications: List[EnterpriseNotificationDTO] = field(default_factory=lambda: [])
    requests: List[EnterpriseRequestDTO] = field(default_factory=lambda: [])
