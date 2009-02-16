# Create your views here.

import copy
import threading
# from http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/84317
class Future:
    def __init__(self, func, *args, **kwargs):
        # Constructor
        self.__done=0
        self.__result=None
        self.__status='working'
        self.__excpt = None
        
        self.__C=threading.Condition()   # Notify on this Condition when result is ready
        
        # Run the actual function in a separate thread
        self.__T=threading.Thread(target=self.Wrapper,args=((func,) + args), **kwargs)
        self.__T.setName("FutureThread")
        self.__T.start()
    
    def __repr__(self):
        return '<Future at '+hex(id(self))+':'+self.__status+'>'
    
    def __call__(self):
        self.__C.acquire()
        while self.__done==0:
            self.__C.wait()
        self.__C.release()
        # We deepcopy __result to prevent accidental tampering with it.
        a=copy.deepcopy(self.__result)
        if self.__excpt:
            raise self.__excpt[0], self.__excpt[1], self.__excpt[2]
        return a
    
    def Wrapper(self, func, *args, **kwargs):
        # Run the actual function, and let us housekeep around it
        self.__C.acquire()
        try:
            self.__result=func(*args, **kwargs)
        except:
            self.__result="Exception raised within Future"
            self.__excpt = sys.exc_info()
        self.__done=1
        self.__status=self.__result
        self.__C.notify()
        self.__C.release()
    

import cPickle as pickle
import md5

def cache_function(length):
    """
    A variant of the snippet posted by Jeff Wheeler at
    http://www.djangosnippets.org/snippets/109/
    
    Caches a function, using the function and its arguments as the key, and the return
    value as the value saved. It passes all arguments on to the function, as
    it should.
    
    The decorator itself takes a length argument, which is the number of
    seconds the cache will keep the result around.
    
    It will put in a MethodNotFinishedError in the cache while the function is
    processing. This should not matter in most cases, but if the app is using
    threads, you won't be able to get the previous value, and will need to
    wait until the function finishes. If this is not desired behavior, you can
    remove the first two lines after the ``else``.
    """
    def decorator(func):
        def inner_func(*args, **kwargs):
            from django.core.cache import cache
            
            raw = [func.__name__, func.__module__, args, kwargs]
            pickled = pickle.dumps(raw, protocol=pickle.HIGHEST_PROTOCOL)
            key = md5.new(pickled).hexdigest()
            value = cache.get(key)
            if cache.has_key(key):
                return value
            else:
                # This will set a temporary value while ``func`` is being
                # processed. When using threads, this is vital, as otherwise
                # the function can be called several times before it finishes
                # and is put into the cache.
                class MethodNotFinishedError(Exception): pass
                cache.set(key, MethodNotFinishedError(
                    'The function %s has not finished processing yet. This \
value will be replaced when it finishes.' % (func.__name__)
                ), length)
                result = func(*args, **kwargs)
                cache.set(key, result, length)
                return result
        return inner_func
    return decorator

# *********************


from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.utils.safestring import mark_safe
from django.utils import simplejson

import Image 
import base64
import cgi
import datetime
import hashlib
import md5
import os
import time
import time
import urlparse
import couchdb.client
from operator import itemgetter

# from django.core import urlresolvers
# from django.conf import settings
# from django.utils.html import escape 
# from django.utils.safestring import mark_safe 
# from django.utils.functional import curry
# from django.db.models import ImageField, signals
# 

IMAGESERVER = "http://images.hudora.de"
COUCHSERVER = "http://couchdb.local.hudora.biz:5984"
COUCHDB_NAME = "huimages"

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
import os.path
import random
import time
import couchdb.client

COUCHSERVER = "http://couchdb.local.hudora.biz:5984"
COUCHDB_NAME = "huimages"
# I'm totally out of ideas how to switch between production and test environments


_sizes = {'mini':    "23x40",
          'thumb':   "50x200", 
          'sidebar': "179x600",
          'small':   "240x160",
          'medium':  "480x320", 
          'full':    "477x800",
          'vga':     "640x480", 
          'svga':    "800x600", 
          'xvga':    "1024x768",
          'square':  "75x75!"} 


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
    db = _setup_couchdb()
    doc = db[imageid]
    return doc
    

def imageurl(imageid, size='o'):
    return urlparse.urljoin(IMAGESERVER, os.path.join(size, imageid)) + '.jpeg'
    

def scaled_imageurl(imageid, size='square'):
    """Scales an image according to 'size' and returns the URL of the scaled image."""
    return urlparse.urljoin(IMAGESERVER, os.path.join(_sizes.get(size, size), imageid)) + '.jpeg'
    

