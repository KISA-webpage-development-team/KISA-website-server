import server
import base64
import boto3
import io
import datetime

def handle_imgs(body, postid, prev_text=""):
    # Starting array for new body text
    srcs = body['text'].split("<img src=")
    new_body_text = [srcs[0]]
    img_index = 0
    s3 = boto3.client('s3')
    cloudfront = boto3.client('cloudfront')

    # Extract the keys of the images that were uploaded before
    if len(prev_text) > 0 and "<img src=" in prev_text:
        prev_uploaded_keys = set()
        already_uploaded_keys = set()
        max_img_index = 0

        for prev_img_src in prev_text.split("<img src=")[1::]:
            prev_uploaded_keys.add(
                prev_img_src.split(server.config.CLOUDFRONT_URL + "/")[1].split("\"")[0]
            )
            max_img_index = int(
                prev_img_src.split(server.config.CLOUDFRONT_URL + "/images/")[1]
                .split("_")[2]
                .split(".")[0]
                )
    
        # Index for image per post is +1 of the max index of the previous images
        img_index = max_img_index + 1

        # Extract the keys of the images that are left in the new body
        for img_src in srcs[1::]:
            if server.config.CLOUDFRONT_URL in img_src:
                already_uploaded_keys.add(
                    img_src.split(server.config.CLOUDFRONT_URL + "/")[1].split("\"")[0]
                )

        # Delete images that are not in the new body text
        for key in prev_uploaded_keys - already_uploaded_keys:
            try:
                # Invalidate CloudFront cache for the specific object
                invalidate_paths = [f"/{key}"]
                cloudfront.create_invalidation(
                    DistributionId='E1S1VP7DQ3SUMS',
                    InvalidationBatch={
                        'Paths': {
                            'Quantity': len(invalidate_paths),
                            'Items': invalidate_paths
                        },
                        'CallerReference': str(datetime.datetime.now())
                    }
                )
                s3.delete_object(
                    Bucket='kisaweb-cdn-bucket',
                    Key=key
                )
            except Exception as e:
                print(f"Failed to delete image: {str(e)}")
            
    # Handle text of request body (from add, edit)
    for img_src in srcs[1::]:
        # If the image is already uploaded, do not upload again
        # Leave the chunk as it is and append it to the new body text
        if server.config.CLOUDFRONT_URL in img_src:
            new_body_text.append(img_src)

        # If the image is not uploaded yet, upload the image
        else:
            # Extract the base64 string and extension of the image
            image_base_64 = img_src.split(",")[1].split("\"")[0]
            extension = img_src.split("/")[1].split(";")[0]

            # Decode the base64 string and compose the image key and URL
            img_data = base64.b64decode(image_base_64)
            img_key = f"post_{postid}_{img_index}.{extension}"
            img_url = f"{server.config.CLOUDFRONT_URL}/images/{img_key}"

            try:
                # Upload image data directly from memory (BytesIO)
                with io.BytesIO(img_data) as f:
                    s3.upload_fileobj(f, 'kisaweb-cdn-bucket', f"images/{img_key}")

                # Append new image tag with updated URL
                rest = "\"".join(img_src.split("\"")[2:])
                new_body_text.append(f"\"{img_url}\"{rest}")
                img_index += 1

            except Exception as e:
                print(f"Failed to upload image: {str(e)}")
    
    body['text'] = "<img src=".join(new_body_text)

def delete_imgs(text):
    if "<img src=" in text:
        s3 = boto3.client('s3')
        cloudfront = boto3.client('cloudfront')

        for img_src in text.split("<img src=")[1::]:
            key = img_src.split(server.config.CLOUDFRONT_URL + "/")[1].split("\"")[0]
            try:
                # Invalidate CloudFront cache for the specific object
                invalidate_paths = [f"/{key}"]
                cloudfront.create_invalidation(
                    DistributionId='E1S1VP7DQ3SUMS',
                    InvalidationBatch={
                        'Paths': {
                            'Quantity': len(invalidate_paths),
                            'Items': invalidate_paths
                        },
                        'CallerReference': str(datetime.datetime.now())
                    }
                )
                s3.delete_object(
                    Bucket='kisaweb-cdn-bucket',
                    Key=key
                )
            except Exception as e:
                print(f"Failed to delete image: {str(e)}")