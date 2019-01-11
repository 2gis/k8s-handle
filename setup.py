import os
from setuptools import setup, find_packages

readme_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'README.md')


def get_content(path):
    with open(path, 'r') as f:
        return f.read()


setup(name='k8s-handle',
      version='0.2.3',
      long_description=get_content(readme_path),
      long_description_content_type="text/markdown",
      description='Provisioning tool for Kubernetes apps',
      url='http://github.com/2gis/k8s-handle',
      author='Vadim Reyder',
      author_email='vadim.reyder@gmail.com',
      license='Apache 2.0',
      packages=find_packages(exclude=("tests",)),
      entry_points={
          "console_scripts": [
              "k8s-handle=k8s_handle:main",
          ]
      },
      install_requires=[
          'requests>=2.20.1',
          'jinja2>=2.10',
          'PyYAML>=4.2b4',
          'kubernetes>=6.0.0',
          'semver>=2.8.1',
      ],
      zip_safe=False)
