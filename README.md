fbconsole
=========

fbconsole is a small facebook api client for use in python scripts.

You can install fbconsole using pip:

    pip install fbconsole


Quick Start Guide
-----------------

**Authentication**

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

**Graph API Basics**

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

