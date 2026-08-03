from .base import SiteAdapter, Job
from .eleman import ElemanAdapter
from .isinolsun import IsinolsunAdapter
from .kariyer import KariyerAdapter

ADAPTERS = {
    'eleman': ElemanAdapter,
    'isinolsun': IsinolsunAdapter,
    'kariyer': KariyerAdapter,
}


def get_adapter(name):
    cls = ADAPTERS.get(name)
    return cls() if cls else None
