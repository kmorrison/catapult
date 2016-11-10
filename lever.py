import logging
import json
import urllib2
import urllib3

import requests

import secret

logger = logging.getLogger(__name__)

class LeverClient(object):

    def _make_lever_request(self, relative_url, data=None):
        passman = urllib2.HTTPPasswordMgrWithDefaultRealm()
        passman.add_password(
            None,
            secret.lever_api_path,
            secret.lever_api_key,
            '',
        )
        authhandler = urllib2.HTTPBasicAuthHandler(passman)
        opener = urllib2.build_opener(authhandler)
        urllib2.install_opener(opener)
        try:
            pagehandle = urllib2.urlopen(
                secret.lever_api_path + relative_url,
            )
        except Exception as e:
            exc_str = 'error reading from lever %s' % relative_url
            logger.exception(exc_str)
            print e
            return '{}'
        return pagehandle.read()

    def _make_lever_request2(self, path, fields=None):
        headers = urllib3.util.make_headers(basic_auth='%s:' % secret.lever_api_key)
        from urllib3.contrib.appengine import AppEngineManager
        http = AppEngineManager()
        response = http.request(
            'GET',
            secret.lever_api_path + path,
            fields=fields,
            headers=headers,
        )
        return json.loads(response.data)

    def _post_to_lever(self, url, perform_as, data):
        try:
            return requests.post(
                secret.lever_api_path + url + '?perform_as=' + perform_as + '&dedupe=true',
                data=json.dumps(data),
                headers={'Content-Type': 'application/json'},
                auth=(secret.lever_api_key, ''),
            ).json()

        except Exception as e:
            print e
            return '{}'

    def get_posting(self, posting_id):
        try:
            return requests.get(
                secret.lever_api_path + '/postings/' + posting_id,
                auth=(secret.lever_api_key, ''),
            ).json()

        except Exception as e:
            print e
            return '{}'

    def get_all_postings(self, team_name):
        postings = []
        offset = None
        while True:
            params = dict(
                team=team_name,
            )
            if offset is not None:
                params['offset'] = offset
            posting_slice = requests.get(
                secret.lever_api_path + '/postings',
                params=params,
                auth=(secret.lever_api_key, ''),
            ).json()
            postings.extend(posting_slice['data'])
            if posting_slice['hasNext']:
                offset = posting_slice['next']
            else:
                return postings

    def get_user(self, user_id):
        user_resp = self._make_lever_request2(
            '/users/%s' % (user_id,),
        )
        return user_resp['data']

    def get_candidate(self, candidate_id):
        candidate_resp = self._make_lever_request2(
            '/candidates/%s' % (candidate_id,),
        )
        return candidate_resp['data']

    def get_candidate_feedback(self, candidate_id):
        feedbacks = []
        offset = None
        params = {}
        while True:
            """
            params = dict(
                team=team_name,
            )
            """
            if offset is not None:
                params['offset'] = offset
            feedback_slice = self._make_lever_request2(
                '/candidates/%s/feedback' % (candidate_id,),
                fields=params,
            )
            feedbacks.extend(feedback_slice['data'])
            if feedback_slice['hasNext']:
                offset = feedback_slice['next']
            else:
                return feedbacks


if __name__ == '__main__':
    eliason_morrison = 'faf06fcf-8a9f-494b-9b7d-893d05a2f2fa'
    posting = '89a3bac3-b5bb-4e87-893e-cc92ab4a0c22'
    tags = ['Testing', 'Test in show', 'Testerfield']

    client = LeverClient()
    """
    resp = client._post_to_lever('/candidates', eliason_morrison, dict(
        name='Testy Testerson',
        headline='',
        location='Testville',
        emails=['eli@yelp.com'],
        tags=tags,
        #origin='My Fair Lady',
        owner=eliason_morrison,
        postings=[posting],
    ))
    """
    #print client.get_posting(posting)['data']['owner']
    resp =  client.get_candidate_feedback('1b25d45c-c68e-4a29-9610-a8d34afe0eb2')
    #resp = client.get_all_postings('College Engineering & Product')
    print len(resp)
