# setting the PATH seems only to work in GNUmake not in BSDmake
PATH := ./testenv/bin:$(PATH)

default: dependencies check

hudson: dependencies check statistics
	find huimages -name '*.py' | xargs /usr/local/hudorakit/bin/hd_pep8
	/usr/local/hudorakit/bin/hd_pylint -f parseable huimages | tee .pylint.out

check:
	find huimages -name '*.py' | xargs /usr/local/hudorakit/bin/hd_pep8
	/usr/local/hudorakit/bin/hd_pylint huimages

dependencies:
	virtualenv testenv
	pip -q install -E testenv -r requirements.txt

build:
	curl -o huimages/imagebrowser/swfupload.swf http://s.hdimg.net/libs/swfupload/swfupload.swf
	python setup.py build sdist bdist_egg

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
