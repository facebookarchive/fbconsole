#!/usr/bin/env python
#
# Copyright 2010-present Facebook
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import BaseHTTPServer
import cookielib
import httplib
import anyjson as json
import random
import mimetypes
import os
import os.path
import stat
import time
import types
import urllib
import webbrowser
import StringIO
import six
from six import b

poster_is_available = False
try:
    # try to use poster if it is available
    import poster.streaminghttp
    import poster.encode
    poster.streaminghttp.register_openers()
    poster_is_available = True
except ImportError:
    pass # we can live without this.

from urlparse import urlparse
from pprint import pprint

try:
    from urlparse import parse_qs
except ImportError:
    from cgi import parse_qs

if six.PY3:
    import io
    FileType = io.IOBase
else:
    FileType = types.FileType

if six.PY3:
    from urllib.request import build_opener
    from urllib.request import HTTPCookieProcessor
    from urllib.request import BaseHandler
    from urllib.request import HTTPHandler
    from urllib.request import urlopen
    from urllib.request import Request
    from urllib.parse import urlencode
    from urllib.error import HTTPError
else:
    from urllib2 import build_opener
    from urllib2 import HTTPCookieProcessor
    from urllib2 import BaseHandler
    from urllib2 import HTTPHandler
    from urllib2 import urlopen
    from urllib2 import HTTPError
    from urllib2 import Request
    from urllib import urlencode

APP_ID = '179745182062082'
SERVER_PORT = 8080
ACCESS_TOKEN = None
CLIENT = None
ACCESS_TOKEN_FILE = '.fb_access_token'
AUTH_SCOPE = []
BATCH_REQUEST_LIMIT = 50

AUTH_SUCCESS_HTML = """
You have successfully logged in to facebook with fbconsole.
You can close this window now.
"""

__all__ = [
    'help',
    'authenticate',
    'logout',
    'graph_url',
    'oauth_url',
    'Batch',
    'get',
    'post',
    'delete',
    'shell',
    'fql',
    'iter_pages',
    'Client',
    'APP_ID',
    'SERVER_PORT',
    'ACCESS_TOKEN',
    'AUTH_SCOPE',
    'ACCESS_TOKEN_FILE']


class _MultipartPostHandler(BaseHandler):
    handler_order = HTTPHandler.handler_order - 10 # needs to run first

    def http_request(self, request):
        data = request.get_data()
        if data is not None and not isinstance(data, types.StringTypes):
            files = []
            params = []
            try:
                for key, value in data.items():
                    if isinstance(value, FileType):
                        files.append((key, value))
                    else:
                        params.append((key, value))
            except TypeError:
                raise TypeError("not a valid non-string sequence or mapping object")

            if len(files) == 0:
                data = urlencode(params)
                if six.PY3:
                    data = data.encode('utf-8')
            else:
                boundary, data = self.multipart_encode(params, files)
                contenttype = 'multipart/form-data; boundary=%s' % boundary
                request.add_unredirected_header('Content-Type', contenttype)

            request.add_data(data)
        return request

    https_request = http_request

    def multipart_encode(self, params, files, boundary=None, buffer=None):
        if six.PY3:
            boundary = boundary or b('--------------------%s---' % random.random())
            buffer = buffer or b('')
            for key, value in params:
                buffer += b('--%s\r\n' % boundary)
                buffer += b('Content-Disposition: form-data; name="%s"' % key)
                buffer += b('\r\n\r\n' + value + '\r\n')
            for key, fd in files:
                file_size = os.fstat(fd.fileno())[stat.ST_SIZE]
                filename = fd.name.split('/')[-1]
                contenttype = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
                buffer += b('--%s\r\n' % boundary)
                buffer += b('Content-Disposition: form-data; ')
                buffer += b('name="%s"; filename="%s"\r\n' % (key, filename))
                buffer += b('Content-Type: %s\r\n' % contenttype)
                fd.seek(0)
                buffer += b('\r\n') + fd.read() + b('\r\n')
            buffer += b('--%s--\r\n\r\n' % boundary)
        else:
            boundary = boundary or '--------------------%s---' % random.random()
            buffer = buffer or ''
            for key, value in params:
                buffer += '--%s\r\n' % boundary
                buffer += 'Content-Disposition: form-data; name="%s"' % key
                buffer += '\r\n\r\n' + value + '\r\n'
            for key, fd in files:
                file_size = os.fstat(fd.fileno())[stat.ST_SIZE]
                filename = fd.name.split('/')[-1]
                contenttype = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
                buffer += '--%s\r\n' % boundary
                buffer += 'Content-Disposition: form-data; '
                buffer += 'name="%s"; filename="%s"\r\n' % (key, filename)
                buffer += 'Content-Type: %s\r\n' % contenttype
                fd.seek(0)
                buffer += '\r\n' + fd.read() + '\r\n'
            buffer += '--%s--\r\n\r\n' % boundary
        return boundary, buffer


