from locust import HttpUser, task, between
import logging
import json

class QuickstartUser(HttpUser):
    wait_time = between(1, 2)

    def __init__(self, parent):
        super(QuickstartUser, self).__init__(parent)
        logging.info("Logging in...")
        self.token = ""
        self.headers = {}
        self.client.headers.update({"Authorization":"Basic cndlcjp3ZXJ3ZXI="})
        self.client.headers.update({"Accept":"application/json"})
        self.client.headers.update({"X-Track-Caller":"4324"})
        self.client.headers.update({"x-track-Session-id":"4324"})

        # response = self.client.get("/api/simple-example/0x20/basic-auth/0x20/login")
        # print(json.loads(response._content))

        self.token = self.login()
        self.client.headers.update({'Authorization': 'Bearer ' + self.token})

    def login(self):
          response = self.client.get("/api/simple-example/0x20/basic-auth/0x20/login")
          return json.loads(response._content)['access_token']

    @task(1)
    def hello_query_something(self):
        self.client.get("/api/simple-example/0x20/query-something?item_id=p_id")
