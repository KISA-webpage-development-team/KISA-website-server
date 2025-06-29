# KISA website server

Official repository of the KISA website server.

## Description

The server itself is deployed in the AWS Elastic Beanstalk environment.
This server interacts with the client, (https://umichkisa.com) and the MySQL database
deployed in AWS RDS environment.

## Getting Started

### Dependencies

- Before starting, all dependencies must be installed.
  First, the global environment can be installed through:

```
~/kisaweb-server $ brew install virtualenv mysql-client pkg-config
```

Now, set up a virtual environemt using virtualenv.

```
~/kisaweb-server $ virtualenv virt
```

Now, turn the virtual environment on

```
~/kisaweb-server $ source virt/bin/activate
(virt) ~/kisaweb-server $
```

Install all virtual environment dependencies from the requirements.txt file.

```
(virt) ~/kisaweb-server $ pip install -r requirements.txt
```

### Access API endpoints / testing

- How to run the program

To open a local server on port 8000 (DO NOT FORGET THE -l FLAG):

```
(virt) ~/kisaweb-server $ python application.py -l
```

- Open a browser, and access http://localhost:8000
- Following the base url as above, the routes defined can be accessed from here.

To access endpoints that need bodies or headers specified, use curl...

```
(virt) ~/kisaweb-server $ curl -X POST \
            -H "Content-Type: application/json" \
            -d {"type": "community", "title": "test post" ...} \
            http://localhost:8000/api/v2/posts/
```

- The -X flag stands for the method of the request.
- The -H flag stands for the headers included in the request.
- The -d flag stands for the body included in the request.
- Lastly, the destination api endpoint is specified.
- For more information about curl, see the Ackowledgements.

## Authors

Contributors names and contact info

[@DongsubAidenKim](https://www.linkedin.com/in/aiden-dongsub-kim/)

## Version History

- v1
  - Very first version of the KISAWEB server endpoints.
  - Includes CRUD methods and image handling.
- v2
  - Code has been simplified.
  - Local test database added.
  - Anonymous posts / comments added.
  - Like methods to be implemented in further versions.
- v2.0.1
  - Test database is not local anymore.
  - Test database is in deployed AWS RDS instance, named 'testdb'.
  - Application now automatically generates an environment variable when runned.
  - Based on the environment variable, server will automatically access the appropriate database. When hosted by the local environment, it will access 'testdb', and in the production environment, it will access 'ebdb'.

## Acknowledgments

For your inspiration.

- [curl](https://curl.se/docs/)
- [Flask deployment on EB AWS](https://blog.memcachier.com/2023/09/08/deploy-flask-on-elastic-beanstalk-and-scale-with-memcache/)
- [Flask](https://flask.palletsprojects.com/en/3.0.x/)
- [HTTPS configuration](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/configuring-https-elb.html)