def scaled_dimensions(imageid, size='square'):
    """Scales an image according to 'size' and returns the dimensions."""
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
    """Scales an image according to 'size' and returns an XHTML tag for that image.
    
    Additional keyword arguments are added as attributes to  the <img> tag.
    
    >>> img.path_scaled().svga_tag(alt='neu')
    '<img src="http://images.hudora.de/477x600/0ead6fsdfsaf.jpeg" width="328" height="600" alt="neu"/>'
    """
    ret = ['<img src="%s"' % cgi.escape(scaled_imageurl(imageid, size), True)]
    width, height = scaled_dimensions(imageid, size)
    if width and height:
        ret.append('width="%d" height="%d"' % (width, height))
    ret.extend(args)
    for key, val in kwargs.items():
        ret.append('%s="%s"' % (cgi.escape(key, True), egi.escape(val, True)))
    ret.append('/>')
    return ' '.join(ret)
    

def get_rating(imageid):
    server = couchdb.client.Server(COUCHSERVER)
    db = server[COUCHDB_NAME+'_meta']
    ret = [x.value for x in db.view('ratings/all', group=True, startkey=imageid ,limit=1) if x.key == imageid]
    if ret:
        votecount = ret[0][0]
        return votecount, float(ret[0][1])/votecount
    else:
        return 0, 0
    

def get_user_tags(imageid, userid):
    server = couchdb.client.Server(COUCHSERVER)
    db = server[COUCHDB_NAME+'_meta']
    doc_id = "%s-%s" % (imageid, userid)
    return db.get(doc_id, {}).get('tags', [])
    

def is_favorite(imageid, userid):
    server = couchdb.client.Server(COUCHSERVER)
    db = server[COUCHDB_NAME+'_meta']
    doc_id = "%s-%s" % (imageid, userid)
    return db.get(doc_id, {}).get('favorite', False)
    

@cache_function(60)
def get_tagcount():
    server = couchdb.client.Server(COUCHSERVER)
    db = server[COUCHDB_NAME+'_meta']
    ret = dict([(x.key, x.value) for x in db.view('tags/tagcount', group=True)])
    return ret

def get_random_imageid():
    db = _setup_couchdb()
    startkey = base64.b32encode(hashlib.sha1(str(random.random())).digest()).rstrip('=')
    return [x.id for x in db.view('all/without_deleted', startkey=startkey, limit=1)][0]
    

def get_next_imageid(imageid):
    db = _setup_couchdb()
    return [x.id for x in db.view('_all_docs', startkey=imageid, limit=2)][-1]
    

def get_previous_imageid(imageid):
    db = _setup_couchdb()
    return [x.id for x in db.view('_all_docs', startkey=imageid, limit=2, descending=True)][-1]
    

def update_user_metadata(imageid, userid, data):
    server = couchdb.client.Server(COUCHSERVER)
    db = server[COUCHDB_NAME+'_meta']
    
    doc_id = "%s-%s" % (imageid, userid)
    doc = {'imageid': imageid, 'userid': userid}
    doc.update(data)
    
    try:
        db[doc_id] = doc
    except couchdb.client.ResourceConflict:
        doc = db[doc_id]
        doc.update(data)
        db[doc_id] = doc
        
# ****************************

def startpage(request):
    def get_line():
        line = []
        for x in range(5):
            imageid = get_random_imageid()
            line.append(mark_safe('<a href="image/%s/">%s</a>' % (imageid, scaled_tag(imageid, "150x150!"))))
        return line
    
    tagfuture = Future(get_tagcount)
    linef = []
    for y in range(3):
        linef.append(Future(get_line))
    tagcount = tagfuture().items()
    tagcount.sort()
    lines = []
    for line in linef:
        lines.append(line())
    return render_to_response('imagebrowser/startpage.html', {'lines': lines, 'tags': tagcount, 
                              'title': 'HUDORA Bilderarchiv'},
                                context_instance=RequestContext(request))
    

def favorites_redirect(request):
    # TODO: extract
    server = couchdb.client.Server(COUCHSERVER)
    db = server[COUCHDB_NAME+'_meta']
    return HttpResponseRedirect("%s/" % request.clienttrack_uid)
    

