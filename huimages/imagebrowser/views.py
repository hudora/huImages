#!/usr/bin/env python
# encoding: utf-8
"""
imagebrowser/views.py

Created by Maximillian Dornseif on 2009-01-29.
Copyright (c) 2009, 2010 HUDORA. All rights reserved.
"""


import couchdb.client
import os
from operator import itemgetter
from huTools.async import Future
from huTools.decorators import cache_function

from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.utils.safestring import mark_safe
from django.utils import simplejson
from django.core.urlresolvers import reverse

from huimages import *
from huimages.imagebrowser.forms import UploadForm

IMAGESERVER = "http://i.hdimg.net"
COUCHSERVER = "http://couchdb.local.hudora.biz:5984"
COUCHDB_NAME = "huimages"

# helpers

def get_rating(imageid):
    server = couchdb.client.Server(COUCHSERVER)
    db = server[COUCHDB_NAME + '_meta']
    ret = [x.value for x in db.view('ratings/all', startkey=imageid, limit=1) if x.key == imageid]
    if ret:
        votecount = ret[0][0]
        return votecount, float(ret[0][1]) / votecount
    else:
        return 0, 0


def get_user_tags(imageid, userid):
    """Returns a list of user specific tags"""
    server = couchdb.client.Server(COUCHSERVER)
    db = server[COUCHDB_NAME + '_meta']
    doc_id = "%s-%s" % (imageid, userid)
    return db.get(doc_id, {}).get('tags', [])


def get_all_tags(imageid):
    """Return a list of all tags for an image"""
    server = couchdb.client.Server(COUCHSERVER)
    db = server[COUCHDB_NAME + '_meta']
    doc_id = imageid
    tags = set([x.value for x in db.view('tags/tags_per_document', startkey=imageid, endkey="%sZ" % imageid)])
    return list(tags)


def is_favorite(imageid, userid):
    server = couchdb.client.Server(COUCHSERVER)
    db = server[COUCHDB_NAME + '_meta']
    doc_id = "%s-%s" % (imageid, userid)
    return db.get(doc_id, {}).get('favorite', False)


@cache_function(60)
def get_tagcount():
    server = couchdb.client.Server(COUCHSERVER)
    db = server[COUCHDB_NAME + '_meta']
    ret = dict([(x.key, x.value) for x in db.view('tags/tagcount', group=True)])
    return ret


def update_user_metadata(imageid, userid, data):
    server = couchdb.client.Server(COUCHSERVER)
    db = server[COUCHDB_NAME + '_meta']

    doc_id = "%s-%s" % (imageid, userid)
    doc = {'imageid': imageid, 'userid': userid}
    doc.update(data)
    open('/tmp/debug3.txt', 'a').write(repr([doc_id]))

    try:
        db[doc_id] = doc
    except couchdb.client.http.ResourceConflict:
        doc = db[doc_id]
        doc.update(data)
        db[doc_id] = doc


def images_by_tag(tagname):
    """Returns ImageIds with a certain tag."""
    server = couchdb.client.Server(COUCHSERVER)
    db = server[COUCHDB_NAME + '_meta']
    ret = [x.value for x in db.view('tags/document_per_tag', startkey=tagname, endkey="%sZ" % tagname)]
    return ret


def get_favorites(uid):
    server = couchdb.client.Server(COUCHSERVER)
    db = server[COUCHDB_NAME + '_meta']
    ret = [x.value for x in db.view('favorites/all', startkey=uid, endkey="%sZ" % uid)]
    return ret


def set_tags(newtags, imageid, userid):
    open('/tmp/debug2.txt', 'a').write(repr([newtags, imageid, userid]))
    newtags = newtags.lower().replace(',', ' ').split(' ')
    newtags = [x.strip() for x in newtags if x.strip()]
    tags = set(get_user_tags(imageid, userid) + newtags)
    tags = [x.lower() for x in list(tags) if x]
    open('/tmp/debug2.txt', 'a').write(repr([tags]))
    update_user_metadata(imageid, userid, {'tags': tags})
    return newtags


# views

