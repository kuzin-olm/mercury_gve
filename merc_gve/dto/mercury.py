import re
from typing import List
from dataclasses import dataclass, field

from merc_gve.types import NotificationType


CAR_RUS_MINI_REGEX = r"(?i)^[АВЕКМНОРСТУХ]\d{3}(?<!000)[АВЕКМНОРСТУХ]{2}$"
CAR_RUS_FULL_REGEX = r"(?i)^[АВЕКМНОРСТУХ]\d{3}(?<!000)[АВЕКМНОРСТУХ]{2} *\d{2,3}$"
TRAILERS_RUS_MINI_REGEX = r"(?i)^[АВЕКМНОРСТУХ]{2}\d{4}(?<!0000)$"
TRAILERS_RUS_FULL_REGEX = r"(?i)^[АВЕКМНОРСТУХ]{2}\d{4}(?<!0000) *\d{2,3}$"


@dataclass(frozen=True)
class User:
    login: str
    password: str


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
    _car_number: str = None
    _verified_car_number: str = None
    product: str = None
    product_mass: str = None
    type_product: str = None
    recipient_prod: str = None
    recipient_firm: str = None
    recipient_ttn_number: str = None
    recipient_ttn_date: str = None

    @property
    def car_number(self):
        return self._car_number

    @property
    def verified_car_number(self):
        return self._verified_car_number

    @car_number.setter
    def car_number(self, val: str):
        if not isinstance(val, str):
            raise ValueError('Value must be a string')
        self._car_number = val

        numbers = [number.strip() for number in val.split("/")]
        verified = []
        for number in numbers:
            match = any(map(
                lambda regex: re.search(regex, number),
                [CAR_RUS_FULL_REGEX, TRAILERS_RUS_FULL_REGEX, CAR_RUS_MINI_REGEX, TRAILERS_RUS_MINI_REGEX]
            ))
            if match:
                verified.append(number)

        self._verified_car_number = " / ".join(verified)


@dataclass
class EnterpriseDTO:
    pk: int
    name: str
    notifications: List[EnterpriseNotificationDTO] = field(default_factory=lambda: [])
    requests: List[EnterpriseRequestDTO] = field(default_factory=lambda: [])
