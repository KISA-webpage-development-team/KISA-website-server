import cloudinary
import cloudinary.uploader
import cloudinary.api
import server

def init_cloudinary():
    """Initialize Cloudinary configuration"""
    cloudinary.config(
        cloud_name=server.config.CLOUDINARY_CLOUD_NAME,
        api_key=server.config.CLOUDINARY_API_KEY,
        api_secret=server.config.CLOUDINARY_API_SECRET
    )

def delete_existing_menu_image(menu_id):
    """
    Delete an existing image from pocha folder for a specific menu ID
    
    Args:
        menu_id (int): ID of the menu item
    
    Returns:
        bool: True if deletion was successful or no image existed, False if error
    """
    try:
        public_id = f"pocha/menu-{menu_id}"
        
        # Check if image exists
        try:
            result = cloudinary.api.resource(public_id)
            if result:
                # Image exists, delete it
                cloudinary.uploader.destroy(public_id)
                print(f"Deleted existing image: {public_id}")
        except cloudinary.api.NotFound:
            # Image doesn't exist, which is fine
            pass
        
        return True
        
    except Exception as e:
        print(f"Error deleting existing menu image: {e}")
        return False

def move_image_to_pocha_folder(temp_image_url, menu_id, is_update=False):
    """
    Move an image from temp folder to pocha folder with new name
    
    Args:
        temp_image_url (str): URL of the image in temp folder
        menu_id (int): ID of the menu item
        is_update (bool): If True, delete existing image before moving new one
    
    Returns:
        str: New URL of the image in pocha folder, or None if failed
    """
    try:
        # Extract public_id from temp URL
        # Assuming temp URL format: https://res.cloudinary.com/cloud_name/image/upload/v1234567890/temp/image_name.jpg
        if '/temp/' not in temp_image_url:
            return None
            
        # Extract the part after /temp/ and before any transformations
        temp_part = temp_image_url.split('/temp/')[1]
        if '?' in temp_part:
            temp_part = temp_part.split('?')[0]
        
        # Remove file extension if present (Cloudinary public_id doesn't include extension)
        if '.' in temp_part:
            temp_part = temp_part.rsplit('.', 1)[0]
        
        
        # Create new public_id for pocha folder
        new_public_id = f"pocha/menu-{menu_id}"
        
        # If this is an update, delete any existing image first
        if is_update:
            delete_existing_menu_image(menu_id)
        print(f"Deleting existing image: {new_public_id}")
        print(f"Deleting existing image: {temp_part}")
        # Rename the image (this moves it from temp to pocha folder)
        result = cloudinary.uploader.rename(
            f"temp/{temp_part}",
            new_public_id,
            overwrite=True
        )
        
        if result.get('secure_url'):
            return result['secure_url']
        else:
            return None
            
    except Exception as e:
        print(f"Error moving image to pocha folder: {e}")
        return None

def delete_temp_image(temp_image_url):
    """
    Delete an image from temp folder after moving it
    
    Args:
        temp_image_url (str): URL of the image in temp folder
    """
    try:
        if '/temp/' in temp_image_url:
            temp_part = temp_image_url.split('/temp/')[1]
            if '?' in temp_part:
                temp_part = temp_part.split('?')[0]
            
            public_id = f"temp/{temp_part}"
            cloudinary.uploader.destroy(public_id)
    except Exception as e:
        print(f"Error deleting temp image: {e}")