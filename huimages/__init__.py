#!/usr/bin/env python
# encoding: utf-8
"""
imageserver/__init__.py

Store images in couchdb and access them via a separate server.

You are expect to dump images via save_image(), get an ID back and furter on
only use the ID to access the image. You can get the URL of the Image via
imageurl(ID) and scaled_imageurl(ID). You can get a complete XHTML <img> tag
via scaled_tag(ID).

This module uses the concept of "sizes". A size is a numeric specification
like "240x160". If the numeric specification ends with "!" (like in "75x75!")
the image is scaled and cropped to be EXACTLY of that size. IF not the image
keeps it aspect ratio.

You can use get_random_imageid(), get_next_imageid(ID) and
get_previous_imageid(ID) to implement image browsing.

server.py implements the actual serving of image data.

Created by Maximillian Dornseif on 2009-01-29.
Copyright (c) 2009 HUDORA. All rights reserved.
"""

import Image 
import base64
import boto
import boto.s3.connection
import boto.s3.key
import cgi
import couchdb.client
import datetime
import hashlib
import httplib2
import mimetypes
import os
import os.path
import random
import time
import urlparse
from cStringIO import StringIO
from operator import itemgetter

keys = ['S3BUCKET', 'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'IMAGESERVERURL']
for key in keys:
    if key not in os.environ:
        raise RuntimeError("Please set the %r environment variable!" % key)

COUCHSERVER = os.environ.get('COUCHSERVER', 'http://127.0.0.1:5984')
COUCHDB_NAME = "huimages"
# Amazon S3 Bucket where you are storing the original images
S3BUCKET = os.environ['S3BUCKET']
# Your Amazon access credentials
AWS_ACCESS_KEY_ID = os.environ['AWS_ACCESS_KEY_ID']
AWS_SECRET_ACCESS_KEY = os.environ['AWS_SECRET_ACCESS_KEY']
# where server.py is running
IMAGESERVERURL = os.environ.get('IMAGESERVERURL', 'http://i.hdimg.net/')


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
    

def save_image(imagedata, contenttype=None, timestamp=None, title='',
               references=None, filename='image.jpeg', typ=''):
    """Stores an Image in the database. Returns the image ID for further image access.
    
    contenttype should be the Mime-Type of the image or None. If not given the library tries to
    determine the content-type from the filename parameter.
    
    timestamp should be a datetime object representing the creation time of the image or None.
    
    title should be an title for the image.
    
    references can be arbitrary data e.g. referencing an article number.
    
    filename can be the original name of the file.
    
    typ can be the type of the image. So far only 'product_image' is used.
    """
    
    db = _setup_couchdb()
    # the '01' postfix can later used to idnetify the cluster the image is stored on
    doc_id = "%s01" % base64.b32encode(hashlib.sha1(imagedata).digest()).rstrip('=')
    
    try:
        doc = db[doc_id]
    except couchdb.client.ResourceNotFound:
        doc = {}
    
    if not contenttype:
        contenttype = mimetypes.guess_type(filename)
        if len(contenttype) == 2:
            contenttype = contenttype[0]
    if not timestamp:
        timestamp = _datetime2str(datetime.datetime.now())
    if not 'ctime' in doc:
        doc['ctime'] = timestamp
    doc['mtime'] = timestamp
    if typ and (typ not in doc.get('types', [])):
        doc.setdefault('types', []).append(typ)
    if references:
        for key, value in references.items():
            if value not in doc.get('references', {}).get(key, []):
                doc.setdefault('references', {}).setdefault(key, []).append(value)
    if title and title not in doc.get('title', []):
        doc.setdefault('title', []).append(title)
    img = Image.open(StringIO(imagedata))
    doc['width'], doc['height'] = img.size
    
    db[doc_id] = doc
    if not (doc.get('_attachments')):
        db.put_attachment(db[doc_id], imagedata, filename)
    
    # Push data into S3 if needed
    conn = boto.connect_s3()
    s3bucket = conn.get_bucket(S3BUCKET)
    k = s3bucket.get_key(doc_id)
    if not k:
        headers = {}
        headers['Content-Type'] = contenttype
        k = boto.s3.key.Key(s3bucket)
        k.key = doc_id 
        k.set_metadata('width', str(doc['width']))
        k.set_metadata('height', str(doc['height']))
        k.set_contents_from_string(imagedata, headers, replace=True)
        k.make_public()
    
    return doc_id
    

def delete_image(imageid):
    """Deletes an image and all associated data."""
 
    # delete in CouchDB
    db = _setup_couchdb()
    try:
        doc = db[imageid]
        db.delete(doc)
    except couchdb.client.ResourceNotFound:
        pass
    # Push data into S3 if needed
    conn = boto.connect_s3()
    s3bucket = conn.get_bucket(S3BUCKET)
    k = s3bucket.get_key(imageid)
    if k:
        k.delete()


def get_imagedoc(imageid):
    """Get a dictionary describing an Image."""
    db = _setup_couchdb()
    doc = db[imageid]
    return doc
    

def get_length(imageid):
    """Get the length in bytes of an unmodified image."""
    doc = get_imagedoc(imageid)
    attachment = doc['_attachments'][doc['_attachments'].keys()[0]]
    return attachment['length']
    

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
    want_width, want_height = int(want_width), int(want_height)
    if is_width > want_width and is_height > want_height:
        lfactorx = float(want_width) / float(is_width)
        lfactory = float(want_height) / float(is_height)
        lfactor = min(lfactorx, lfactory)
    elif is_width > want_width:
        lfactor = float(want_width) / float(is_width)
    elif is_height > want_height:
        lfactor = float(want_height) / float(is_height)
    return (int(float(is_width) * lfactor), int(float(is_height) * lfactor))
    

def imageurl(imageid, size='o'):
    """Get the URL where the Image can be accessed."""
    return urlparse.urljoin(IMAGESERVERURL, os.path.join(size, imageid)) + '.jpeg'
    

def scaled_imageurl(imageid, size='150x150'):
    """Get the URL where a scaled version of the Image can be accessed."""
    return urlparse.urljoin(IMAGESERVERURL, os.path.join(_sizes.get(size, size), imageid)) + '.jpeg'
    

def scaled_imagedata(imageid, size='150x150'):
    """Returns the datasteream of a scaled image."""
    url = scaled_imageurl(imageid, size)
    http = httplib2.Http()
    response, content = http.request(url, 'GET')
    if str(response.status) == '200':
        return content
    else:
        return None


def scaled_dimensions(imageid, size='150x150'):
    """Returns the dimensions of an image after scaling."""
    size = _sizes.get(size, size)
    width, height = size.split('x')
    if size.endswith('!'):
        return (int(width), int(height.rstrip('!')))
    # get current is_width and is_height
    try:
        db = _setup_couchdb()
        doc = db[imageid]
        return _scale(width, height, doc['width'], doc['height'])
    except:
        raise
        return (None, None)
    

def scaled_tag(imageid, size='150x150', *args, **kwargs):
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
    if 'alt' not in kwargs:
        ret.append('alt=""')
    ret.append('/>')
    return ' '.join(ret)
    

def get_random_imageid():
    """Returns a random (valid) ImageID."""
    db = _setup_couchdb()
    startkey = base64.b32encode(hashlib.sha1(str(random.random())).digest()).rstrip('=')
    return [x.id for x in db.view('all/without_deleted_and_automatic', startkey=startkey, limit=1)][0]
    

def get_next_imageid(imageid):
    """Get the 'next' ImageID."""
    db = _setup_couchdb()
    return [x.id for x in db.view('_all_docs', startkey=imageid, limit=2)][-1]
    

def get_previous_imageid(imageid):
    """Get the 'previous' ImageID."""
    db = _setup_couchdb()
    return [x.id for x in db.view('_all_docs', startkey=imageid, limit=2, descending=True)][-1]


# Meta-Data related functionality

def update_metadata(doc_id, timestamp=None, title='', references=None, typ=''):
    """Updates metadata for an image.
    
    timestamp should be a datetime object representing the creation time of the image or None.
    
    title should be an title for the image.
    
    references can be arbitrary data e.g. referencing an article number.
    
    typ can be the type of the image. So far only 'product_image' is used.
    """
    db = _setup_couchdb()
    doc = db[doc_id]
    
    if timestamp:
        timestamp = _datetime2str(datetime.datetime.now())
        doc['mtime'] = timestamp
        if 'ctime' not in doc:
            doc['ctime'] = timestamp
    
    if typ and (typ not in doc.get('types', [])):
        doc.setdefault('types', []).append(typ)
    if title and title not in doc.get('title', []):
        doc.setdefault('title', []).append(title)
    
    if references:
        for key, value in references.items():
            if value not in doc.get('references', {}).get(key, []):
                doc.setdefault('references', {}).setdefault(key, []).append(value)
    
    db[doc_id] = doc
    return doc_id
    

def set_title(imageid, newtitle):
    """Save an image title."""
    db = _setup_couchdb()
    doc = get_imagedoc(imageid)
    if newtitle and newtitle not in doc.get('title', []):
        doc.setdefault('title', []).append(newtitle)
    db[imageid] = doc
