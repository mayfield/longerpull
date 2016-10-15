from setuptools import setup, find_packages
from distutils.core import Extension

README = 'README.md'

with open('requirements.txt') as f:
    requirements = f.readlines()


def long_desc():
    try:
        import pypandoc
    except ImportError:
        with open(README) as f:
            return f.read()
    else:
        return pypandoc.convert(README, 'rst')

setup(
    name='longerpull',
    version='1',
    description='AIO service for long-pull style RPC',
    author='Justin Mayfield',
    author_email='tooker@gmail.com',
    url='https://github.com/mayfield/longerpull/',
    license='MIT',
    long_description=long_desc(),
    packages=find_packages(),
    ext_modules=[
        Extension('longerpull._protocol',
                  sources=['longerpull/_protocol.c'],
                  libraries=['z']
        )
    ],
    test_suite='test',
    install_requires=requirements,
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.5',
    ]
)