def startpage(request):
    def get_line():
        line = []
        for dummy in range(5):
            imageid = get_random_imageid()
            line.append(mark_safe('<a href="image/%s/">%s</a>' % (imageid, scaled_tag(imageid, "150x150!"))))
        return line

    tagfuture = Future(get_tagcount)
    linef = []
    for dummy in range(3):
        linef.append(Future(get_line))
    tagcount = sorted(tagfuture().items())
    lines = []
    for line in linef:
        lines.append(line())
    return render_to_response('imagebrowser/startpage.html', {'lines': lines, 'tags': tagcount,
                              'title': 'HUDORA Bilderarchiv'},
                                context_instance=RequestContext(request))


def upload(request):
    if request.method == "POST":
        form = UploadForm(request.POST, request.FILES)
        if form.is_valid():
            image = request.FILES['image']
            imageid = save_image(image.read(), title=form.cleaned_data.get('title'))
            set_tags(form.cleaned_data.get('tags'), imageid, request.clienttrack_uid)
            return HttpResponseRedirect(reverse('view-image', kwargs={'imageid': imageid}))
    else:
        form = UploadForm()
    return render_to_response('imagebrowser/upload.html', {'form': form, 'title': 'Bilder Upload',
                                                           'clienttrack': request.clienttrack_uid},
                                context_instance=RequestContext(request))


def api_store_image(request):
    if request.method == 'POST':
        if request.FILES:
            image = request.FILES['uploadfile']
            imageid = save_image(image.read(), title=request.GET.get('title', ''))
            set_tags(request.GET.get('tags', ''), imageid, request.GET.get('clienttrack', 'API'))
            return HttpResponse(imageid)
    raise Http404


def upload_serve_swffile(request):
    """Server the Shopwave uploader - should be served from the same path as the upload destination."""
    ret = HttpResponse(mimetype="application/xhtml+xml")
    fd = open(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'swfupload.swf'))
    ret.write(fd.read(), mimetype='application/x-shockwave-flash')
    return ret


def favorites_redirect(request):
    """Redirects to the user specific favorites page."""
    return HttpResponseRedirect("%s/" % request.clienttrack_uid)


def favorites(request, uid):
    ret = get_favorites(uid, request)
    lines = []
    while ret:
        line = []
        for dummy in range(5):
            if ret:
                imageid = ret.pop()
                line.append(mark_safe('<a href="/i/image/%s/">%s</a>' % (imageid,
                            scaled_tag(imageid, "150x150!"))))
        lines.append(line)
    return render_to_response('imagebrowser/collection.html', {'lines': lines, 'title': 'Ihre Favoriten'},
                                context_instance=RequestContext(request))


def by_tag(request, tagname):
    ret = images_by_tag(tagname)
    lines = []
    while ret:
        line = []
        for dummy in range(5):
            if ret:
                imageid = ret.pop()
                line.append(mark_safe('<a href="/i/image/%s/">%s</a>' % (imageid,
                            scaled_tag(imageid, "150x150!"))))
        lines.append(line)
    return render_to_response('imagebrowser/collection.html', {'lines': lines, 'title': 'Tag "%s"' % tagname},
                                context_instance=RequestContext(request))


def image(request, imageid):
    imagetag = mark_safe('<a href="%s">%s</a>' % (imageurl(imageid), scaled_tag(imageid, "vga")))
    imagedoc = get_imagedoc(imageid)
    votecount, rating = get_rating(imageid)
    favorite = is_favorite(imageid, request.clienttrack_uid)
    tags = get_all_tags(imageid)
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
    tagcount = list(get_tagcount().items())
    tagcount.sort(key=itemgetter(1), reverse=True)
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

def tag(request, imageid):
    """Set tags via AJAX."""
    newtags = request.POST['newtag']
    userid = request.clienttrack_uid
    newtags = set_tags(newtags, imageid, userid)
    # todo: flush tag cache
    json = simplejson.dumps(newtags)
    response = HttpResponse(json, mimetype='application/json')
    return response


# AJAX titeling

def update_title(request, imageid):
    set_title(imageid, request.POST['value'])
    response = HttpResponse(request.POST['value'], mimetype='text/plain')
    return response
