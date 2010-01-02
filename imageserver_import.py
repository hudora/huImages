#!/usr/bin/env python
# encoding: utf-8
"""
imageserver_import.py

Created by Maximillian Dornseif on 2009-01-29.
Copyright (c) 2009 HUDORA. All rights reserved.
"""

import base64
import datetime
import hashlib
import mimetypes
import time
import couchdb.client
import os
import sys
import datetime
from optparse import OptionParser
import huimages

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

