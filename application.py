from server import application

# run the application.
if __name__ == "__main__":
    # Setting debug to True enables debug output. This line should be
    # removed before deploying a production application.
    application.debug = True
    application.run(host='0.0.0.0',port=8000)

    # production code
    # application.run()