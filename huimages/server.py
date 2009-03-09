# -*- coding: utf-8 -*-

"""Serving images out of CouchDB. Runs on i.hdimg.net."""

# Created 2006, 2009 by Maximillian Dornseif. Consider it BSD licensed.

import couchdb.client
import Image 
import os
import os.path
import tempfile
from wsgiref.simple_server import make_server

COUCHSERVER = "http://couchdb.local.hudora.biz:5984"
COUCHDB_NAME = "huimages"
# I'm totally out of ideas how to switch between production and test environments


def _scale_image(width, height, image):
    """
    This function will scale an image to a given bounding box. Image
    aspect ratios will be conserved and so there might be blank space
    at two sides of the image if the ratio isn't identical to that of
    the bounding box.
    """
    #from http://simon.bofh.ms/cgi-bin/trac-django-projects.cgi/file/stuff/branches/magic-removal/image.py
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
    #from http://simon.bofh.ms/cgi-bin/trac-django-projects.cgi/file/stuff/branches/magic-removal/image.py
    # moderately modified
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


CACHEDIR = './cache'


def imagserver(environ, start_response):
    parts = environ.get('PATH_INFO', '').split('/')
    if len(parts) != 3:
        start_response('404 Not Found', [('Content-Type', 'text/plain')])
        return ["File not found"]
    typ, doc_id = parts[1:]
    doc_id = doc_id.strip('jpeg.')
    if not os.path.exists(os.path.join(CACHEDIR, typ)):
        os.makedirs(os.path.join(CACHEDIR, typ))
    
    cachefilename = os.path.join(CACHEDIR, typ, doc_id + '.jpeg')
    if os.path.exists(cachefilename):
        # serve request from cache
        print "Cache Hit"
        start_response('200 OK', [('Content-Type', 'image/jpeg'),
                                  ('Cache-Control', 'max-age=172800, public'), # 2 Days
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
        img = Image.open(orgfile)
        if height.endswith('!'):
            height = height.strip('!')
            img = _crop_image(width, height, img)
        else:
            img = _scale_image(width, height, img)
        if img.mode != "RGB":
            img = img.convert("RGB")
        
        tempfilename = tempfile.mktemp(prefix='tmp_%s_%s' % (typ, doc_id), dir=CACHEDIR)
        img.save(tempfilename, "JPEG")
        os.rename(tempfilename, cachefilename)
        imagefile = open(cachefilename)
    
    start_response('200 OK', [('Content-Type', 'image/jpeg'),
                              ('Cache-Control', 'max-age=1209600, public'), # 14 Days
                              ])
    return imagefile


def _get_original_file(doc_id):
    """Returns a filehandle for the unscaled file related to doc_id."""
    
    cachefilename = os.path.join(CACHEDIR, 'o', doc_id + '.jpeg')
    if os.path.exists(cachefilename):
        return open(cachefilename)
    
    db = couchdb.client.Server(COUCHSERVER)[COUCHDB_NAME]
    try:
        doc = db[doc_id]
    except couchdb.client.ResourceNotFound:
        return None
        
    filename = doc['_attachments'].keys()[0]
    
    # save original Image in Cache
    filedata = db.get_attachment(doc_id, filename)
    if not os.path.exists(os.path.join(CACHEDIR, 'o')):
        os.makedirs(os.path.join(CACHEDIR, 'o'))
    tempfilename = tempfile.mktemp(prefix='tmp_%s_%s' % ('o', doc_id), dir=CACHEDIR)
    open(os.path.join(tempfilename), 'w').write(filedata)
    os.rename(tempfilename, cachefilename)
    return open(cachefilename)


if __name__ == '__main__':
    PORT = 8000
    httpd = make_server('', PORT, app)
    print 'Starting up HTTP server on port %i...' % PORT
    
    # Respond to requests until process is killed
    httpd.serve_forever()
