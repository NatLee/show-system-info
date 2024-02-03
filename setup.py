import setuptools

with open('README.md', 'r', encoding='utf-8') as fh:
    long_description = fh.read()

setuptools.setup(
    name='System Info',
    author='Nat Lee',
    author_email='natlee.work@gmail.com',
    description='A simple package to get system spec information',
    keywords='system, information, spec, hardware, software, os, platform, cpu, memory, disk, network, gpu, display, monitor, resolution, screen, monitor, heic, heif, png, convert, converter, cli, command, line, interface, tool, utility',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/natlee/system-info',
    project_urls={
        'Documentation': 'https://github.com/natlee/system-info',
        'Bug Reports': 'https://github.com/natlee/system-info/issues',
        'Source Code': 'https://github.com/natlee/system-info'
    },
    package_dir={'': 'src'},
    packages=setuptools.find_packages(where='src'),
    classifiers=[
        # see https://pypi.org/classifiers/
        'Development Status :: 5 - Production/Stable',

        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',

        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3 :: Only',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.7',
    install_requires=['psutil'],
    extras_require={
        'dev': ['check-manifest'],
        # 'test': ['coverage'],
    },
    entry_points={
        'console_scripts': [
            'systeminfo=systeminfo.cli:main'
        ]
    }
)
