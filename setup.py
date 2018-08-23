"""Configure doxy_db."""

from setuptools import setup

with open("README.md", "r") as f:
    readme = f.read()

setup(
    name="doxy_db",
    author="Travis A. Everett",
    author_email="travis.a.everett+doxy_db@gmail.com",
    install_requires=[],
    setup_requires=["pytest-runner"],
    tests_require=["pytest", "coverage"],
    extras_require={"dev": ["black"]},
    packages=["doxy_db"],
    # description="",
    long_description=readme,
    include_package_data=True,
    classifiers=[
        # 'Development Status :: 3 - Alpha',
        "License :: OSI Approved :: MIT License",
        # 'Programming Language :: Python :: 2.7',
        "Topic :: Documentation",
        "Topic :: Software Development :: Documentation",
    ],
    license="MIT",
    keywords="Doxygen docs documentation sqlite3",
    url="https://github.com/abathur/doxy_db",
    project_urls={
        "Issue Tracker": "https://github.com/abathur/doxy_db/issues",
        # "Documentation": "https://github.com/abathur/doxy_db",
    },
    test_suite="doxy_db.tests",
)
