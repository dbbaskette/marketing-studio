"""Blog Studio's check of a brand skill repository's address, which the shared brand
source asks for as `settings.check_repository`: the shared settings' own check
(`studios_config.check_brand_repository`)."""

from studios_config import check_brand_repository


def check_repository(value):
    return check_brand_repository(value)
