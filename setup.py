"""PyPi setup script."""
import setuptools

with open("README.md", "r") as fh:  # pylint: disable=unspecified-encoding
    long_description = fh.read()

setuptools.setup(
    name="pykeurig",
    version="1.2.0",
    author="Dominick Meglio",
    license="MIT",
    author_email="dmeglio@gmail.com",
    description="Provides an interface to the Keurig API.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/dcmeglio/pykeurig",
    packages=setuptools.find_packages(),
    install_requires=["httpx", "signalrcoreplus", "tzlocal"],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
)
