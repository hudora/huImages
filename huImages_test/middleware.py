#!/usr/bin/env python
# encoding: utf-8
"""
middleware.py tracks clients by setting a persistent coockie.

You can access it via request.clienttrack_uid.

Created by Maximillian Dornseif on 2009-02-07.
Copyright (c) 2009 HUDORA. All rights reserved.
"""

import time
import base64
import hashlib
import random
from django.utils.http import cookie_date

class ClienttrackMiddleware(object):
    def process_request(self, request):
        if '_hda' in request.COOKIES:
            request.clienttrack_first_visit, request.clienttrack_uid =  request.COOKIES.get('_hda').split(',')[:2]
        else:
            request.clienttrack_uid = base64.b32encode(hashlib.md5("%f-%f" % (random.random(), time.time())).digest()).rstrip('=')
            request.clienttrack_first_visit = None
    
    def process_response(self, request, response):
        if not request.clienttrack_first_visit:
                max_age = 3*365*24*60*60  # 3 years
                expires_time = time.time() + max_age
                expires = cookie_date(expires_time)
                response.set_cookie('_hda', "%d,%s" % (time.time(), request.clienttrack_uid),
                                    max_age=max_age, expires=expires)
        return response
