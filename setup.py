# coding: utf-8
from setuptools import setup

setup(
    name='remote_storage_finder',
    version='0.0.1',
    license='BSD',
    author=u'shandymora',
    description=('A plugin for connecting graphite-web with remote graphite-webs'),
    py_modules=('remote_storage_finder',),
    zip_safe=False,
    include_package_data=True,
    platforms='any',
    classifiers=(
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Topic :: System :: Monitoring',
    ),
    install_requires=(
        'requests',
    ),
)