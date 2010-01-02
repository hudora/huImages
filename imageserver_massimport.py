#!/usr/bin/env python
# encoding: utf-8
"""
untitled.py

Created by Maximillian Dornseif on August 2006.
Copyright (c) 2006, 2009 HUDORA. All rights reserved.
"""


import Image 
import base64
import cgi
import couchdb.client
import datetime
import hashlib
import md5
import mimetypes
import os
import os.path
import random
import time
import urlparse
import os
from os.path import join, getsize
import re
import huimages


COUCHDB_NAME = "huimages"
COUCHSERVER = "http://couchdb.local.hudora.biz:5984"
IMAGESERVER = "http://i.hdimg.net"


def main(startpath):
    for root, dirs, files in os.walk(startpath):
        print "#", root
        for filenameraw in files:
            filename = re.sub('[^\x00-\x7f]+', '_', filenameraw)
            if filename.lower().endswith('jpeg') \
                or filename.lower().endswith('jpg'):
                #or file.lower().endswith('tiff') \
                #or file.lower().endswith('tif'):
                if 'mobotix' in filename or filename.startswith('.'):
                    continue
                filepath = os.path.join(root, filenameraw)
                print filepath, filename
                try:
                    print huimages.save_image(open(filepath).read(),
                        timestamp=datetime.datetime.utcfromtimestamp(os.stat(filepath).st_mtime),
                        title=filename,
                        references={'path': re.sub('[^\x00-\x7f]+', '_', root)}, filename=filename)
                except Exception, msg:
                    print "*error*", msg

main('/tank/archive/Bilder/')
#main('/tank/fileserver/intranet3')
