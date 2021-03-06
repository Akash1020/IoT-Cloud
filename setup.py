# -*- coding: utf-8 -*-

from setuptools import setup


with open('README.md') as f:
    readme = f.read()

with open('LICENSE') as f:
    license = f.read()

setup(
    name='iot-cloud-cli',
    version='0.1.0',
    description='Privacy friendly framework for IoT Cloud',
    long_description=readme,
    author='Martin Heinz',
    author_email='martin7.heinz@gmail.com',
    url='',
    license=license,
    packages=['client', 'client.user', 'client.device'],
    include_package_data=True,
    install_requires=[
        'Click',
        'requests',
        'cryptography',
        'tinydb',
        'paho-mqtt',
        'passlib',
        'scipy',
        'APScheduler',
        'mmh3',
        'pyope',
        'flask',
        'Charm-Crypto',
        'SQLAlchemy',
        'Flask-SQLAlchemy',
        'Authlib'
    ],
    entry_points='''
        [console_scripts]
        iot-cloud-cli=client.cli:cli
    ''',
)
