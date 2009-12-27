# Functionality

huImages provides an infrastructure for storing, serving and scaling images.
It might not work for facebook or flickr scale image-pools, but for a few
hundred thousand images it woks very nicely. Currently it only supports
JPEG files.

When you upload an image, you get back a alpha-numeric ID back for further
accessing the image. You can get the URL of the Image via imageurl(ID) and
`scaled_imageurl(ID)`. You can get a complete XHTML `<img>` tag via
`scaled_tag(ID)`.

This module uses the concept of "sizes". A size can be a numeric specification
like "240x160". If the numeric specification ends with "!" (like in "75x75!")
the image is scaled and cropped to be EXACTLY of that size. If not the image
keeps it aspect ratio.

You can use `get_random_imageid()`, `get_next_imageid(ID)` and
`get_previous_imageid(ID)` to implement image browsing.

# The image Server

`server.py` implements the image servin infrastructure. huImages assumes that
images are served form a separate server. We strongly suggest to serve them
from a separate domain. This domain should have which been used for cookies.
This is because the existence of cookies usually badly hurts caching
behaviour. "yourdomain-img.net" would be a good choice for a domain name. We
use "i.hdimg.net." for that purpose.

In the first few Versions of huImages Meta-Data and Images where stored in
[CouchDB][1]. After the fist few dozen Gigabytes it turned out that the huge
database files are a kind of headache and we moved to Storing the actual
original image data to [Amazon S3][2]. The server still is able to handle
Content stored in CouchDB and migrates it automatically to S3 where the need
arises.

[1]: http://couchdb.apache.org/
[2]: http://aws.amazon.com/s3

server.py works with any fast FastCGI compliant Webserver. It needs the
[Flup][3] toolkit installed to interface to a FastCGI enabled Server. We
use [lighttpd][4] for connectiong to it and `server.py` contains
configuration instructions for lighttpd. Of course you also can use other
httpd servers instead.

[3]: http://trac.saddi.com/flup
[4]: http://www.lighttpd.net/

server.py assumes that you have a filesystem which is able to handele very
large cache directories with no substential preformance penalty. We have been
running the system on [UFS2/dirhash][5] and XFS systems with success but it
should also work well on modenrn ext2/3 implementations with
[directory indexing][6].

[5]: http://code.google.com/soc/2008/freebsd/appinfo.html?csaid=69F96419FD4920FF
[6]: http://ext2.sourceforge.net/2005-ols/paper-html/node3.html

Wen a image is Requested and the original image is not in the Cache, the
original is pulled form CouchDB/S3 and put into the filesystem cache. Then the
[Python Imaging Library (PIL)[7] isused to generate the scaled version of the
image. The result is cached again in the filesystem and send to the client.

[7]: http://www.pythonware.com/products/pil/

If the image is requested again, it is served directly from the filesystem by
lighttpd without ever hitting the Python based `server.py`.

If you are short on diskspace fou can expire files from the cache directory
by just removing the oldest file until you have enough space again.


# Server Installation

We will show installation on a Ubuntu 9.10 based [Amazon EC2][8] instance.
huImages should qork on every POSIX system but requores a recent CouchDB
version. I assume you have an [EC2 environment up and running][9] and your
EC2-SSH key is named "ssh-ec2" and located in the current directory.

[8]: http://aws.amazon.com/ec2/
[9]: https://help.ubuntu.com/community/EC2StartersGuide


    INSTANCE=`ec2-run-instances ami-a62a01d2 --key ssh-ec2 --region eu-west-1 | cut -f2 | tail -n1`
    sleep 60
    IP=`ec2-describe-instances $INSTANCE | cut -f 17 | tail -n1`
    ssh -i ssh-ec2 ubuntu@$IP

You now should be logged into the new Amazon instance

    sudo apt-get update -y
    sudo apt-get install -y couchdb lighttpd git-core
    sudo apt-get install -y python-pip python-boto python-imaging
    sudo apt-get install -y python-couchdb python-flup

    git clone git://github.com/hudora/huImages.git
    sudo mv huImages /usr/local/huImages
    cd /usr/local/huImages
    sudo mkdir /mnt/huimages-cache
    sudo ln -s /mnt/huimages-cache /usr/local/huImages/cache
    sudo cp examples/lighttpd.conf /etc/lighttpd/lighttpd.conf
    sudo vi /etc/lighttpd/lighttpd.conf

Change `%%AWS_ACCESS_KEY_ID%%`, `%%AWS_SECRET_ACCESS_KEY%%` and `%%S3BUCKET%%`
to the appropriate values.

    sudo /etc/init.d/lighttpd restart
    sudo chown www-data.www-data /mnt/huimages-cache /usr/local/huImages/cache
    curl -X PUT http://127.0.0.1:5984/huimages
    curl -X PUT http://127.0.0.1:5984/huimages_meta

Now you can start putting images into the Database.


# Client usge

Now you can start putting images into the Database. If you don't run on the
same Server, you must find a wy to make CouchDB accessible to the client.
[Running a CouchDB cluster on Amazon EC2][10] might be a good startingpoint.
An other (easier) approach is simply running the client on the same machine
as the server.

[10]: http://blogs.23.nu/c0re/2009/12/running-a-couchdb-cluster-on-amazon-ec2/

Now ensure the required environment variables are set. Here are some sample
values:

    AWS_ACCESS_KEY_ID=AAOWSMAKNATAM5
    AWS_SECRET_ACCESS_KEY=aHo789V1H1Kzrs3yIaj7Uvxtskz6fUvgpa6n
    IMAGESERVERURL=http://i.hdimg.net/
    COUCHSERVER=http://admin:7o8V91H1Krzs3yIjaU7xtv@127.0.0.1:5984/
    S3BUCKET=originals.i.hdimg.net
    
    Now you should be able to use it like this:
    
    >>> import huimages
    >>> imagedata=open('./test.jpeg').read()
    >>> huimages.save_image(imagedata, filename='test.jpeg')
    '23EQ53G6WZTGF5675CUJQFKBIS6UWWOL01'

    >>> huimages.imageurl('23EQ53G6WZTGF5675CUJQFKBIS6UWWOL01')
    'http://i.hdimg.net/o/23EQ53G6WZTGF5675CUJQFKBIS6UWWOL01.jpeg'

    >>> huimages.scaled_imageurl('23EQ53G6WZTGF5675CUJQFKBIS6UWWOL01', size="150x150!")
    'http://i.hdimg.net/150x150!/23EQ53G6WZTGF5675CUJQFKBIS6UWWOL01.jpeg'

    >>> huimages.get_length('23EQ53G6WZTGF5675CUJQFKBIS6UWWOL01')
    87761

    >>> huimages.scaled_dimensions('23EQ53G6WZTGF5675CUJQFKBIS6UWWOL01', '320x240')
    (240, 240)

Call `pydoc huimages` for further documentation.


# Security

Malicious users knowing the ID of an image can consume great amounts of CPU
time, bandwith and diskspace.

Users knowing the IS of an image can pass that one to unautorized users.

Nobody should be able to see images on the server unless he knows the ID
or has access to the CouchDB or S3 bucket. Be sure that your S3 bucket does
[*not* provide public read access][11]!

[11]: http://www.bucketexplorer.com/documentation/amazon-s3--access-control-list-details.html


# Further Reading

 * [Blogpost about image Serving][12] (in german)
 * [django-photologue][13] - somewhat similar application

[12]: http://blogs.23.nu/disLEXia/2009/02/imageserver/
[13]: http://code.google.com/p/django-photologue/
