from app.sources import SourceAdapter
from app.sources.demo import DemoAdapter

REGISTRY: dict[str, type[SourceAdapter]] = {
    DemoAdapter.code: DemoAdapter,
    # "rad_rss": RadRssAdapter,
    # "orsha_ecokarta": OrshaAdapter,
}
