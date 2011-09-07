# fbconsole #

fbconsole is a small facebook api client for use in python scripts.

You can install fbconsole using pip:

    pip install fbconsole


## Quick Start Guide ##


### Authentication ###

For many api calls, you will need to authenticate your script with Facebook.
fbconsole makes this easy by providing an `authenticate` function.  If your
script needs extended permissions, for example to post a status update, you can
specify which extended permissions to request with the AUTH_SCOPE setting.  For
example:

    import fbconsole

    fbconsole.AUTH_SCOPE = ['publish_stream', 'publish_checkins']
    fbconsole.authenticate()

You can find a list of permissions in Facebook's api documentation
[here](https://developers.facebook.com/docs/reference/api/permissions/).

During the authentication process, a browser window will be opened where you can
enter in your facebook login credentials.  After logging in, you can close the
browser window.  Your script will continue executing in the background.


### Graph API Basics ###


You can make HTTP POST requests using the `post` function.  Here is how
you would update your status:

    status = fbconsole.post('/me/feed', {'message':'Hello from my awesome script'})

You can make HTTP GET requests using the `get` function.  Here is how you would
fetch likes on a status update:

    likes = fbconsole.get('/'+status['id']+'/likes')

You can make HTTP DELETE requests using the `delete` function.  Here is how you
would delete a status message:

    fbconsole.delete('/'+status['id'])

To upload a photo, you can profile a file-like object as a post parameter:

    fbconsole.post('/me/photos', {'source':open('my-photo.jpg')})

Finally, you can also make
[FQL](https://developers.facebook.com/docs/reference/fql/) queries using the
`fql` function.  For example:

    friends = fbconsole.fql("SELECT name FROM user WHERE uid IN "
                            "(SELECT uid2 FROM friend WHERE uid1 = me())")


### More Authentication Options ###

By default, fbconsole will make all it's requests as the fbconsole facebook app.
If you want the requests to be made by your own facebook application, you must
modify the APP_ID setting.  For example:

    fbconsole.APP_ID = '<your-app-id>'
    fbconsole.authenticate()

For the authentication flow to work, you must configure your Facebook
application correctly by setting the "Site URL" option to http://127.0.0.1:8080

If you don't want to change your application settings, you can also specify an
access token to use directly, in which case you can skip authentication
altogether:

    fbconsole.ACCESS_TOKEN = '<your-access-token>'


### Other Options ###

There are two other options you can specify.

- `SERVER_PORT` controls which port the local server runs on.  If you modify
     this, make sure your applications settings on Facebook, specifically "Site
     URL", reflect the port number you are using.  The default is 8080.

- `ACCESS_TOKEN_FILE` controls where the access token gets stored on the file
  system.  The default is `.fb_access_token`.


## Feedback ##

For issues pertaining to fbconsole only, use
[the issue tracker on github](https://github.com/facebook/fbconsole/issues).
For issues with the graph api or other aspects of Facebook's platform, please
refer to [the developer docs](https://developers.facebook.com/docs/) and
[the Facebook Platform bug tracker](http://bugs.developers.facebook.net/).


## License Information ##

fbconsole is licensed under the [Apache License, Version
2.0](http://www.apache.org/licenses/LICENSE-2.0.html)
