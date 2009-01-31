#!/usr/bin/env python
# encoding: utf-8
"""
untitled.py

Created by Maximillian Dornseif on 2009-01-29.
Copyright (c) 2009 HUDORA. All rights reserved.
"""

import base64
import datetime
import hashlib
import time
import couchdb.client
from django.core import urlresolvers

COUCHSERVER = "http://couchdb.local.hudora.biz:5984"
COUCHDB_NAME = "huImages"
# I'm totally out of ideas how to switch between production and test environments


def _datetime2str(d):
    """Converts a datetime object to a usable string."""
    return "%s.%06d" % (d.strftime('%Y%m%dT%H%M%S'), d.microsecond)
    

def _setup_couchdb():
    """Get a connection handler to the CouchDB Database, creating it when needed."""
    server = couchdb.client.Server(COUCHSERVER)
    if COUCHDB_NAME in server:
        return server[COUCHDB_NAME]
    else:
        return server.create(COUCHDB_NAME)
    
def save_image(imagedata, contenttype=None, timestamp=None, references='', filename='image.jpeg'):
    
    db = _setup_couchdb()
    doc_id = "%s@N1" % base64.b32encode(hashlib.md5(imagedata).digest())
    if not contenttype:
        contenttype = mimetypes.guess_type(filename)
    
    if not timestamp:
        timestamp = datetime.datetime.now()
    doc = {
           'type': 'product_image',
           'timestamp': _datetime2str(timestamp),
          }
    if refereces:
        doc['references'] = references
    # save
    try:
        db[doc_id] = doc
    except couchdb.client.PreconditionFailed:
        # saving failed - update
        newdoc = db[doc_id]
        newdoc.update(doc)
        doc = newdoc
        db[doc_id] = doc
    
    db.put_attachment(db[doc_id], imagedata, filename)
    return doc_id


if __name__ == '__main__':
    unittest.main()