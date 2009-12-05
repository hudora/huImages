long_description = """huimages is an way of storing images in couchdb and serving them with high
preformance back to the client."""

from setuptools import setup, find_packages

setup(name='huimages',
      maintainer='Maximillian Dornseif',
      maintainer_email='md@hudora.de',
      version='1.04p1',
      description='Image storage & scaling in CouchDB.',
      long_description=long_description,
      classifiers=['License :: OSI Approved :: BSD License',
                   'Intended Audience :: Developers',
                   'Programming Language :: Python'],
      download_url='https://cybernetics.hudora.biz/nonpublic/eggs/',
      package_data={"huimages": ["imagebrowser/templates/imagebrowser/*.html"]},
      zip_safe=False,
      packages=find_packages(),
      include_package_data=True,
      install_requires=['couchdb', 'huTools'], # PIL/Imaging has serious issues with easy_install
      dependency_links = ['http://cybernetics.hudora.biz/dist/', 'http://cybernetics.hudora.biz/nonpublic/eggs/',
                          'http://www.pythonware.com/products/pil/'],
)
