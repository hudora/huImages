# setting the PATH seems only to work in GNUmake not in BSDmake
PATH := ./pythonenv/bin:$(PATH)

default: dependencies

cleanup: clean
	2to3 -w -f zip -f xreadlines -f xrange -f ws_comma -f throw -f standarderror -f repr \
	-f raise -f paren -f nonzero -f ne -f idioms -f has_key \
	-f getcwdu -f filter -f except huimages
	# on 2.7 we also can use -f print -f isinstance -f reduce
	pip -q install -E pythonenv 'huTools>=0.44' pep8
	./pythonenv/bin/reindent.py -r huimages
	# returncode is broken until http://bit.ly/dknmXy is pulled into the main trunk
	-./pythonenv/bin/pep8 --count --repeat --ignore=E501,E301,E302,E303 huimages

dependencies:
	virtualenv testenv
	pip -q install -E testenv -r requirements.txt

build:
	curl -o huimages/imagebrowser/swfupload.swf http://s.hdimg.net/libs/swfupload/swfupload.swf
	python setup.py build sdist

statistics:
	sloccount --wide --details huimages > .sloccount.sc

upload: build
	python setup.py sdist upload

install: build
	sudo python setup.py install

clean:
	rm -Rf testenv build dist html test.db .pylint.out .sloccount.sc pip-log.txt
	find . -name '*.pyc' -or -name '*.pyo' -delete

.PHONY: build clean install upload check
