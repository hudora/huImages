long_description = """huimages is an way of storing images in couchdb and
serving them with high preformance back to clients."""

from setuptools import setup, find_packages

setup(name='huImages',
      maintainer='Maximillian Dornseif',
      maintainer_email='md@hudora.de',
      version='2.01',
      url='http://github.com/hudora/huImages/',
      description='Image storage & scaling in CouchDB.',
      long_description=long_description,
      classifiers=['License :: OSI Approved :: BSD License',
                   'Intended Audience :: Developers',
                   'Programming Language :: Python'],
      # CARVE! setuptools seems buggy in regard of sdist & package_data
      package_data={"huImages": ["huimages/imagebrowser/templates/imagebrowser/*.html"]},
      zip_safe=False,
      packages=find_packages(),
      include_package_data=True,
      install_requires=['couchdb', 'huTools', 'boto'], # PIL/Imaging has serious issues with easy_install
      dependency_links = ['http://cybernetics.hudora.biz/nonpublic/eggs/',
                          'http://www.pythonware.com/products/pil/'],
)