class _RequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):

    def do_GET(self):
        global ACCESS_TOKEN
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()

        params = parse_qs(urlparse(self.path).query)
        ACCESS_TOKEN = params.get('access_token', [None])[0]
        if ACCESS_TOKEN:
            data = {'scope': AUTH_SCOPE,
                    'access_token': ACCESS_TOKEN}
            expiration = params.get('expires_in', [None])[0]
            if expiration:
                if expiration == '0':
                    # this is what's returned when offline_access is requested
                    data['expires_at'] = 'never'
                else:
                    data['expires_at'] = int(time.time()+int(expiration))
            open(ACCESS_TOKEN_FILE,'w').write(json.dumps(data))
            self.wfile.write(b(AUTH_SUCCESS_HTML))
        else:
            self.wfile.write(b('<html><head>'
                               '<script>location = "?"+location.hash.slice(1);</script>'
                               '</head></html>'))

class ApiException(Exception):

    def __init__(self, message, error_type, code):
        super(ApiException, self).__init__(message)
        self.error_type = error_type
        self.code = code

    @staticmethod
    def from_json(data):
        error_type = data.get('type')
        for subclass in ApiException.__subclasses__():
            if subclass.__name__ == error_type:
                return subclass(data.get('message'),
                                data.get('error_type'),
                                data.get('code'))

        return UnknownApiException(data.get('message'),
                                   data.get('error_type'),
                                   data.get('code'))


class UnknownApiException(ApiException):
    """Some unknown error."""

class OAuthException(ApiException):
    """Just an oath exception."""


def _handle_http_error(e):
    body = e.read()
    if six.PY3:
        body = body.decode('utf-8')
    try:
        body = json.loads(body)
    except ValueError:
        pass
    else:
        error = body.get('error')
        if error:
            return ApiException.from_json(error)
    return e

def _safe_url_load(*args, **kwargs):
    """Wrapper around urlopen that translates http errors into nicer exceptions."""
    try:
        return urlopen(*args, **kwargs)
    except HTTPError, e:
        error = _handle_http_error(e)
    raise error

def _safe_json_load(*args, **kwargs):
    f = _safe_url_load(*args, **kwargs)
    if six.PY3:
        return json.loads(f.read().decode('utf-8'))
    else:
        return json.loads(f.read())

def help():
    """Print out some helpful information"""
    print '''
The following commands are available:

help() - display this help message
authenticate() - authenticate with facebook.
logout() - Remove the cached access token, forcing authenticate() to get a new
           access token
graph_url(path, params) - get the full url to a graph api path
get(path, params) - call the graph api with the given path and query parameters
post(path, data) - post data to the graph api with the given path
delete(path, params) - send a delete request
fql(query) - make an fql request
'''

def authenticate():
    """Authenticate with facebook so you can make api calls that require auth.

    Alternatively you can just set the ACCESS_TOKEN global variable in this
    module to set an access token you get from facebook.

    If you want to request certain permissions, set the AUTH_SCOPE global
    variable to the list of permissions you want.
    """
    global ACCESS_TOKEN
    needs_auth = True
    if os.path.exists(ACCESS_TOKEN_FILE):
        data = json.loads(open(ACCESS_TOKEN_FILE).read())
        expires_at = data.get('expires_at')
        still_valid = expires_at and (expires_at == 'never' or expires_at > time.time())
        if still_valid and set(data['scope']).issuperset(AUTH_SCOPE):
            ACCESS_TOKEN = data['access_token']
            needs_auth = False

    if needs_auth:
        webbrowser.open(oauth_url(
                APP_ID,
                'http://127.0.0.1:%s/' % SERVER_PORT, AUTH_SCOPE
                ))

        httpd = BaseHTTPServer.HTTPServer(('127.0.0.1', SERVER_PORT), _RequestHandler)
        while ACCESS_TOKEN is None:
            httpd.handle_request()

