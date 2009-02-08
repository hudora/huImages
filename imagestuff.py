#!/usr/bin/env python
# encoding: utf-8
"""
untitled.py

Created by Maximillian Dornseif on August 2006.
Copyright (c) 2006, 2009 HUDORA. All rights reserved.
"""

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
    print db[doc_id]
    if not (doc.get('_attachments')):
        db.put_attachment(db[doc_id], imagedata, filename)
    return doc_id
    

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
    

def get_random_imageid():
    db = _setup_couchdb()
    startkey = base64.b32encode(hashlib.sha1(str(random.random())).digest()).rstrip('=')
    return [x.id for x in db.view('_all_docs', startkey=startkey, limit=1)][0]


print '<html><body>'
for y in range(4):
    for x in range(4):
        imageid = get_random_imageid()
        print '<a href="http://couchdb1.local.hudora.biz:5984/_utils/document.html?huimages/%s">%s</a>' % (imageid, scaled_tag(imageid, "200x200!"))
    print '<br/>'
print '</body></html>'


#from produktpass.models import *
#for i in  Image.objects.all():
#    filename = os.path.split(str(i.path))[1]
#    print save_image(i.path.read(), references={"artnr": i.product.artnr}, title=i.title, filename=filename)    



# encoding: utf-8

"""Image field which scales images on demand.

This acts like Django's ImageField but in addition can scale images on demand. Scaled Images are put in
<settings.MEDIA_ROOT>/,/<originalpath>. The avialable scaling factors are hardcoded in the dictionary _sizes.
If the dimensions there are followed by an '!' this means the images should be cropped to exactly this size.
Without this the images are scaled to fit in the given size without changing the aspect ratio of the image.

Scaled versions of the images are generated on the fly using PIL and then kept arround in the Filesystem. 

Given a model like

class Image(models.Model):
    path       = ScaledImageField(verbose_name='Datei', upload_to='-/product/image')
    [...]

you can do  the following:

>>> img.path  
'-/product/image/0e99d6be8ec0259df920c2d273d1ad6f.jpg'
>>>img.get_path_url()
'/media/-/product/image/0e99d6be8ec0259df920c2d273d1ad6f.jpg'
>>> img.get_path_size()
417119L
>>> img.get_path_width()
1584
>>> img.get_path_height()
2889

All well known metods from ImageField are supported. The new functionality is available via img.path_scaled - this returns an
Imagescaler instance beeing able to play some nifty tricks:

>>> img.path_scaled().svga()
'/,/-/product/image/0e99d6be8ec0259df920c2d273d1ad6f.jpg/svga.jpeg'
>>> img.path_scaled().svga_path()
'/usr/local/web/media/,/-/product/image/0e99d6be8ec0259df920c2d273d1ad6f.jpg/svga.jpeg'
>>> img.path_scaled().svga_dimensions()
(328, 600)
>>> img.path_scaled().svga_tag()
'<img src="/,/-/product/image/0e99d6be8ec0259df920c2d273d1ad6f.jpg/svga.jpeg" width="328" height="600" />'
>>> img.path_scaled().thumb_dimensions()
(50, 91)
>>> img.path_scaled().square_dimensions()
(75, 76)

Created August 2006, 2009 by Maximillian Dornseif. Consider it BSD licensed.
"""



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
    

class Imagescaler:
    """Class whose instances scale an image on the fly to desired properties.
    
    For each set of dimensions defined in _sizes imagescaler has a set of functions, e.g. for 'small':
    
    o.small() = return the URL of the small version of the image
    o.small_path() - return the absolute  pathe in the filesystem for the  image
    o.small_dimensions() - return (width,  heigth)
    o.small_tag() - return a complete image tag for use in XHTML
    
    >>> img.path_scaled().svga()
    '/,/-/product/image/0e99d6be8ec0259df920c2d273d1ad6f.jpg/svga.jpeg'
    >>> img.path_scaled().svga_path()
    '/usr/local/web/media/,/-/product/image/0e99d6be8ec0259df920c2d273d1ad6f.jpg/svga.jpeg'
    >>> img.path_scaled().svga_dimensions()
    (328, 600)
    >>> img.path_scaled().svga_tag()
    '<img src="/,/-/product/image/0e99d6be8ec0259df920c2d273d1ad6f.jpg/svga.jpeg" width="328" height="600" />'
    """
    def __init__(self, field, obj):
        self.field = field
        self.parent_obj = obj
        self.original_image = getattr(self.parent_obj, self.field.attname)
        # if broken.gif exists we sendd that if there are any problems during scaling
        if not os.path.exists(self.original_image_path):
            self.broken_image = os.path.join(settings.MEDIA_ROOT, 'broken.gif') 
        for size in _sizes:
            setattr(self, '%s' % (size), curry(self.scaled_url, size))
            setattr(self, '%s_dimensions' % (size), curry(self.scaled_dimensions, size))
            setattr(self, '%s_tag' % (size), curry(self.scaled_tag, size))
    
    def scaled_url(self, size='thumb'):
        """Scales an image according to 'size' and returns the URL of the scaled image."""
        return urlparse.urljoin(IMAGESERVER, _sizes.get(size, size), self.imageid) + '.jpeg'
    
    def scaled_dimensions(self, size='thumb'):
        """Scales an image according to 'size' and returns the dimensions."""
        size = _sizes.get(size, size)
        width, height = [int(i) for i in _sizes[size].split('x')]
        if size.endswith('!'):
            return (width, height)
        # get current is_width and is_height
        try:
            db = _setup_couchdb()
            doc = db[doc_id]
            return _scale(width, height, doc.width, doc.height)
        except:
            return (None, None)
    
    def scaled_tag(self, size='thumb', *args, **kwargs):
        """Scales an image according to 'size' and returns an XHTML tag for that image.
        
        Additional keyword arguments are added as attributes to  the <img> tag.
        
        >>> img.path_scaled().svga_tag(alt='neu')
        '<img src="http://images.hudora.de/477x600/0ead6fsdfsaf.jpeg" width="328" height="600" alt="neu"/>'
        """
        ret = ['<img src="%s"' % escape(self.scaled_url(size))]
        width, height = self.scaled_dimensions(size)
        if width and height:
            ret.append('width="%d" height="%d"' % (width, height))
        ret.extend(args)
        for key, val in kwargs.items():
            ret.append('%s="%s"' % (escape(key), escape(val)))
        ret.append('/>')
        return mark_safe(' '.join(ret))


#class ScalingImageField(ImageField):
#    """This acts like Django's ImageField but in addition can scale images on demand by providing an
#    ImageScler object.
#    
#    >>> img.path_scaled().svga()
#    '/,/-/product/image/0e99d6be8ec0259df920c2d273d1ad6f.jpg/svga.jpeg'
#    """
#    
#    def __init__(self, verbose_name=None, name=None, width_field=None, height_field=None, auto_rename=True,
#                 **kwargs):
#        """Inits the ScalingImageField."""
#        super(ScalingImageField, self).__init__(verbose_name, name, width_field, height_field, **kwargs)
#    
#    def contribute_to_class(self, cls, name):
#        """Adds field-related functions to the model."""
#        super(ScalingImageField, self).contribute_to_class(cls, name)
#        setattr(cls, '%s_scaled' % self.name, curry(Imagescaler, self))
#    
#    def get_internal_type(self):
#        return 'ImageField'
#
#
#
#if __name__ == '__main__':
#    unittest.main()
    