check: clean
	find huimages -name '*.py'  -exec pep8 --ignore=E501,W291 --repeat {} \;
	pylint huimages

build:
	python setup.py build sdist bdist_egg

upload: build
	rsync dist/* root@cybernetics.hudora.biz:/usr/local/www/apache22/data/nonpublic/eggs/


install: build
	sudo python setup.py install

clean:
	rm -Rf build dist html test.db
	find . -name '*.pyc' -or -name '*.pyo' -delete

.PHONY: build clean install upload check
