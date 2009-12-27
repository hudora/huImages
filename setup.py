long_description = """huimages is an way of storing images in couchdb and
serving them with high preformance back to clients."""

from setuptools import setup, find_packages

setup(name='huImages',
      maintainer='Maximillian Dornseif',
      maintainer_email='md@hudora.de',
      version='2.0p1',
      url='http://github.com/hudora/huImages/',
      description='Image storage & scaling in CouchDB.',
      long_description=long_description,
      classifiers=['License :: OSI Approved :: BSD License',
                   'Intended Audience :: Developers',
                   'Programming Language :: Python'],
      package_data={"huimages": ["imagebrowser/templates/imagebrowser/*.html"]},
      zip_safe=False,
      packages=find_packages(),
      include_package_data=True,
      install_requires=['couchdb', 'huTools', 'boto'], # PIL/Imaging has serious issues with easy_install
      dependency_links = ['http://cybernetics.hudora.biz/dist/', 'http://cybernetics.hudora.biz/nonpublic/eggs/',
                          'http://www.pythonware.com/products/pil/'],
)
