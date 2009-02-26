#!/usr/bin/env python
# encoding: utf-8
"""
untitled.py

Created by Maximillian Dornseif on 2009-01-29.
Copyright (c) 2009 HUDORA. All rights reserved.
"""

# Create your views here.


import couchdb.client
import os.path
from operator import itemgetter
from huTools.async import Future
from huTools.decorators import cache_function

from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.utils.safestring import mark_safe
from django.utils import simplejson

IMAGESERVER = "http://i.hdimg.net"
COUCHSERVER = "http://couchdb.local.hudora.biz:5984"
COUCHDB_NAME = "huimages"


def get_rating(imageid):
    server = couchdb.client.Server(COUCHSERVER)
    db = server[COUCHDB_NAME+'_meta']
    ret = [x.value for x in db.view('ratings/all', group=True, startkey=imageid, limit=1) if x.key == imageid]
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
                line.append(mark_safe('<a href="/images/image/%s/">%s</a>' % (imageid,
                            scaled_tag(imageid, "150x150!"))))
        lines.append(line)
    return render_to_response('imagebrowser/startpage.html', {'lines': lines, 'title': 'Ihre Favoriten'},
                                context_instance=RequestContext(request))
    

def by_tag(request, tagname):
    # TODO: extract
    server = couchdb.client.Server(COUCHSERVER)
    db = server[COUCHDB_NAME+'_meta']
    ret = [x.value for x in db.view('tags/document_per_tag', startkey=tagname, endkey="%sZ" % tagname)]
    lines = []
    while ret:
        line = []
        for x in range(5):
            if ret:
                imageid = ret.pop()
                line.append(mark_safe('<a href="/images/image/%s/">%s</a>' % (imageid,
                            scaled_tag(imageid, "150x150!"))))
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
    return render_to_response('imagebrowser/image.html', {'imagetag': imagetag,
         'favorite': favorite, 'tags': tags, 'rating': rating,
        'previous': mark_safe('<a href="../../image/%s/">%s</a>' % (previousid,
                              scaled_tag(previousid, "75x75!"))),
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
