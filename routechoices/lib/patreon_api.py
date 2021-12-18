import json
import requests


class PatreonAPI:
    def __init__(self, access_token):
        super().__init__()
        self.access_token = access_token

    def fetch_user(self):
        return self.__get_json('current_user')

    def fetch_campaign_and_patrons(self):
        return self.__get_json('current_user/campaigns?include=rewards,creator,goals,pledges')

    def __get_json(self, suffix):
        request = requests.get(
            f'https://api.patreon.com/oauth2/api/{suffix}',
            headers={'Authorization': f'Bearer {self.access_token}'}
        )
        return request.json()
