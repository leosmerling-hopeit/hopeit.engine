import setuptools

version = {}
with open("../../../engine/src/hopeit/server/version.py") as fp:
    exec(fp.read(), version)

setuptools.setup(
    name="hopeit.redis-storage",
    version=version['ENGINE_VERSION'],
    description="Hopeit Engine Redis Storage Toolkit",
    license="Apache 2",
    long_description=open('README.md').read(),
    long_description_content_type="text/markdown",
    author="Leo Smerling and Pablo Canto",
    author_email="contact@hopeit.com.ar",
    url="https://github.com/hopeit-git/hopeit.engine",
    classifiers=[
        "License :: OSI Approved :: Apache Software License",
        "Intended Audience :: Developers",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Development Status :: 5 - Production/Stable",
        "Operating System :: POSIX :: Linux",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: Microsoft :: Windows",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Framework :: AsyncIO",
    ],    
    project_urls={
        "CI: GitHub Actions": "https://github.com/hopeit-git/hopeit.engine/actions?query=workflow",  # noqa
        "Docs: RTD": "https://hopeitengine.readthedocs.io/en/latest/",
        "GitHub: issues": "https://github.com/hopeit-git/hopeit.engine/issues",
        "GitHub: repo": "https://github.com/hopeit-git/hopeit.engine",
    },
    package_dir={
        "": "src"
    },
    packages=[
        "hopeit.redis_storage"
    ],
    include_package_data=True,
    package_data={
        "hopeit.redis_storage": ["py.typed"]
    },
    python_requires=">=3.9",
    install_requires=[
        f"hopeit.engine=={version['ENGINE_VERSION']}",
        "redis>=5.0.0"
    ],
    extras_require={
    },
    entry_points={
    }
)
