# import argparse
import argparse
import os
from server import application

# run the application.
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-l', action='store_true', help='Run the server locally.')
    args, unknown = parser.parse_known_args()
    if args.l:
        os.environ['FLASK_ENV'] = 'development'
        print("local FLASK_ENV set to development")
        print(f"FLASK_ENV: {os.getenv('FLASK_ENV')}")
        application.debug = True
        application.run(host='0.0.0.0',port=8000)    
    else:
        application.run()