import random
import string
import uuid

from src.config import Config

def upload_images(image):
    if image:
        filename = image.filename
        ext = filename.split('.')[-1]
        filename = generate_random_string() + '.' + ext
        print(filename)
        image.save(Config.IMAGE_PATH + "/" + filename)
        return filename


#generate a random alphanumeric function
def generate_random_string(length=12):
    # Define the characters to choose from (uppercase, lowercase, digits)
    characters = string.ascii_letters + string.digits

    # Generate a random string of the specified length
    random_string = ''.join(random.choice(characters) for _ in range(length))

    return random_string


def generate_strong_password(length=12):
    chars = string.ascii_letters + string.digits + string.punctuation
    return ''.join(random.choice(chars) for _ in range(length))