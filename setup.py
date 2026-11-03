import setuptools

with open('README.md', 'r', encoding='utf-8') as fh:
    long_description = fh.read()

setuptools.setup(
    name='ShowSys',
    author='Nat Lee',
    author_email='natlee.work@gmail.com',
    description='A simple package to get system spec information',
    keywords='system, information, spec, hardware, software, os, platform, cpu, memory, disk, network, cli, command, line, interface, tool, utility',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/NatLee/show-system-info',
    project_urls={
        'Documentation': 'https://github.com/NatLee/show-system-info',
        'Bug Reports': 'https://github.com/NatLee/show-system-info/issues',
        'Source Code': 'https://github.com/NatLee/show-system-info'
    },
    package_dir={'': 'src'},
    packages=setuptools.find_packages(where='src'),
    # py.typed: tells type checkers that showsys ships its own type hints (PEP 561).
    package_data={'showsys': ['py.typed']},
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
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: 3.13',
        'Programming Language :: Python :: 3.14',
        'Programming Language :: Python :: 3 :: Only',
        'Typing :: Typed',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.7',
    install_requires=['psutil', 'py-cpuinfo'],
    extras_require={
        'dev': ['check-manifest'],
        'test': ['pytest'],
        # NVIDIA GPUs for --gpu; the official NVML bindings, imported as pynvml.
        'gpu': ['nvidia-ml-py'],
    },
    entry_points={
        'console_scripts': [
            'showsys=showsys.cli:main'
        ]
    }
)
