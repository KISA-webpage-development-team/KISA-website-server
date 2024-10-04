from server import application
from server import args

# run the application.
if __name__ == "__main__":
    if args.l:
        print("Local server is running ...")
        application.debug = True
        application.run(host='0.0.0.0',port=8000)    
    else:
        application.run()