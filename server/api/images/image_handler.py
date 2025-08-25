import server
import os
from ..helpers import extract_temp_keys, extract_uploaded_keys, replace_temp_srcs

def upload_imgs(text, postid):
    """
    Uploads images in a text
    """
    # Base url for images for display on editor is a s3 url
    temp_keys = extract_temp_keys(text)
        
    # Construct list of new scrs
    new_urls = []
    for i, temp_key in enumerate(temp_keys):
        extension = temp_key.split(".")[-1]
        directory = "test_images" if os.getenv("FLASK_ENV") == 'development' else "images"
        new_urls.append(
            f"{os.getenv('CLOUDFRONT_URL')}/{directory}/post_{postid}_{i}.{extension}"
        )

    # Initiate AWS clients
    client = server.model.AWSClient()

    # Locate s3 images with the keys and move them to '/images', with new keys
    for temp_key, new_url in zip(temp_keys, new_urls):
        # Construct new key
        new_key = new_url.split(f"{os.getenv('CLOUDFRONT_URL')}/")[1]

        client.move_object(temp_key, new_key)
    
    # return modified text to upper scope
    return replace_temp_srcs(text, new_urls)


def update_imgs(new_text, prev_text, postid):
    """
    Handle image upload and deletion according to the new and previous text
    """
    # Extract key information from the previous and new text
    # existing_keys = set(extract_keys(prev_text))
    print("prev_text:" , prev_text)

    existing_keys = set(extract_uploaded_keys(prev_text))

    print("existing_keys:", existing_keys)
    remaining_keys = set(extract_uploaded_keys(new_text))
    keys_to_delete = list(existing_keys - remaining_keys)
    keys_to_move = extract_temp_keys(new_text)
    no_image_prev_text = not bool(existing_keys)
    no_image_new_text = not bool(remaining_keys)

    # case 1. no image in the original post && no new image added
    if(no_image_prev_text and no_image_new_text):
        return new_text

    # Delete the images that does not remain in the new text anymore
    client = server.model.AWSClient()
    if keys_to_delete:
        client.delete_uploaded_objects(keys_to_delete)

    # Find maximum index of the images in the previous text
    max_index = max(int(key.split('/')[1].split('_')[2].split('.')[0]) for key in existing_keys)

    # Index for new images starts from +1 the max index
    new_img_index = max_index + 1

    # Move the temp images in the new text to the permanent folder
    # Construct list of new scrs
    new_urls = []
    for i, key in enumerate(keys_to_move, start=new_img_index):
        extension = key.split(".")[-1]
        directory = "test_images" if os.getenv("FLASK_ENV") == 'development' else "images"
        new_urls.append(
            f"{os.getenv('CLOUDFRONT_URL')}/{directory}/post_{postid}_{i}.{extension}"
        )

    # Locate s3 images with the keys and move them to '/images', with new keys
    for temp_key, new_url in zip(keys_to_move, new_urls):
        # Construct new key
        new_key = new_url.split(f"{os.getenv('CLOUDFRONT_URL')}/")[1]

        # Move the image
        client.move_object(temp_key, new_key)

    # return modified text to upper scope
    return replace_temp_srcs(new_text, new_urls)

def delete_imgs(text):
    """
    Delete image files that were uploaded to the s3 bucket
    """
    # Initiate AWS clients
    client = server.model.AWSClient()

    # Extract the keys of the images that were uploaded before
    keys_to_delete = extract_uploaded_keys(text)

    # Delete the images
    if keys_to_delete:
        client.delete_uploaded_objects(keys_to_delete)