def favorites(request, uid):
    # TODO: extract
    server = couchdb.client.Server(COUCHSERVER)
    db = server[COUCHDB_NAME+'_meta']
    ret = [x.value for x in db.view('favorites/all', startkey=uid, endkey="%sZ" % request.clienttrack_uid)]
    lines = []
    while ret:
        line = []
        for x in range(5):
            if ret:
                imageid = ret.pop()
                line.append(mark_safe('<a href="/images/image/%s/">%s</a>' % (imageid, scaled_tag(imageid, "150x150!"))))
        lines.append(line)
    return render_to_response('imagebrowser/startpage.html', {'lines': lines, 'title': 'Ihre Favoriten'},
                                context_instance=RequestContext(request))
    

def by_tag(request, tagname):
    # TODO: extract
    server = couchdb.client.Server(COUCHSERVER)
    db = server[COUCHDB_NAME+'_meta']
    ret = [x.value for x in db.view('tags/document_per_tag', startkey=tagname, endkey="%sZ" % tagname)]
    print ret
    lines = []
    while ret:
        line = []
        for x in range(5):
            if ret:
                imageid = ret.pop()
                line.append(mark_safe('<a href="/images/image/%s/">%s</a>' % (imageid, scaled_tag(imageid, "150x150!"))))
        lines.append(line)
    return render_to_response('imagebrowser/startpage.html', {'lines': lines, 'title': 'Tag "%s"' % tagname},
                                context_instance=RequestContext(request))
    

def image(request, imageid):
    imagetag = mark_safe('<a href="%s">%s</a>' % (imageurl(imageid), scaled_tag(imageid, "vga")))
    imagedoc = get_imagedoc(imageid)
    votecount, rating = get_rating(imageid)
    favorite = is_favorite(imageid, request.clienttrack_uid)
    tags = get_user_tags(imageid, request.clienttrack_uid)
    previousid = get_previous_imageid(imageid)
    nextid = get_next_imageid(imageid)
    return render_to_response('imagebrowser/image.html', {'imagetag': imagetag, 'favorite': favorite,
                                                          'tags': tags, 'rating': rating,
                                                          'previous': mark_safe('<a href="../../image/%s/">%s</a>' % (previousid, scaled_tag(previousid, "75x75!"))),
                                                          'next': mark_safe('<a href="../../image/%s/">%s</a>' % (nextid, scaled_tag(nextid, "75x75!"))),
                                                          'title': imagedoc.get('title', ['ohne Titel'])[-1]},
                                context_instance=RequestContext(request))

def previous_image(request, imageid):
    return HttpResponseRedirect("../../%s/" % get_previous_imageid(imageid))
    

def random_image(request):
    return HttpResponseRedirect("../%s/" % get_random_imageid())
    

def next_image(request, imageid):
    return HttpResponseRedirect("../../%s/" % get_next_imageid(imageid))
    

def tag_suggestion(request, imageid):
    prefix = request.GET.get('tag', '')
    tagcount = get_tagcount().items()
    tagcount.sort(key = itemgetter(1), reverse=True)
    json = simplejson.dumps([x[0] for x in tagcount if x[0].startswith(prefix)])
    response = HttpResponse(json, mimetype='application/json')
    return response
    

# AJAX bookmarking
def favorite(request, imageid):
    if request.POST['rating'] == '1':
        update_user_metadata(imageid, request.clienttrack_uid, {'favorite': True})
    else:
        update_user_metadata(imageid, request.clienttrack_uid, {'favorite': False})
    return HttpResponse('ok', mimetype='application/json')
    

# AJAX rating
def rate(request, imageid):
    update_user_metadata(imageid, request.clienttrack_uid, {'rating': int(request.POST['rating'])})
    votecount, rating = get_rating(imageid)
    json = simplejson.dumps(rating)
    response = HttpResponse(json, mimetype='application/json')
    return response
    

# AJAX tagging
def tag(request, imageid):
    newtags = request.POST['newtag'].lower().replace(',', ' ').split(' ')
    newtags = [x.strip() for x in newtags if x.strip()]
    tags = set(get_user_tags(imageid, request.clienttrack_uid) + newtags)
    tags = [x.lower() for x in list(tags) if x]
    update_user_metadata(imageid, request.clienttrack_uid, {'tags': tags})
    # todo: flush tag cache
    json = simplejson.dumps(newtags)
    response = HttpResponse(json, mimetype='application/json')
    return response
    

# AJAX titeling
def update_title(request, imageid):
    db = _setup_couchdb()
    title = request.POST['value']
    doc = get_imagedoc(imageid)
    if title and title not in doc.get('title', []):
        doc.setdefault('title', []).append(title)
    db[imageid] = doc
    response = HttpResponse(title, mimetype='text/plain')
    return response
