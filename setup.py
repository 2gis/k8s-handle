import os
from setuptools import setup, find_packages

readme_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'README.md')


def get_content(path):
    with open(path, 'r') as f:
        return f.read()


setup(name='k8s-handle',
      version=os.environ.get('RELEASE_TAG', '0.0.0'),
      long_description=get_content(readme_path),
      long_description_content_type='text/markdown',
      description='Provisioning tool for Kubernetes apps',
      url='http://github.com/2gis/k8s-handle',
      author='Vadim Reyder',
      author_email='vadim.reyder@gmail.com',
      license='Apache 2.0',
      packages=find_packages(exclude=("tests",)),
      data_files=['requirements.txt'],
      entry_points={
          "console_scripts": [
              "k8s-handle=k8s_handle:main",
          ]
      },
      install_requires=get_content('requirements.txt').split('\n'),
      zip_safe=False)