def logout():
    """Logout of facebook.  This just removes the cached access token."""
    if os.path.exists(ACCESS_TOKEN_FILE):
        os.remove(ACCESS_TOKEN_FILE)


class _GraphRequest:

    def __init__(self, method, path, params, name, ignore_result):
        self.method = method
        self.path = path
        self.params = params or {}
        self.name = name
        self.ignore_result = ignore_result
        self.result = None
        self.error = None

    def get_result(self):
        if self.error:
            raise self.error
        return self.result

class Batch:
    """A class that lets you batch multiple graph api calls into a single request.

    First we create a new batch instance.

      >>> batch = Batch()

    Then we can start fetching a bunch of stuff by calling
    get/post/delete/etc. on the batch object.  When calling these methods, a
    request object will be returned which can be used to fetch the result of
    that request after the batch has been sent.  By passing in a name, you can
    refer to the results of a previous request in a subsequent request using the
    special syntax defined documented here:
    https://developers.facebook.com/docs/reference/api/batch/

      >>> me = batch.get('/me', name='me')
      >>> coke = batch.get('/cocacola', name='coke')

    If you pass in ignore_result=True when making the request, then no request
    object will be returned and the results will not be passed down from
    facebook.  You can still use the results in other requests using the
    specialized syntax, but facebook won't send the results back.

      >>> image = open("icon.gif", "rb")
      >>> batch.post('/me/photos',
      ...            {'name': '{result=me:$.name} likes {result=coke:$.name}',
      ...             'source': image},
      ...            name='photo',
      ...            ignore_result=True)
      >>> photo = batch.get('/{result=photo:$.id}')

    Now we can send the request:

      >>> batch.send()
      >>> image.close()

    And look at the results:

      >>> print me.get_result()['name']
      David Amcafiaddddh Yangstein

      >>> print coke.get_result()['name']
      Coca-Cola

      >>> print photo.get_result()['name']
      David Amcafiaddddh Yangstein likes Coca-Cola

    If you try to send a batch request twice, it will fail.  You must
    reconstruct a new batch.

      >>> batch.send()
      Traceback (most recent call last):
      ...
      RuntimeError: This batch request has already been sent

    There is also a limit to the number of requests that can be sent in a single
    batch.  Going over this limit will cause an exception to be thrown.

      >>> batch = Batch()
      >>> for i in xrange(BATCH_REQUEST_LIMIT+1):
      ...   batch.get('/me')
      Traceback (most recent call last):
      ...
      RuntimeError: You can't send more than 50 requests in a single batch
    """

    def __init__(self, client=None):
        self.client = client
        self.__api_calls = []
        self.__batch_request_sent = False

    def __add_request(self, request):
        if len(self.__api_calls) >= BATCH_REQUEST_LIMIT:
            raise RuntimeError(
                "You can't send more than %s requests in a single batch" %
                BATCH_REQUEST_LIMIT)
        self.__api_calls.append(request)
        if request.ignore_result:
            return None
        return request

    def get(self, path, params=None, name=None, ignore_result=False):
        return self.__add_request(_GraphRequest('GET',
                                                path[1:],
                                                params,
                                                name,
                                                ignore_result))

    def post(self, path, params=None, name=None, ignore_result=False):
        return self.__add_request(_GraphRequest('POST',
                                                path[1:],
                                                params,
                                                name,
                                                ignore_result))

    def delete(self, path, params=None, name=None, ignore_result=False):
        return self.__add_request(_GraphRequest('DELETE',
                                                path[1:],
                                                params,
                                                name,
                                                ignore_result))

    def fql(self, query, name=None, ignore_result=False):
        return self.__add_request(_GraphRequest('GET',
                                                'fql',
                                                {'q': query},
                                                name,
                                                ignore_result))

    def __build_params(self):
        # See https://developers.facebook.com/docs/reference/api/batch/
        # for documentation on how the batch api is supposed to work.

        batch = []
        all_files = []
        for request in self.__api_calls:
            payload = {'method': request.method}
            if not request.ignore_result:
                payload['omit_response_on_success'] = False
            if request.name:
                payload['name'] = request.name
            if request.method in ['GET', 'DELETE']:
                payload['relative_url'] = request.path+'?'+urlencode(request.params)
            elif request.method == 'POST':
                payload['relative_url'] = request.path
                files = []
                params = {}
                for key, value in request.params.iteritems():
                    if isinstance(value, FileType):
                        all_files.append(value)
                        files.append('file%s' % (len(all_files) - 1))
                    else:
                        params[key] = value
                payload['body'] = urlencode(params)
                payload['attached_files'] = ','.join(files)
            batch.append(payload)

        params = {'batch':json.dumps(batch)}
        for i, f in enumerate(all_files):
            params['file%s' % i] = f

        return params

    def send(self):
        if self.__batch_request_sent:
            raise RuntimeError("This batch request has already been sent")
        self.__batch_request_sent = True

        client = self.client or _get_client()
        responses = client.post('', self.__build_params())

        # process the response
        for request, response in zip(self.__api_calls, responses):
            if response is None:
                # this happens when you use the result in a following request
                continue
            if response['code'] == 200:
                request.result = json.loads(response['body'])
            else:
                request.error = ApiException.from_json(json.loads(response['body'])['error'])


