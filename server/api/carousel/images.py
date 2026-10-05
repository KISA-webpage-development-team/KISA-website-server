"""Cloudinary operations for carousel item images.

Each item owns exactly one image, at carousel/item-{id}. The image's version is
stored on the row and goes into its URL, so a replaced image gets a new URL
rather than a stale cached one.
"""
import cloudinary
import cloudinary.uploader
import cloudinary.utils

TEMP_PREFIX = "temp/"

# Long edge cap for served images, matching the carousel images the site used
# to serve from public/.
DISPLAY_WIDTH = 1600


def item_public_id(item_id):
    return f"carousel/item-{item_id}"


def claim_temp_image(temp_public_id, item_id):
    """Move an upload from temp/ onto the item's image. Returns the new version."""
    result = cloudinary.uploader.rename(
        temp_public_id, item_public_id(item_id), overwrite=True, invalidate=True
    )
    return result["version"]


def copy_image(source_public_id, source_version, item_id):
    """Copy another item's image onto this item's image. Returns the new version."""
    source_url, _ = cloudinary.utils.cloudinary_url(
        source_public_id, version=source_version, secure=True
    )
    result = cloudinary.uploader.upload(
        source_url, public_id=item_public_id(item_id), overwrite=True, invalidate=True
    )
    return result["version"]


def delete_image(public_id):
    cloudinary.uploader.destroy(public_id, invalidate=True)


def image_url(public_id, version):
    url, _ = cloudinary.utils.cloudinary_url(
        public_id,
        version=version,
        secure=True,
        fetch_format="auto",
        quality="auto",
        width=DISPLAY_WIDTH,
        crop="limit",
    )
    return url
