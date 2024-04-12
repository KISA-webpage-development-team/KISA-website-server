import argparse
from server import application

# run the application.
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-l', action='store_true')
    args = parser.parse_args()
    if args.l:
        application.debug = True
        application.run(host='0.0.0.0',port=8000)    
    else:
        application.run()