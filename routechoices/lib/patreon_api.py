import json
import urllib.request


class PatreonAPI(object):
    def __init__(self, access_token):
        super(PatreonAPI, self).__init__()
        self.access_token = access_token

    def fetch_user(self):
        return self.__get_json('current_user')

    def fetch_campaign_and_patrons(self):
        return self.__get_json('current_user/campaigns?include=rewards,creator,goals,pledges')

    def __get_json(self, suffix):
        url = "https://api.patreon.com/oauth2/api/{}".format(suffix)
        headers = {'Authorization': "Bearer {}".format(self.access_token)}
        request = urllib.request.Request(url, headers=headers)
        contents = urllib.request.urlopen(request).read()
        return json.loads(contents)
