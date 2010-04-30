#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Serving of Images from CouchDB or Amazon S3 with scaling.

Is meant to run with lighttpd for fast serving and cache friendly headers.
/etc/lighttpd/lighttpd.conf should look like examples/lighttpd.conf

If you start getting low on disk space, delete the oldest files in
/usr/local/huImages/cache/
"""

# Created 2006, 2009 by Maximillian Dornseif. Consider it BSD licensed.

import Image
import boto
import boto.s3.connection
import boto.s3.key
import couchdb.client
import os
import os.path
import re
import tempfile
from wsgiref.simple_server import make_server
from flup.server.fcgi_fork import WSGIServer

# This tool needs keeys being set at the shell:
# export AWS_ACCESS_KEY_ID='AKIRA...Z'
# export AWS_SECRET_ACCESS_KEY='hal6...7'

S3BUCKET = os.environ.get('HUIMAGES3BUCKET',
                          os.environ.get('S3BUCKET', 'originals.i.hdimg.net'))
COUCHSERVER = os.environ.get('HUIMAGESCOUCHSERVER',
                             os.environ.get('COUCHSERVER', 'http://127.0.0.1:5984'))
CACHEDIR = os.path.abspath('../cache')
COUCHDB_NAME = "huimages"
typ_re = re.compile('^(o|\d+x\d+!?)$')
docid_re = re.compile('^[A-Z0-9]+$')


def _scale_image(width, height, image):
    """
    This function will scale an image to a given bounding box. Image
    aspect ratios will be conserved and so there might be blank space
    at two sides of the image if the ratio isn't identical to that of
    the bounding box.
    """
    # originally from
    # http://simon.bofh.ms/cgi-bin/trac-django-projects.cgi/file/stuff/branches/magic-removal/image.py
    lfactor = 1
    width, height = int(width), int(height)
    (xsize, ysize) = image.size
    if xsize > width and ysize > height:
        lfactorx = float(width) / float(xsize)
        lfactory = float(height) / float(ysize)
        lfactor = min(lfactorx, lfactory)
    elif xsize > width:
        lfactor = float(width) / float(xsize)
    elif ysize > height:
        lfactor = float(height) / float(ysize)
    res = image.resize((int(float(xsize) * lfactor), int(float(ysize) * lfactor)), Image.ANTIALIAS)
    return res


def _crop_image(width, height, image):
    """
    This will crop the largest block out of the middle of an image
    that has the same aspect ratio as the given bounding box. No
    blank space will be in the thumbnail, but the image isn't fully
    visible due to croping.
    """
    # origially from
    # http://simon.bofh.ms/cgi-bin/trac-django-projects.cgi/file/stuff/branches/magic-removal/image.py
    width, height = int(width), int(height)
    lfactor = 1
    (xsize, ysize) = image.size
    if xsize > width and ysize > height:
        lfactorx = float(width) / float(xsize)
        lfactory = float(height) / float(ysize)
        lfactor = max(lfactorx, lfactory)
    newx = int(float(xsize) * lfactor)
    newy = int(float(ysize) * lfactor)
    res = image.resize((newx, newy), Image.ANTIALIAS)
    leftx = 0
    lefty = 0
    rightx = newx
    righty = newy
    if newx > width:
        leftx += (newx - width) / 2
        rightx -= (newx - width) / 2
    elif newy > height:
        lefty += (newy - height) / 2
        righty -= (newy - height) / 2
    res = res.crop((leftx, lefty, rightx, righty))
    return res


def mark_broken(doc_id):
    """If there is a Problem with an Image, mark it as broken (deleted) in the Database."""
    db = couchdb.client.Server(COUCHSERVER)[COUCHDB_NAME]
    doc = db[doc_id]
    doc['deleted'] = True
    db[doc_id] = doc


def imagserver(environ, start_response):
    """Simple WSGI complient Server."""
    parts = environ.get('PATH_INFO', '').split('/')
    if len(parts) < 3:
        start_response('404 Not Found', [('Content-Type', 'text/plain')])
        return ["File not found\n"]
    typ, doc_id = parts[1:3]
    doc_id = doc_id.strip('jpeg.')
    if not typ_re.match(typ):
        start_response('501 Error', [('Content-Type', 'text/plain')])
        return ["Not Implemented\n"]
    if not docid_re.match(doc_id):
        start_response('501 Error', [('Content-Type', 'text/plain')])
        return ["Not Implemented\n"]

    if not os.path.exists(os.path.join(CACHEDIR, typ)):
        os.makedirs(os.path.join(CACHEDIR, typ))

    cachefilename = os.path.join(CACHEDIR, typ, doc_id + '.jpeg')
    if os.path.exists(cachefilename):
        # serve request from cache
        start_response('200 OK', [('Content-Type', 'image/jpeg'),
                                  ('Cache-Control', 'max-age=1728000, public'),  # 20 Days
                                  ])
        return open(cachefilename)

    # get data from database
    orgfile = _get_original_file(doc_id)
    if not orgfile:
        start_response('404 Not Found', [('Content-Type', 'text/plain')])
        return ["File not found"]

    if typ == 'o':
        imagefile = orgfile
    else:
        width, height = typ.split('x')
        try:
            img = Image.open(orgfile)

            if height.endswith('!'):
                height = height.strip('!')
                img = _crop_image(width, height, img)
            else:
                img = _scale_image(width, height, img)
        except IOError:
            # we assume the source file is broken
            mark_broken(doc_id)
            start_response('404 Internal Server Error', [('Content-Type', 'text/plain')])
            return ["File not found"]

        if img.mode != "RGB":
            img = img.convert("RGB")

        tempfilename = tempfile.mktemp(prefix='tmp_%s_%s' % (typ, doc_id), dir=CACHEDIR)
        img.save(tempfilename, "JPEG")
        os.rename(tempfilename, cachefilename)
        # using X-Sendfile could speed this up.
        imagefile = open(cachefilename)

    start_response('200 OK', [('Content-Type', 'image/jpeg'),
                              ('Cache-Control', 'max-age=1728000, public'),  # 20 Days
                              ])
    return imagefile


def save_imagserver(environ, start_response):
    """Executes imageserver() returning a 500 status code on an exception."""
    try:
        return imagserver(environ, start_response)
    except:
        raise
        try:
            start_response('500 OK', [('Content-Type', 'text/plain')])
        except:
            pass
        return ['Error']


def _get_original_file(doc_id):
    """Returns a filehandle for the unscaled file related to doc_id."""

    cachefilename = os.path.join(CACHEDIR, 'o', doc_id + '.jpeg')
    if os.path.exists(cachefilename):
        # File exists in the cache
        return open(cachefilename)

    # ensure the needed dirs exist
    if not os.path.exists(os.path.join(CACHEDIR, 'o')):
        os.makedirs(os.path.join(CACHEDIR, 'o'))

    # try to get file from S3
    conn = boto.connect_s3()
    s3bucket = conn.get_bucket(S3BUCKET)
    k = s3bucket.get_key(doc_id)
    if k:
        # write then rename to avoid race conditions
        tempfilename = tempfile.mktemp(prefix='tmp_%s_%s' % ('o', doc_id), dir=CACHEDIR)
        k.get_file(open(tempfilename, "w"))
        os.rename(tempfilename, cachefilename)
        return open(cachefilename)

    # try to get it from couchdb
    db = couchdb.client.Server(COUCHSERVER)[COUCHDB_NAME]
    try:
        doc = db[doc_id]
    except couchdb.client.ResourceNotFound:
        return None

    filename = list(doc['_attachments'].keys())[0]

    # save original Image in Cache
    filedata = db.get_attachment(doc_id, filename)
    # write then rename to avoid race conditions
    tempfilename = tempfile.mktemp(prefix='tmp_%s_%s' % ('o', doc_id), dir=CACHEDIR)
    open(os.path.join(tempfilename), 'w').write(filedata)
    os.rename(tempfilename, cachefilename)

    # upload to S3 for migrating form CouchDB to S3
    conn = boto.connect_s3()
    k = s3bucket.get_key(doc_id)
    if not k:
        k = boto.s3.key.Key(s3bucket)
        k.key = doc_id
        k.set_contents_from_filename(cachefilename)
        k.make_public()

    return open(cachefilename)


standalone = False
if standalone:
    PORT = 8080
    httpd = make_server('', PORT, imagserver)
    print 'Starting up HTTP server on port %i...' % PORT

    # Respond to requests until process is killed
    httpd.serve_forever()

# FastCGI
WSGIServer(save_imagserver).run()
