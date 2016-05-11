# KidQuestServer

KidQuestServer is the server back-end of the KidQuest application. 
This has been created as the software artefact contribution to my BSc (Hons) Software Engineering degree.

## Setup

The server can be run by running the following command in the project root folder:

```bash
python3 server.py
```

As long as this command is running, the API will be available on port 5000 of the machine, and will be accessible at http://<ServerIP>:5000/api/ 

The script will automatically create a database file if it cannot find one, this will be named app.sqlite.
Please view the applications README file on how to connect the application to the newly created instance of the server.

### Dependencies

A list of dependencies for the server code can be found in the requirements.txt file.

These can be installed easily using pip by running the following command in the project root folder:

```bash
sudo pip3 install -r requirements.txt
```

Note: A hosted instance of KidQuestServer will be maintained until June 10th for the benefit of examiners at http://kitari.ddns.net:5000/api/
 
No changes will be made to server code, but uptime will be monitored. 
It is highly recommended that no real data is used on the default instance of the server due to the ethical concerns of this project. 
Email verification has not been implemented to allow the use of fake email addresses when registering to the service (Though they must still meet the format of a valid email address.)