class Client:
    """A class that encapsulates a client for a single access token.

    Using a Client object, you can make requests using different access tokens
    within the same application.

      >>> user1 = Client('AAACjeiZB6FgIBAJhJMaspnA8V06q859FvUJsJtVbEsXpEKOv5H6RIvU7hWU5EgINj5fBPoGlVt0JIkWVYHVemOmehqMyiQFSWDbDq0AZDZD')
      >>> user2 = Client('AAACjeiZB6FgIBAB8eZABg7So8ALDisFLugfIJSZCg3FEDRy82yEmdXYYfNvdv2kWVMWxaJgWqqVMPtG5v5n4lMG5VXmZBZBykQkeluhpFPQZDZD')

      >>> print user1.get('/me')['name']
      David Amcfbdajbbhi Alisonsen
      >>> print user2.get('/me')['name']
      David Amcafiaddddh Yangstein

    """

    def __init__(self, access_token=None):
        self.access_token = access_token

    def __get_url(self, path, args=None):
        args = args or {}
        if self.access_token:
            args['access_token'] = self.access_token
        subdomain = 'graph'
        if '/videos' in path:
            subdomain = 'graph-video'
        if 'access_token' in args or 'client_secret' in args:
            endpoint = "https://%s.facebook.com" % subdomain
        else:
            endpoint = "http://%s.facebook.com" % subdomain
        return endpoint+str(path)+'?'+urlencode(args)

    def get(self, path, params=None):
        return _safe_json_load(self.__get_url(path, args=params))

    def post(self, path, params=None):
        params = params or {}
        if poster_is_available:
            data, headers = poster.encode.multipart_encode(params)
            request = Request(self.__get_url(path), data, headers)
            return _safe_json_load(request)
        else:
            opener = build_opener(
                HTTPCookieProcessor(cookielib.CookieJar()),
                _MultipartPostHandler)
            try:
                return json.loads(opener.open(self.__get_url(path), params).read().decode('utf-8'))
            except HTTPError, e:
                error = _handle_http_error(e)
            raise error

    def delete(self, path, params=None):
        if not params:
            params = {}
        params['method'] = 'delete'
        return post(path, params)

    def fql(self, query):
        url = self.__get_url('/fql', args={'q': query})
        return _safe_json_load(url)['data']

    def graph_url(self, path, params=None):
        return self.__get_url(path, args=params)


def _get_client():
    global CLIENT
    if not CLIENT or CLIENT.access_token != ACCESS_TOKEN:
        CLIENT = Client(ACCESS_TOKEN)
    return CLIENT

def get(path, params=None):
    """Send a GET request to the graph api.

    For example:

      >>> user = get('/me')
      >>> print user['first_name']
      David
      >>> short_user = get('/me', {'fields':'id,first_name'})
      >>> print short_user['id'], short_user['first_name']
      100003169144448 David

    """
    return _get_client().get(path, params=params)

