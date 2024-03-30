import server

# run the app.
if __name__ == "__main__":
    # Setting debug to True enables debug output. This line should be
    # removed before deploying a production app.
    server.app.debug = True
    server.app.run(port=8000)