from googleanalytics.exception import GoogleAnalyticsClientError
from googleanalytics import config
from googleanalytics.account import Account
from xml.etree import ElementTree

import re
import urllib
import urllib2

class GAConnection:
    user_agent = 'python-gapi-v2'
    auth_token = None

    def __init__(self, google_email=None, google_password=None, api_key=None, timeout=10):
        self._timeout = timeout
        authtoken_pat = re.compile(r"Auth=(.*)")
        base_url = 'https://www.google.com'
        path = '/accounts/ClientLogin'
        self._api_key = api_key
        if not all([google_email, google_password, self._api_key]):
            google_email, google_password, self._api_key = config.get_google_credentials()

        data = {
            'accountType': 'GOOGLE',
            'Email': google_email,
            'Passwd': google_password,
            'key': self._api_key,
            'service': 'analytics',
            'source': self.user_agent
        }
        response = self.make_request('POST', base_url, path, data=data)
        auth_token = authtoken_pat.search(response.read())
        self.auth_token = auth_token.groups(0)[0]

    def get_accounts(self, start_index=1, max_results=None):
        if not hasattr(self, '_accounts'):
            self._accounts = []
            base_url = 'https://www.googleapis.com/analytics/v2.4'
            path = '/management/accounts/~all/webproperties/~all/profiles'
            data = {'start-index': start_index}
            if max_results:
                data['max-results'] = max_results
            response = self.make_request('GET', base_url, path, data=data)
            raw_xml = response.read()
            xml_tree = ElementTree.fromstring(raw_xml)
            accounts = xml_tree.getiterator('{http://www.w3.org/2005/Atom}entry')
            for account in accounts:
                account_data = {
                    'title': account.find('{http://www.w3.org/2005/Atom}title').text,
                    'id': account.find('{http://www.w3.org/2005/Atom}id').text,
                    'updated': account.find('{http://www.w3.org/2005/Atom}updated').text,
                }
                for f in account.getiterator('{http://schemas.google.com/analytics/2009}property'):
                    account_data[f.attrib['name']] = f.attrib['value']

                a = Account(
                    connection=self,
                    title=account_data['title'],
                    id=account_data['id'],
                    updated=account_data['updated'],
                    table_id=account_data['dxp:tableId'],
                    account_id=account_data['ga:accountId'],
                    account_name=account_data['ga:profileName'],
                    currency=account_data['ga:currency'],
                    time_zone=account_data['ga:timezone'],
                    profile_id=account_data['ga:profileId'],
                    web_property_id=account_data['ga:webPropertyId'],
                )
                self._accounts.append(a)
        return self._accounts

    def get_account(self, profile_id):
        """Returns an Account object matching the `profile_id` argument."""
        for account in self.get_accounts():
            if account.profile_id == profile_id:
                return account
        raise GoogleAnalyticsClientError("%s is not a valid `profile_id`" % profile_id)

    def make_request(self, method, base_url, path, headers=None, data=''):
        if headers == None:
            headers = {
                'User-Agent': self.user_agent,
                'GData-Version': '2'
            }
            if self.auth_token:
                headers['Authorization'] = 'GoogleLogin auth=%s' % self.auth_token
        else:
            headers = headers.copy()

        data['key'] = self._api_key
        data = urllib.urlencode(data)

        if method == 'GET':
            path = '%s?%s' % (path, data)

        if method == 'POST':
            request = urllib2.Request(base_url + path, data, headers)
        elif method == 'GET':
            request = urllib2.Request(base_url + path, headers=headers)

        try:
            response = urllib2.urlopen(request, timeout=self._timeout)
        except urllib2.HTTPError, e:
            raise GoogleAnalyticsClientError(e)
        return response
