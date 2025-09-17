from setuptools import setup, find_packages
about = {}
with open("archivetools/__version__.py") as f:
    exec(f.read(), about)


setup(
    name="archivetools",
    version=about["__version__"],
    description="A suite of tools for archiving, cleaning, organizing, and validating media collections.",
    author="gabbro246",
    packages=["archivetools"],
    install_requires=[
        "pyzipper",
        "piexif",
        "Pillow",
        "colorama",
    ],
    entry_points={
        "console_scripts": [
            "checkmediacorruption=archivetools.checkmediacorruption:main",
            "cleanup=archivetools.cleanup:main",
            "converttozip=archivetools.converttozip:main",
            "converttofolder=archivetools.converttofolder:main",
            "deleteduplicates=archivetools.deleteduplicates:main",
            "flattenfolder=archivetools.flattenfolder:main",
            "organizebydate=archivetools.organizebydate:main",
            "setdates=archivetools.setdates:main",
        ]
    },
    include_package_data=True,
    python_requires=">=3.7",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
