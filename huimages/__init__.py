#!/usr/bin/env python
# encoding: utf-8
"""
imageserver/__init__.py

Store images in couchdb and access them via a separate server.

You are expect to dump images via save_image(), get an ID back and furter on only use
the ID to access the image. You can get the URL of the Image via imageurl(ID) and
scaled_imageurl(ID). You can get a complete XHTML <img> tag via scaled_tag(ID).
    
This module uses the concept of "sizes". A size might be a predefined string
like "thumb" or "svga" or a numeric specification like "240x160". If the numeric
specification ends with "!" (like in "75x75!") the image is scaled and cropped
to be EXACTLY of that size. IF not the image keeps it aspect ratio.

See imageserver._sizes for the list of predefined sizes.

You can use get_random_imageid(), get_next_imageid(ID) and get_previous_imageid(ID)
to implement image browsing.

server.py implements the actual serving of image data.

Created by Maximillian Dornseif on 2009-01-29.
Copyright (c) 2009 HUDORA. All rights reserved.
"""

IMAGESERVER = "http://i.hdimg.net"                   # where server.py is running
COUCHSERVER = "http://couchdb.local.hudora.biz:5984" # where CouchDB is running
COUCHDB_NAME = "huimages"                            # CouchDB database to use

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
from operator import itemgetter
from huTools.async import Future
from huTools.decorators import cache_function

_sizes = {'mini': "23x40",
          'thumb': "50x200", 
          'sidebar': "179x600",
          'small': "240x160",
          'medium': "480x320", 
          'full': "477x800",
          'vga': "640x480", 
          'svga': "800x600", 
          'xvga': "1024x768",
          'square': "75x75!"} 


def _datetime2str(dateobj):
    """Converts a datetime object to a usable string."""
    return "%s.%06d" % (dateobj.strftime('%Y%m%dT%H%M%S'), dateobj.microsecond)
    

def _setup_couchdb():
    """Get a connection handler to the CouchDB Database, creating it when needed."""
    server = couchdb.client.Server(COUCHSERVER)
    if COUCHDB_NAME in server:
        return server[COUCHDB_NAME]
    else:
        return server.create(COUCHDB_NAME)
    

def save_image(imagedata, contenttype=None, timestamp=None, title='', references={}, filename='image.jpeg'):  
    """Stores an Image in the database. Returns the image ID for further image access."""
    db = _setup_couchdb()
    doc_id = "%s01" % base64.b32encode(hashlib.sha1(imagedata).digest()).rstrip('=')
    
    try:
        doc = db[doc_id]
    except couchdb.client.ResourceNotFound:
        doc = {}
    
    if not contenttype:
        contenttype = mimetypes.guess_type(filename)    
    if not timestamp:
        timestamp = _datetime2str(datetime.datetime.now())
    if not 'ctime' in doc:
        doc['ctime'] = timestamp
    doc['mtime'] = timestamp
    if 'product_image' not in doc.get('types', []):
        doc.setdefault('types', []).append('product_image')
    for key, value in references.items():
        if value not in doc.get('references', {}).get(key, []):
            doc.setdefault('references', {}).setdefault(key, []).append(value)
    if title and title not in doc.get('title', []):
        doc.setdefault('title', []).append(title)
        
    db[doc_id] = doc
    if not (doc.get('_attachments')):
        db.put_attachment(db[doc_id], imagedata, filename)
    return doc_id
    

def get_imagedoc(imageid):
    """Get a dictionary describing an Image."""
    db = _setup_couchdb()
    doc = db[imageid]
    return doc
    

def _scale(want_width, want_height, is_width, is_height):
    """
    This function will scale an image to a given bounding box. Image
    aspect ratios will be conserved and so there might be blank space
    at two sides of the image if the ratio isn't identical to that of
    the bounding box.
    
    Returns the size of the final image.
    """
    # from http://simon.bofh.ms/cgi-bin/trac-django-projects.cgi/file/stuff/branches/magic-removal/image.py
    lfactor = 1    
    width, height = int(want_width), int(want_width)
    if is_width > width and is_height > height:
        lfactorx = float(width) / float(is_width)
        lfactory = float(height) / float(is_height)
        lfactor = min(lfactorx, lfactory)
    elif is_width > width:
        lfactor = float(width) / float(is_width)
    elif is_height > height:
        lfactor = float(height) / float(is_height)
    return (int(float(width) * lfactor), int(float(height) * lfactor))
    

def imageurl(imageid, size='o'):
    """Get the URL where the Image can be accessed."""
    return urlparse.urljoin(IMAGESERVER, os.path.join(size, imageid)) + '.jpeg'
    

def scaled_imageurl(imageid, size='square'):
    """Get the URL where a scaled version of the Image can be accessed."""
    return urlparse.urljoin(IMAGESERVER, os.path.join(_sizes.get(size, size), imageid)) + '.jpeg'
    

def scaled_dimensions(imageid, size='square'):
    """Returns the dimensions of an image after scaling."""
    size = _sizes.get(size, size)
    width, height = size.split('x')
    if size.endswith('!'):
        return (int(width), int(height.rstrip('!')))
    # get current is_width and is_height
    try:
        db = _setup_couchdb()
        doc = db[imageid]
        return _scale(width, height, doc.width, doc.height)
    except:
        return (None, None)
    

def scaled_tag(imageid, size='square', *args, **kwargs):
    """Creates an XHTML tag for an Image scaled to <size>.
    
    Additional keyword arguments are added as attributes to  the <img> tag.
    
    >>> img.path_scaled().svga_tag(alt='neu')
    '<img src="http://images.hudora.de/477x600/0eadsaf.jpeg" width="328" height="600" alt="neu"/>'
    """
    ret = ['<img src="%s"' % cgi.escape(scaled_imageurl(imageid, size), True)]
    width, height = scaled_dimensions(imageid, size)
    if width and height:
        ret.append('width="%d" height="%d"' % (width, height))
    ret.extend(args)
    for key, val in kwargs.items():
        ret.append('%s="%s"' % (cgi.escape(key, True), cgi.escape(val, True)))
    ret.append('/>')
    return ' '.join(ret)
    

def get_random_imageid():
    """Returns a random (valid) ImageID."""
    db = _setup_couchdb()
    startkey = base64.b32encode(hashlib.sha1(str(random.random())).digest()).rstrip('=')
    return [x.id for x in db.view('all/without_deleted', startkey=startkey, limit=1)][0]
    

def get_next_imageid(imageid):
    """Get the 'next' ImageID."""
    db = _setup_couchdb()
    return [x.id for x in db.view('_all_docs', startkey=imageid, limit=2)][-1]
    

def get_previous_imageid(imageid):
    """Get the 'previous' ImageID."""
    db = _setup_couchdb()
    return [x.id for x in db.view('_all_docs', startkey=imageid, limit=2, descending=True)][-1]


# Meta-Data related functionality

def set_title(imageid, newtitle):
    """Save an image title."""
    db = _setup_couchdb()
    doc = get_imagedoc(imageid)
    if newtitle and newtitle not in doc.get('title', []):
        doc.setdefault('title', []).append(newtitle)
    db[imageid] = doc