def iter_pages(json_response):
    """Iterate over multiple pages of data.

    The graph api can return a lot of data, but will only return a limited
    amount of data in a single request.  To get more data, you must query for it
    explicitly using paging.  This function will do automatic paging in the form
    of an iterator.  For example to print the id of every photo tagged with the
    logged in user:

      >>> total = 0
      >>> for photo in iter_pages(get('/19292868552/feed', {'limit':2})):
      ...     total += 1
      ...     print "There are at least", total, "feed stories"
      ...     if total > 4: break
      There are at least 1 feed stories
      There are at least 2 feed stories
      There are at least 3 feed stories
      There are at least 4 feed stories
      There are at least 5 feed stories

    """
    while len(json_response.get('data','')):
        for item in json_response['data']:
            yield item
        next_url = json_response['paging']['next']
        json_response = _safe_json_load(next_url)

def post(path, params=None):
    """Send a POST request to the graph api.

    You can also upload files using this function.  For example:

      >>> image = open("icon.gif", "rb")
      >>> photo_id = post('/me/photos',
      ...            {'name': 'My Photo',
      ...             'source': image})['id']
      >>> image.close()
      >>> print get('/'+photo_id)['name']
      My Photo

    Or like an object:

      >>> success = post('/'+photo_id+'/likes')
      >>> print get('/'+photo_id+'/likes')['data'][0]['name']
      David Amcafiaddddh Yangstein

    """
    return _get_client().post(path, params=params)

def delete(path, params=None):
    """Send a DELETE request to the graph api.

    For example:

      >>> msg_id = post('/me/feed', {'message':'hello world'})['id']
      >>> delete('/'+msg_id)
      True

    """
    return _get_client().delete(path, params=params)

def fql(query):
    """Make an fql request.

    For example:

      >>> data = fql('SELECT name FROM user WHERE uid = me()')
      >>> print data[0]['name']
      David Amcafiaddddh Yangstein

    """
    return _get_client().fql(query)

def graph_url(path, params=None):
    """Get the full url to the graph api for the given path and query args.

    This is useful if you want to use your own method of making http requests or
    are not interested in the json parsing that occurs by default. For example,
    download a large profile picture of Mark Zuckerberg:

      >>> url = graph_url('/zuck/picture', {"type":"large"})
      >>> filename, response = urllib.urlretrieve(url, 'mark.jpg')

    """
    return _get_client().graph_url(path, params=params)

def oauth_url(app_id, redirect_uri, auth_scope):
    """Generates a url to an oath authentication dialog.

      >>> print oauth_url(APP_ID, 'http://127.0.0.1:8080/', ['publish_stream'])
      https://www.facebook.com/dialog/oauth?scope=publish_stream&redirect_uri=http%3A%2F%2F127.0.0.1%3A8080%2F&response_type=token&client_id=179745182062082
    """
    return 'https://www.facebook.com/dialog/oauth?' + \
        urlencode({'client_id':app_id,
                   'redirect_uri':redirect_uri,
                   'response_type':'token',
                   'scope':','.join(auth_scope)})


INTRO_MESSAGE = '''\
  __ _                                _
 / _| |                              | |
| |_| |__   ___  ___  _ __  ___  ___ | | ___
|  _| '_ \ / __|/ _ \| '_ \/ __|/ _ \| |/ _ \\
| | | |_) | (__| (_) | | | \__ \ (_) | |  __/
|_| |_.__/ \___|\___/|_| |_|___/\___/|_|\___|

Type help() for a list of commands.
quick start:

  >>> authenticate()
  >>> print "Hello", get('/me')['name']

'''

def shell():
    try:
        from IPython.Shell import IPShellEmbed
        IPShellEmbed()(INTRO_MESSAGE)
    except ImportError:
        import code
        code.InteractiveConsole(globals()).interact(INTRO_MESSAGE)


def test_suite():
    import doctest
    global ACCESS_TOKEN
    ACCESS_TOKEN = 'AAACjeiZB6FgIBAB8eZABg7So8ALDisFLugfIJSZCg3FEDRy82yEmdXYYfNvdv2kWVMWxaJgWqqVMPtG5v5n4lMG5VXmZBZBykQkeluhpFPQZDZD'
    return doctest.DocTestSuite()

if __name__ == '__main__':
    shell()
