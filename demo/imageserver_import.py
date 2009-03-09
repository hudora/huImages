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
import mimetypes
import time
import couchdb.client

COUCHSERVER = "http://couchdb.local.hudora.biz:5984"
COUCHDB_NAME = "huimages"
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
    
def save_image(imagedata, contenttype=None, timestamp=None, title='', references={}, filename='image.jpeg'):    
    db = _setup_couchdb()
    doc_id = "%s01" % base64.b32encode(hashlib.sha1(imagedata).digest()).rstrip('=')

    try:
        doc = db[doc_id]
    except couchdb.client.ResourceNotFound:
        doc = {}

    if not contenttype:
        contenttype = mimetypes.guess_type(filename)    
    if not timestamp:
        timestamp = datetime.datetime.now()
    if hasattr(timestamp, 'strftime'):
        timestamp = _datetime2str(datetime.datetime.now())

    if not 'ctime' in doc:
        doc['ctime'] = timestamp
    doc['mtime'] = timestamp
    for key, value in references.items():
        if value not in doc.get('references', {}).get(key, []):
            doc.setdefault('references', {}).setdefault(key, []).append(value)
    if title and title not in doc.get('title', []):
        doc.setdefault('title', []).append(title)
        
    db[doc_id] = doc
    print db[doc_id]
    if not (doc.get('_attachments')):
        db.put_attachment(db[doc_id], imagedata, filename.lstrip('./'))
    return doc_id


import os
import sys
import datetime
from optparse import OptionParser


def parse_commandline():
    """Parse the commandline and return information."""
    
    parser = OptionParser(version=True)
    parser.set_usage('usage: %prog [options] filename [filename]. Try %prog --help for details.')    
    parser.add_option('--artnr', action='store', type='string')
    parser.add_option('--title', action='store', type='string')
    options, args = parser.parse_args()
    
    print vars(options)
    if len(args) < 1:
        parser.error("incorrect number of arguments")
    return options, args
    

options, args = parse_commandline()

# save_image(i.path.read(), references={"artnr": i.product.artnr}, title=i.title, filename=filename)    
ref={}
if options.artnr:
    ref['artnr'] = options.artnr 
for name in args:
    print name
    print save_image(open(name).read(), references=ref, title=options.title, filename=name,
                     timestamp=datetime.datetime.utcfromtimestamp(os.stat(name).st_mtime))

